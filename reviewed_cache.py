"""Exact reviewed path guard; provisional caches never enter this boundary."""
from dataclasses import asdict
from evidence_registry import POLICY_VERSION, content_hash


def reviewed_cache_key(registry, session, intent, prompt_version, verifier_version):
    payload = {"checksum": registry.checksum, "variant": session.bike_variant,
               "edition": session.edition, "intent": intent, "symptoms": sorted(session.current_symptoms),
               "registry_lock": registry.lock, "controller_version": POLICY_VERSION,
               "generation_lock": session.generation_lock,
               "prompt_version": prompt_version, "verifier_version": verifier_version,
               "typed_path": [{"step_id": a.step_id, "condition_id": a.condition_id,
                               "outcome": a.outcome_enum.value,
                               "facts": [(k, asdict(v)) for k, v in a.observed_details]}
                              for a in session.active_attempts() if a.outcome_enum.value != "NOT_TRIED"]}
    return content_hash(payload)


def lookup_reviewed_cache(registry, session, cache, intent, prompt_version, verifier_version):
    # Even a forged legacy approved flag or allow_draft switch cannot cross this gate.
    if not registry.source_ready() or session.version_lock != registry.lock:
        return None
    if session.bike_variant != registry.source["variant"] or session.edition != registry.source["edition"]:
        return None
    if cache.get("schema_version") != "reviewed-path-cache-v1" or cache.get("registry_lock") != registry.lock:
        return None
    key = reviewed_cache_key(registry, session, intent, prompt_version, verifier_version)
    entry = cache.get("entries", {}).get(key)
    if not entry or entry.get("review_status") != "APPROVED" or not entry.get("independent_review"):
        return None
    required = entry.get("step_ids", [])
    if not required or not all(sid in registry.candidate["steps"] and registry.step_ready(sid) for sid in required):
        return None
    # This returns a draft to the controller, never an already-authorized response.
    return entry.get("draft")
