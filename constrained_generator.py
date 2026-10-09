"""Controller-selected approved wording only, followed by separate entailment.

Exact wording membership is a composition constraint, NEVER semantic validation.
Synthetic providers/verifiers test software only and are not calibrated judges.
"""
from copy import deepcopy
from dataclasses import replace
import json
import time

from controller_contracts import ResponseType, Truth
from generation_contracts import (RuntimeConfig, SCHEMA_VERSION, GENERATION_POLICY,
                                  VERIFICATION_POLICY, RESPONSE_SCHEMA, VERIFIER_SCHEMA)
from generation_providers import ProviderResult, UnconfiguredProvider, ProviderFailure


class ValidationFailure(RuntimeError):
    pass


def strict_schema(value, schema):
    kind = schema["type"]
    if kind == "object":
        if type(value) is not dict or set(value) != set(schema["properties"]):
            raise ValidationFailure("OUTPUT_SCHEMA")
        for key, prop in schema["properties"].items():
            strict_schema(value[key], prop)
    elif kind == "array":
        if type(value) is not list or len(value) > 256:
            raise ValidationFailure("OUTPUT_SCHEMA")
        for item in value:
            strict_schema(item, schema["items"])
    elif ((kind == "integer" and type(value) is not int) or
          (kind == "boolean" and type(value) is not bool) or
          (kind == "string" and (type(value) is not str or not value or len(value) > 8000))):
        raise ValidationFailure("OUTPUT_SCHEMA")


def citations(registry, step):
    refs = []
    for eid in sorted(step.required_evidence_ids):
        for prov in registry.evidence[eid]["provenance"]:
            page = prov.get("page_no", prov.get("pdf_page"))
            if type(page) is not int or not 1 <= page <= registry.source["pdf_pages"]:
                raise ValidationFailure("INVALID_SOURCE_PAGE")
            ref = {"evidence_id": eid, "pdf_page": page}
            if ref not in refs:
                refs.append(ref)
    if not refs:
        raise ValidationFailure("MISSING_SOURCE_PROVENANCE")
    return refs


def envelope(controller, session, sid):
    r, step = controller.registry, controller.registry.step(sid)
    if not r.step_ready(sid) or not r.source_ready():
        raise ValidationFailure("SOURCE_REVIEW_REQUIRED")
    if controller.eligible(session, sid).eligibility_status != Truth.TRUE:
        raise ValidationFailure("STEP_NOT_ELIGIBLE")
    if not step.claims or len(step.claims) > 64:
        raise ValidationFailure("CLAIM_BOUND_OR_EMPTY")
    claims = []
    for c in step.claims:
        # Variants are inside the content-hashed independently reviewed step.
        wording = [c["text"], *c.get("reviewed_wording_variants", [])]
        if any(type(t) is not str or not t or len(t) > 8000 for t in wording) or len(wording) > 4:
            raise ValidationFailure("INVALID_REVIEWED_WORDING")
        if controller.audience == "end_user" and (c.get("verbatim_warning") or c.get("presentation_mode") != "REVIEWED_PARAPHRASE"):
            raise ValidationFailure("END_USER_EXCERPT_DISPLAY_PROHIBITED")
        # Metadata authoring contract establishes roles; models cannot label actions.
        role = c.get("response_role")
        if role not in ("ACTION", "FACT", "WARNING", "PREREQUISITE"):
            raise ValidationFailure("CLAIM_ROLE_REVIEW_REQUIRED")
        if any("?" in text for text in wording):
            raise ValidationFailure("UNEXPECTED_TECHNICAL_QUESTION")
        # Specifications and table units remain byte-for-byte reviewed content.
        # No model-written numbers/units or additional steps are accepted.
        claims.append({"claim_id": c["claim_id"], "wording": wording,
                       "evidence_ids": list(c["evidence_ids"]), "role": role})
    if len({c["claim_id"] for c in claims}) != len(claims):
        raise ValidationFailure("DUPLICATE_CLAIM_ID")
    actions = sum(c["role"] == "ACTION" for c in claims)
    if actions != (1 if step.kind == "ACTION" else 0):
        raise ValidationFailure("ONE_STEP_DISCIPLINE")
    categories = r.candidate["dependencies"][sid]["categories"]
    if categories.get("figures") or any(r.evidence[eid].get("type") in ("picture", "figure", "image")
                                        for eid in step.required_evidence_ids):
        # This text-only verifier cannot evaluate a referenced image. Do not infer it.
        raise ValidationFailure("FIGURE_SEMANTIC_ADAPTER_UNAVAILABLE")
    for category, role in (("warnings", "WARNING"), ("prerequisites", "PREREQUISITE")):
        covered = {e for c in claims if c["role"] == role for e in c["evidence_ids"]}
        if not set(categories.get(category, [])) <= covered:
            raise ValidationFailure("MANDATORY_WARNING_OR_CONDITION_OMITTED")
    if any(not c["evidence_ids"] or not set(c["evidence_ids"]) <= set(step.required_evidence_ids) for c in claims):
        raise ValidationFailure("INVALID_CLAIM_CITATION")
    # No raw rider text, media, observation values or free-form attempted details.
    # Claim choice needs no chat transcript; typed history only describes attempts.
    return {"schema_version": SCHEMA_VERSION, "route": "SUPPORTED", "step_id": sid,
            "kind": step.kind, "claims": claims, "citations": citations(r, step),
            "audience": controller.audience, "manual_checksum": r.checksum,
            "index_id": r.index_id, "registry_lock": r.lock,
            "typed_context": [{"step_id": a.step_id, "outcome": a.outcome_enum.value}
                              for a in session.active_attempts()[-12:]]}


def validate_output(draft, allowed):
    strict_schema(draft, RESPONSE_SCHEMA)
    for key in ("schema_version", "route", "step_id", "kind", "citations"):
        if draft[key] != allowed[key]:
            raise ValidationFailure("OUTPUT_CHANGED_" + key.upper())
    if len(draft["claims"]) != len(allowed["claims"]):
        raise ValidationFailure("CLAIM_OMITTED_OR_ADDED")
    for proposed, approved in zip(draft["claims"], allowed["claims"]):
        if proposed["claim_id"] != approved["claim_id"] or proposed["evidence_ids"] != approved["evidence_ids"]:
            raise ValidationFailure("CLAIM_MAPPING_CHANGED")
        if proposed["text"] not in approved["wording"]:
            raise ValidationFailure("UNREVIEWED_WORDING_OR_SPECIFICATION")
    return draft


class SemanticSupportAdapter:
    def __init__(self, provider=None):
        self.provider = provider or UnconfiguredProvider()
        self.last_usage = None

    def verify(self, draft, allowed, evidence):
        self.last_usage = None
        # Only evidence supporting selected claims, no adjacent search hits/prompts.
        objects = {eid: {"type": e.get("type"), "raw_object": e.get("raw_object"),
                         "provenance": e.get("provenance")}
                   for eid, e in evidence.items()}
        payload = {"claims": draft["claims"], "evidence": objects,
                   "selected_kind": allowed["kind"], "audience": allowed["audience"]}
        result = self.provider.complete(VERIFICATION_POLICY, payload, VERIFIER_SCHEMA)
        self.last_usage = result
        strict_schema(result.output, VERIFIER_SCHEMA)
        rows = result.output["claims"]
        ids = [c["claim_id"] for c in draft["claims"]]
        if ([c["claim_id"] for c in rows] != ids or
                any(c["supported"] is not True for c in rows) or
                result.output["unsupported_additions"] is not False):
            raise ValidationFailure("SEMANTIC_SUPPORT_REJECTED")
        return result


class ConstrainedGenerator:
    def __init__(self, provider=None, verifier=None, config=None):
        self.provider = provider or UnconfiguredProvider()
        self.verifier = verifier or SemanticSupportAdapter()
        self.config = config or RuntimeConfig()
        self.last_trace = None

    def compose(self, controller, session, sid, *, cache_draft=None):
        started = time.perf_counter()
        trace = {"runtime_lock": self.config.lock, "versions": self.config.versions(),
                 "generation_calls": 0, "verifier_calls": 0, "retry_count": 0,
                 "generation_ms": 0, "validation_ms": 0, "input_tokens": None,
                 "output_tokens": None, "estimated_cost_usd": None, "cost_status": "NO_CALL",
                 "source_or_user_text_recorded": False}
        self.last_trace = trace
        def bounded(payload):
            if len(json.dumps(payload, allow_nan=False).encode()) > self.config.max_input_bytes:
                raise ValidationFailure("CONTEXT_BOUND_NO_TRUNCATION")
        try:
            allowed = envelope(controller, session, sid)
            if session.generation_lock != self.config.lock:
                raise ValidationFailure("GENERATION_VERSION_RECONFIRM_REQUIRED")
            bounded(allowed)
            if cache_draft is None:
                trace["generation_calls"] = 1
                trace["cost_status"] = "UNKNOWN_PENDING_PROVIDER_USAGE"
                result = self.provider.complete(GENERATION_POLICY, deepcopy(allowed), RESPONSE_SCHEMA)
                trace["generation_transport"] = result.telemetry
                draft = result.output
                trace.update(input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                             estimated_cost_usd=result.cost_usd)
            else:
                draft = deepcopy(cache_draft)  # Approved cache is still untrusted output.
            trace["generation_ms"] = (time.perf_counter() - started) * 1000
            validate_started = time.perf_counter()
            bounded(draft)
            validate_output(draft, allowed)
            step = controller.registry.step(sid)
            evidence = {e: controller.registry.evidence[e] for e in step.required_evidence_ids}
            bounded({"draft": draft, "evidence": evidence})
            trace["verifier_calls"] = 1
            trace["cost_status"] = "UNKNOWN_PENDING_PROVIDER_USAGE"
            checked = self.verifier.verify(deepcopy(draft), deepcopy(allowed), deepcopy(evidence))
            # Prevent an injected adapter mutating the draft/allowed authority.
            validate_output(draft, envelope(controller, session, sid))
            trace["verifier_transport"] = checked.telemetry
            trace["verifier_input_tokens"] = checked.input_tokens
            trace["verifier_output_tokens"] = checked.output_tokens
            trace["validation_ms"] = (time.perf_counter() - validate_started) * 1000
            trace["cost_status"] = "UNKNOWN_PRICING_NOT_CONFIGURED"
            claim_map = tuple({**c, "presentation_mode": controller.registry.step(sid).claims[i].get("presentation_mode")}
                              for i, c in enumerate(draft["claims"]))
            pages = tuple({**p, "manual_checksum": controller.registry.checksum,
                           "index_id": controller.registry.index_id, "pdf_page_index": p["pdf_page"]-1}
                          for p in draft["citations"])
            response = controller.response("SUPPORTED", " ".join(c["text"] for c in draft["claims"]), session,
                                           claim_evidence_map=claim_map, cited_pages=pages,
                                           suggested_step_id=sid if step.kind == "ACTION" else None,
                                           reason_codes=("CONSTRAINED_OUTPUT_VALIDATED",))
            trace["reason_codes"] = response.reason_codes
            trace["total_ms"] = (time.perf_counter() - started) * 1000
            return controller.for_end_user(response) if controller.audience == "end_user" else response
        except (ValidationFailure, ProviderFailure) as exc:
            # Reason codes cannot carry provider exception bodies or secret text.
            if isinstance(exc, ProviderFailure) and exc.telemetry:
                trace["failed_provider_transport"] = exc.telemetry
            if getattr(self.verifier, "last_usage", None):
                trace["verifier_transport"] = self.verifier.last_usage.telemetry
            candidate_code = str(exc)
            known = {"SOURCE_REVIEW_REQUIRED", "STEP_NOT_ELIGIBLE", "CLAIM_BOUND_OR_EMPTY",
                     "INVALID_REVIEWED_WORDING", "END_USER_EXCERPT_DISPLAY_PROHIBITED",
                     "CLAIM_ROLE_REVIEW_REQUIRED", "UNEXPECTED_TECHNICAL_QUESTION", "DUPLICATE_CLAIM_ID",
                     "ONE_STEP_DISCIPLINE", "MANDATORY_WARNING_OR_CONDITION_OMITTED", "INVALID_CLAIM_CITATION",
                     "INVALID_SOURCE_PAGE", "MISSING_SOURCE_PROVENANCE", "FIGURE_SEMANTIC_ADAPTER_UNAVAILABLE",
                     "GENERATION_VERSION_RECONFIRM_REQUIRED", "CONTEXT_BOUND_NO_TRUNCATION", "OUTPUT_SCHEMA",
                     "CLAIM_OMITTED_OR_ADDED", "CLAIM_MAPPING_CHANGED", "UNREVIEWED_WORDING_OR_SPECIFICATION",
                     "SEMANTIC_SUPPORT_REJECTED", "PROVIDER_UNCONFIGURED", "LIVE_CALL_NOT_AUTHORIZED",
                     "PROVIDER_CONTEXT_BOUND", "PROVIDER_OUTPUT_BOUND", "PROVIDER_INCOMPLETE_OR_MODEL_MISMATCH",
                     "PROVIDER_REFUSAL_OR_MALFORMED", "INVALID_PROVIDER_USAGE", "PROVIDER_TOKEN_BOUND",
                     "PROVIDER_REQUEST_FAILED", "PROVIDER_REDIRECT_REJECTED", "PROVIDER_TIMEOUT",
                     "PROVIDER_QUOTA_EXHAUSTED", "PROVIDER_SERVICE_ERROR", "PROVIDER_ACCESS_ERROR",
                     "PROVIDER_REQUEST_REJECTED", "PROVIDER_CONNECTION_FAILED", "PROVIDER_TRANSPORT_UNAVAILABLE"}
            known.update("OUTPUT_CHANGED_" + k.upper() for k in ("schema_version", "route", "step_id", "kind", "citations"))
            code = candidate_code if candidate_code in known else "GENERATION_OR_VERIFICATION_FAILURE"
        except Exception:
            code = "GENERATION_OR_VERIFICATION_FAILURE"
        trace["reason_codes"] = (code,)
        trace["total_ms"] = (time.perf_counter() - started) * 1000
        source_gap = code in ("SOURCE_REVIEW_REQUIRED", "END_USER_EXCERPT_DISPLAY_PROHIBITED", "CLAIM_ROLE_REVIEW_REQUIRED")
        return controller.response("UNSUPPORTED" if source_gap else "SYSTEM_ERROR",
                                   "I could not verify an approved answer for display." if source_gap else
                                   "I am temporarily unable to validate the response.", session, reason_codes=(code,))


def build_generator(config=None, *, live_enabled=False, authorized_calls_per_adapter=0):
    """Trusted server-side factory. Live access is never implied by a key/model name.

    Separate instances reserve separate call allocations; no charge is incurred here.
    Caller must separately authorize the provider account and total allocation.
    """
    from generation_providers import configured_provider
    config = config or RuntimeConfig()
    opts = {"enabled": live_enabled, "authorized_calls": authorized_calls_per_adapter}
    generator = configured_provider(config.generator_provider, config.generator_model, config, **opts)
    verifier = configured_provider(config.verifier_provider, config.verifier_model, config, **opts)
    return ConstrainedGenerator(generator, SemanticSupportAdapter(verifier), config)
