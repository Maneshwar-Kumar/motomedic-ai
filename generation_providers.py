"""Opt-in provider transport; credentials never enter envelopes, logs or locks."""
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, build_opener, HTTPRedirectHandler

from generation_contracts import RuntimeConfig


class ProviderFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderResult:
    output: dict
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


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


def configured_provider(name, model, config, **kwargs):
    if name == "unconfigured":
        return UnconfiguredProvider()
    if name == "openai":
        return OpenAIResponsesProvider(model, config, **kwargs)
    raise ValueError("Unknown provider")
