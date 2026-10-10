"""Opt-in provider transport; credentials never enter envelopes, logs or locks."""
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, build_opener, HTTPRedirectHandler

from generation_contracts import RuntimeConfig


class ProviderFailure(RuntimeError):
    def __init__(self, reason, telemetry=None):
        super().__init__(reason)
        self.telemetry = telemetry


@dataclass(frozen=True)
class ProviderResult:
    output: dict
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    telemetry: dict | None = None


class JSONProvider(Protocol):
    def complete(self, policy: str, payload: dict, schema: dict) -> ProviderResult: ...


class UnconfiguredProvider:
    def complete(self, policy, payload, schema):
        raise ProviderFailure("PROVIDER_UNCONFIGURED")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderFailure("PROVIDER_REDIRECT_REJECTED")


class OpenAIResponsesProvider:
    """One bounded POST, no SDK auto-retries, tools, streaming, history or storage.

    Live spending additionally requires an owner-authorized provider allocation.
    The GCP INR640 billing guard does not protect an OpenAI account.
    """
    def __init__(self, model, config, *, enabled=False, authorized_calls=0, opener=None):
        if not isinstance(config, RuntimeConfig):
            raise ValueError("Runtime configuration required")
        self.model, self.config = model, config
        self.enabled, self.remaining_calls = enabled, authorized_calls
        self.opener = opener or build_opener(NoRedirect())

    def complete(self, policy, payload, schema):
        if not self.enabled or self.remaining_calls < 1:
            raise ProviderFailure("LIVE_CALL_NOT_AUTHORIZED")
        key = os.environ.get("MOTOMEDIC_OPENAI_API_KEY")
        if not key:
            raise ProviderFailure("PROVIDER_UNCONFIGURED")
        # Byte bound conservatively bounds token input; no silent evidence truncation.
        data = json.dumps({"model": self.model, "instructions": policy,
                           "input": json.dumps(payload, ensure_ascii=False, allow_nan=False),
                           "store": False, "tools": [], "max_output_tokens": self.config.max_output_tokens,
                           "text": {"format": {"type": "json_schema", "name": "motomedic",
                                                "strict": True, "schema": schema}}}, allow_nan=False).encode()
        if len(data) > self.config.max_input_bytes:
            raise ProviderFailure("PROVIDER_CONTEXT_BOUND")
        self.remaining_calls -= 1  # Reserve even on failure; never automatically retry.
        request = Request("https://api.openai.com/v1/responses", data=data,
                          headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(131073)
            if len(raw) > 131072:
                raise ProviderFailure("PROVIDER_OUTPUT_BOUND")
            body = json.loads(raw)
            if body.get("status") != "completed" or body.get("model") != self.model:
                raise ProviderFailure("PROVIDER_INCOMPLETE_OR_MODEL_MISMATCH")
            content = [c for item in body.get("output", []) if item.get("type") == "message"
                       for c in item.get("content", [])]
            if len(content) != 1 or content[0].get("type") != "output_text":
                raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED")
            output = json.loads(content[0]["text"])
            usage = body.get("usage") or {}
            if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
                raise ProviderFailure("INVALID_PROVIDER_USAGE")
            if usage["output_tokens"] > self.config.max_output_tokens:
                raise ProviderFailure("PROVIDER_TOKEN_BOUND")
            return ProviderResult(output, usage["input_tokens"], usage["output_tokens"])
        except ProviderFailure:
            raise
        except Exception:
            # Never propagate HTTP bodies, exception messages, source strings or keys.
            raise ProviderFailure("PROVIDER_REQUEST_FAILED") from None



def _response_structure(chunks):
    """Count response shapes before rejection; retain no provider text or arbitrary keys."""
    result = {"chunk_count": 0, "candidate_count": 0,
              "maximum_candidates_per_chunk": 0, "candidate_index_valid": True,
              "text_part_count": 0, "thought_part_count": 0,
              "empty_thought_part_count": 0, "nonempty_thought_part_count": 0,
              "thought_signature_present": False, "thought_signature_part_count": 0,
              "nontext_part_count": 0, "known_nontext_field_count": 0,
              "other_part_field_count": 0, "invalid_structure_count": 0,
              "prompt_block_reasons": [], "usage_metadata_present": False,
              "reported_thoughts_token_count": "UNKNOWN"}
    nontext = {"inlineData", "fileData", "functionCall", "functionResponse",
               "executableCode", "codeExecutionResult"}
    known = nontext | {"text", "thought", "thoughtSignature"}
    blocks = {"BLOCK_REASON_UNSPECIFIED", "SAFETY", "OTHER", "BLOCKLIST",
              "PROHIBITED_CONTENT", "IMAGE_SAFETY"}
    for chunk in chunks:
        result["chunk_count"] += 1
        if not isinstance(chunk, dict):
            result["invalid_structure_count"] += 1
            continue
        feedback = chunk.get("promptFeedback")
        if isinstance(feedback, dict) and feedback.get("blockReason"):
            reason = feedback["blockReason"]
            result["prompt_block_reasons"].append(reason if isinstance(reason, str) and reason in blocks else "UNRECOGNIZED")
        if "usageMetadata" in chunk:
            result["usage_metadata_present"] = True
            usage = chunk["usageMetadata"]
            value = usage.get("thoughtsTokenCount") if isinstance(usage, dict) else None
            result["reported_thoughts_token_count"] = value if type(value) is int and value >= 0 else "UNKNOWN"
        candidates = chunk.get("candidates", [])
        if not isinstance(candidates, list):
            result["invalid_structure_count"] += 1
            continue
        result["candidate_count"] += len(candidates)
        result["maximum_candidates_per_chunk"] = max(result["maximum_candidates_per_chunk"], len(candidates))
        for candidate in candidates:
            if not isinstance(candidate, dict):
                result["candidate_index_valid"] = False
                result["invalid_structure_count"] += 1
                continue
            if candidate.get("index", 0) != 0:
                result["candidate_index_valid"] = False
            content = candidate.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else None
            if not isinstance(parts, list):
                result["invalid_structure_count"] += 1
                continue
            for part in parts:
                if not isinstance(part, dict):
                    result["invalid_structure_count"] += 1
                    continue
                text = part.get("text")
                if type(text) is str:
                    result["text_part_count"] += 1
                else:
                    result["nontext_part_count"] += 1
                if part.get("thought"):
                    result["thought_part_count"] += 1
                    if type(text) is str:
                        key = "empty_thought_part_count" if text == "" else "nonempty_thought_part_count"
                        result[key] += 1
                if "thoughtSignature" in part:
                    result["thought_signature_present"] = True
                    result["thought_signature_part_count"] += 1
                result["known_nontext_field_count"] += len(set(part) & nontext)
                result["other_part_field_count"] += len(set(part) - known)
    return result


class GeminiJSONProvider:
    """Explicit allowlisted Gemma comparison only. JSON is locally validated, not provider-guaranteed.

    System instruction carries policy and schema; payload remains untrusted user data.
    One SSE request, minimal thinking, no tools, history, fallback model or retries.
    """
    MODEL = "gemma-4-31b-it"
    ALLOWED_MODELS = (MODEL, "gemma-4-26b-a4b-it")
    def __init__(self, model, config, *, enabled=False, authorized_calls=0, transport=None):
        from gemini_transport import stream_request
        if (not isinstance(config, RuntimeConfig) or model not in self.ALLOWED_MODELS or
                config.generator_model != model or config.verifier_model != model or
                config.generator_provider != "gemini" or config.verifier_provider != "gemini"):
            raise ValueError("Exact same allowlisted Gemma model required for both adapters")
        if type(authorized_calls) is not int or authorized_calls < 0:
            raise ValueError("Finite nonnegative call allocation required")
        if config.provider_revision != "gemini-sse-json-models-utf8-diagnostics-v4":
            raise ValueError("Gemini transport revision required")
        self.model, self.config = model, config
        self.enabled, self.remaining_calls = enabled, authorized_calls
        self.transport = transport or stream_request
        self.last_telemetry = None

    def complete(self, policy, payload, schema):
        from gemini_transport import TransportFailure
        self.last_telemetry = None  # A denied new call must not inherit an earlier response.
        if not self.enabled or self.remaining_calls < 1:
            raise ProviderFailure("LIVE_CALL_NOT_AUTHORIZED")
        key = os.environ.get("MOTOMEDIC_GEMINI_API_KEY")
        if not key:
            raise ProviderFailure("PROVIDER_UNCONFIGURED")
        # Match Google SDK's UserContent transformation while retaining the
        # dedicated systemInstruction boundary for policy and schema.
        body = {"systemInstruction": {"role": "user", "parts": [{"text": policy +
                    " Return exactly one JSON object, no Markdown or commentary. " +
                    "Required output schema: " + json.dumps(schema, allow_nan=False)}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False, allow_nan=False)}]}],
                "generationConfig": {"maxOutputTokens": self.config.max_output_tokens,
                                     "thinkingConfig": {"thinkingLevel": "minimal"}}}
        if len(json.dumps(body, ensure_ascii=False, allow_nan=False).encode()) > self.config.max_input_bytes:
            raise ProviderFailure("PROVIDER_CONTEXT_BOUND")
        self.remaining_calls -= 1
        self.last_telemetry = {"requested_model": self.model, "retry_count": 0}
        try:
            chunks, trace = self.transport(self.model, key, body, self.config.timeout_seconds)
            self.last_telemetry = trace
            trace["response_structure"] = _response_structure(chunks)
            versions, fragments, finish = set(), [], []
            usage = None
            for chunk in chunks:
                if chunk.get("modelVersion"):
                    versions.add(chunk["modelVersion"])
                if chunk.get("promptFeedback", {}).get("blockReason"):
                    raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
                candidates = chunk.get("candidates", [])
                if len(candidates) > 1:
                    raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
                for candidate in candidates:
                    if candidate.get("index", 0) != 0:
                        raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
                    if candidate.get("finishReason"):
                        finish.append(candidate["finishReason"])
                    for part in candidate.get("content", {}).get("parts", []):
                        if part.get("thought") or set(part) - {"text", "thought"} or type(part.get("text")) is not str:
                            raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
                        fragments.append(part["text"])
                if "usageMetadata" in chunk:
                    usage = chunk["usageMetadata"]
            trace["returned_model_versions"] = [self.model] if versions == {self.model} else ["MISMATCH"]
            trace["finish_reasons"] = [f if f in ("STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER") else "UNRECOGNIZED" for f in finish]
            if versions != {self.model} or not finish or set(finish) != {"STOP"}:
                raise ProviderFailure("PROVIDER_INCOMPLETE_OR_MODEL_MISMATCH", trace)
            if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                    for k in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount")):
                raise ProviderFailure("INVALID_PROVIDER_USAGE", trace)
            thoughts = usage.get("thoughtsTokenCount", 0)
            if type(thoughts) is not int or thoughts != 0:
                raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
            if usage["totalTokenCount"] < usage["promptTokenCount"] + usage["candidatesTokenCount"]:
                raise ProviderFailure("INVALID_PROVIDER_USAGE", trace)
            if usage["candidatesTokenCount"] > self.config.max_output_tokens:
                raise ProviderFailure("PROVIDER_TOKEN_BOUND", trace)
            trace["usage_reported"] = True
            trace["input_tokens"] = usage["promptTokenCount"]
            trace["output_tokens"] = usage["candidatesTokenCount"]
            trace["total_tokens"] = usage["totalTokenCount"]
            trace["service_tier"] = usage.get("serviceTier") if usage.get("serviceTier") in ("standard", "priority", "flex") else "UNRECOGNIZED"
            def unique_pairs(pairs):
                obj = {}
                for k, v in pairs:
                    if k in obj:
                        raise ValueError("Duplicate key")
                    obj[k] = v
                return obj
            output = json.loads("".join(fragments), object_pairs_hook=unique_pairs,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
            if not isinstance(output, dict):
                raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", trace)
            return ProviderResult(output, usage["promptTokenCount"], usage["candidatesTokenCount"], None, trace)
        except TransportFailure as exc:
            self.last_telemetry = exc.telemetry
            raise ProviderFailure(str(exc), exc.telemetry) from None
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure("PROVIDER_REFUSAL_OR_MALFORMED", self.last_telemetry) from None


def gemma_runtime_config(model=GeminiJSONProvider.MODEL):
    """Explicit comparison selection; 31B default, never an automatic fallback."""
    if model not in GeminiJSONProvider.ALLOWED_MODELS:
        raise ValueError("Unknown Gemma comparison model")
    return RuntimeConfig(generator_provider="gemini", generator_model=model,
                         verifier_provider="gemini", verifier_model=model,
                         provider_revision="gemini-sse-json-models-utf8-diagnostics-v4", timeout_seconds=30)


def configured_provider(name, model, config, **kwargs):
    if name == "unconfigured":
        return UnconfiguredProvider()
    if name == "gemini":
        return GeminiJSONProvider(model, config, **kwargs)
    if name == "openai":
        return OpenAIResponsesProvider(model, config, **kwargs)
    raise ValueError("Unknown provider")
