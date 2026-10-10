"""Audit saved hosted results; no provider, cloud or source mutation."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def audit(path, run_id):
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "architecture-comparison-v3"
    assert raw["model"] == "gemma-4-26b-a4b-it"
    assert raw["index_id"] == "index_a3282c4d98cf54595e4ba168"
    assert raw["manual_checksum"] == "cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89"
    assert raw["automatic_model_fallback"] is False
    rows = raw["rows"]
    assert len(rows) == 9
    expected = {(rid, arch) for rid in ("GEN003", "EXP003", "GEN026") for arch in
                ("A_COMPONENT_SELECTION", "B_SHORT_GENERATION", "C_VERIFIED_STREAM_BLOCKS")}
    assert Counter((r["record_id"], r["architecture"]) for r in rows) == Counter(expected)
    calls = sorted((c for r in rows for c in r["provider_attempts"]), key=lambda c: c["call"])
    assert len(calls) == raw["external_provider_attempts"] <= 18
    assert [c["call"] for c in calls] == list(range(1, len(calls) + 1))
    assert all(c["attempt_index"] in (0, 1) for c in calls)
    assert sum(c["attempt_index"] > 0 for c in calls) <= 2
    assert all(c["attempt_index"] == 0 for c in calls if c["kind"] == "GENERATE_STREAM")
    for previous, current in zip(calls, calls[1:]):
        assert current["request_start_monotonic_seconds"] - previous["request_start_monotonic_seconds"] >= 9.98
        assert abs(current["inter_request_start_seconds"] - (current["request_start_monotonic_seconds"] - previous["request_start_monotonic_seconds"])) < 1e-6
    assert all(c["requests_in_rolling_minute"] <= 6 for c in calls)
    assert all(c["reserved_input_tokens_in_rolling_minute"] <= 12000 for c in calls)
    assert all(c.get("input_tokens", 0) <= c["reserved_input_tokens_estimate"] for c in calls)
    assert raw["successful_supported_responses"] == sum(r["route"] == "SUPPORTED" for r in rows)
    assert raw["pretrial_cooldown_seconds_excluded_from_turns"] >= 59.99
    for r in rows:
        assert r["waits_included_in_whole_turn_times"] is True
        attempts = r["provider_attempts"]
        gen = [c for c in attempts if c["kind"] != "VERIFY"]
        verify = [c for c in attempts if c["kind"] == "VERIFY"]
        expected_wait = sum(c["admission_wait_seconds"] for c in attempts + r["admission_failures"])
        assert abs(r["admission_wait_seconds_sum"] - expected_wait) < 1e-6
        assert abs(r["retry_backoff_seconds_sum"] - sum(c.get("retry_backoff_seconds", 0) for c in attempts)) < 1e-6
        assert r["retry_attempts"] == sum(c["attempt_index"] > 0 for c in attempts)
        assert abs(r["generation_provider_active_seconds_sum"] - sum(c["elapsed_seconds"] for c in gen)) < 1e-6
        assert abs(r["verification_seconds_sum"] - sum(c["elapsed_seconds"] for c in verify)) < 1e-6
        if gen:
            expected_wall = max(c["finished_at_seconds"] for c in gen) - r["generation_started_at_seconds"]
            assert abs(r["generation_stage_wall_seconds"] - expected_wall) < 1e-6
        merged = []
        for begin, end in sorted((c["started_at_seconds"], c["finished_at_seconds"]) for c in verify):
            if merged and begin <= merged[-1][1]: merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else: merged.append((begin, end))
        assert abs(r["verification_wall_seconds"] - sum(end-begin for begin,end in merged)) < 1e-6
        if r["route"] == "SUPPORTED":
            assert r["first_verified_output_seconds"] <= r["complete_response_seconds"]
            assert r["session_saved_before_first_delivery"] and r["citation_closure_complete"] and r["immutable_citations_valid"]
        else:
            assert r["route"] == "SYSTEM_ERROR" and r["complete_response_seconds"] is None
    fields = ("record_id", "architecture", "route", "controller_retrieval_assembly_seconds",
              "generation_stage_wall_seconds", "generation_provider_active_seconds_sum",
              "verification_wall_seconds", "verification_seconds_sum", "session_and_delivery_commit_seconds",
              "admission_wait_seconds_sum", "retry_backoff_seconds_sum", "retry_attempts",
              "first_verified_output_seconds", "complete_response_seconds", "failed_attempt_seconds",
              "failure_reason", "failure_class", "partial_verified_delivery_before_failure",
              "generation_verification_overlap_seconds", "delivered_blocks", "admission_failures")
    failures = [{"record_id": r["record_id"], "architecture": r["architecture"],
                 "route": r["route"], "failure_reason": r.get("failure_reason"),
                 "failed_attempt_seconds": r.get("failed_attempt_seconds"),
                 "partial_verified_delivery": r.get("partial_verified_delivery_before_failure", False),
                 "failed_requests": [{"call": c["call"], "kind": c["kind"],
                    "attempt_index": c["attempt_index"], "http_status": (c.get("transport") or {}).get("http_status"),
                    "failure_reason": c.get("failure_reason"), "failure_class": c.get("failure_class"),
                    "active_seconds": c["elapsed_seconds"], "retry_scheduled": c.get("retry_scheduled", False)}
                    for c in r["provider_attempts"] if "failure_class" in c],
                 "admission_failures": r["admission_failures"]}
                for r in rows if r["route"] != "SUPPORTED" or any("failure_class" in c for c in r["provider_attempts"]) or r["admission_failures"]]
    local_schema_failures = []
    for r in rows:
        for c in r["provider_attempts"]:
            diag = c.get("output_diagnostics", {})
            if c["kind"] == "VERIFY" and diag.get("unsupported_additions", {}).get("type") != "bool":
                local_schema_failures.append({"record_id": r["record_id"], "architecture": r["architecture"],
                    "call": c["call"], "http_status": (c.get("transport") or {}).get("http_status"),
                    "failure_reason": "OUTPUT_SCHEMA", "field": "unsupported_additions", "required_type": "bool",
                    "observed_type": diag.get("unsupported_additions", {}).get("type"),
                    "derived_from_redacted_output_diagnostics": True,
                    "technical_text_released": False})
    prior = []
    for old in ("38078598648", "38079224669"):
        old_path = Path("reports") / ("architecture_run_" + old) / "architecture_comparison.json"
        data = json.loads(old_path.read_text())
        prior.append({"run_id": old, "protocol": data["schema_version"], "raw_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
                      "provider_requests": data["external_provider_attempts"], "supported_responses": data["successful_supported_responses"],
                      "not_pooled_with_v3": True})
    return {"schema_version": "architecture-v3-result-audit-v1", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id, "source_report": str(path), "source_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "model": raw["model"], "audit_decision": "PASS_NINE_CELLS_ALL_ATTEMPTS_AND_ADMISSION_TIMINGS",
            "provider_requests": len(calls), "retry_attempts": sum(c["attempt_index"] > 0 for c in calls),
            "supported_responses": raw["successful_supported_responses"],
            "http_status_counts": dict(Counter(str((c.get("transport") or {}).get("http_status")) for c in calls)),
            "minimum_request_start_spacing_seconds": min((b["request_start_monotonic_seconds"]-a["request_start_monotonic_seconds"] for a,b in zip(calls,calls[1:])), default=None),
            "startup_seconds_excluded_from_turns": raw["startup_seconds_excluded_from_turns"],
            "pretrial_cooldown_seconds_excluded_from_turns": raw["pretrial_cooldown_seconds_excluded_from_turns"],
            "pacing_policy": raw["pacing_policy"], "rows": [{k:r.get(k) for k in fields} for r in rows],
            "all_failures_including_recovered_attempts": failures,
            "all_local_verifier_schema_failures_from_redacted_diagnostics": local_schema_failures,
            "prior_protocols_retained_separately": prior,
            "browser_latency_measured": False, "p95_established": False,
            "stage_semantics": "Generation wall includes admission/retries; provider active intervals exclude waits. Verification wall is active interval union. Wait sums can overlap for C and are not additive stage budgets.",
            "architectural_superiority_established": False, "same_model_semantic_verifier": True,
            "actual_account_numeric_quotas_verified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.report, args.run_id)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("audit_decision", "provider_requests", "retry_attempts", "supported_responses", "http_status_counts")}))
