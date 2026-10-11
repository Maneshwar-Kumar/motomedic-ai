"""Draft-only registry authoring and independent, content-bound review workflow."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from evidence_registry import EvidenceRegistry, SCHEMA_VERSION, content_hash, read_json

LOOKUPS = {"oil_grade": "G013", "tyre_pressure": "G014", "fan_fuse": "G016",
           "starter_duration": "G019", "usb_charging": "G020"}
ACTION_RULES = {"a_switches_on": ("q_switches", False), "a_refuel": ("q_fuel", True),
                "a_fuse": ("q_fuse", True), "a_reconnect": ("q_spark_connection", True),
                "a_raise_stand": ("q_side_stand_indicator", True), "a_cool_engine": ("q_engine_hot", True)}
ACTION_TAGS = {"a_switches_on": "no_start", "a_refuel": "no_start", "a_fuse": "no_start",
               "a_reconnect": "no_start", "a_raise_stand": "first_gear_stall", "a_cool_engine": "misfire"}


def write(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def propose(index, destination):
    index, destination = Path(index), Path(destination)
    manifest = read_json(index / "manifest.json")
    checksum = manifest["source_sha256"]
    if manifest["index_id"] != "index_a3282c4d98cf54595e4ba168":
        raise ValueError("Use the selected immutable hosted index")
    flow, cards = read_json("diagnosis_flow.json"), read_json("golden_qa.json")
    if any(obj["source_sha256"].lower() != checksum.lower() for obj in (flow, cards)):
        raise ValueError("Candidate sources differ from index checksum")
    evidence = {e["id"]: e for e in (json.loads(line) for line in (index / "evidence.jsonl").read_text(encoding="utf-8").splitlines())}
    def objects(pages):
        return sorted(eid for eid, e in evidence.items() if any(p.get("page_no", p.get("pdf_page")) in pages for p in e["provenance"]))
    c = {"schema_version": SCHEMA_VERSION, "version": "candidate-steps-v1", "manual_checksum": checksum,
         "index_id": manifest["index_id"], "authored_by": "motomedic-candidate-importer",
         "steps": {}, "rules": {}, "dependencies": {}, "procedures": {},
         "limits": "All imported text, page-scoped dependencies and conditions are DRAFT. Author precise source boundaries, warning/prerequisite scope and claims before independent review."}
    def add_step(sid, pages, text, tags, kind, rules):
        ids = objects(pages)
        action_ids = [eid for eid in ids if evidence[eid]["type"] in ("table", "text", "list_item")]
        parent = "procedure_" + sid if kind == "ACTION" else None
        if parent:
            c["procedures"][parent] = {"procedure_id": parent, "type": "PROCEDURE", "manual_checksum": checksum,
                                      "evidence_ids": ids, "boundaries_checked": False, "review_status": "DRAFT"}
        c["steps"][sid] = {"step_id": sid, "manual_checksum": checksum, "action_evidence_ids": action_ids,
                           "parent_procedure_id": parent, "symptom_tags": tags, "applicability_rule_ids": rules,
                           "required_evidence_ids": ids, "dependency_manifest_version": "dependencies-v1",
                           "review_status": "DRAFT", "rule_version": "rules-v1", "kind": kind,
                           "safety_rule_ids": [], "next_step_ids": [], "next_step_evidence_ids": [], "repeat_rule_ids": [],
                           "claims": [{"claim_id": sid + ":draft", "text": text, "evidence_ids": action_ids}],
                           "draft_pdf_pages": pages, "authoring_required": ["Claim spans", "Mandatory warnings and prerequisites", "Variant fit", "Source-derived question/condition", "No inferred OEM order"]}
        c["dependencies"][sid] = {"step_id": sid, "version": "dependencies-v1", "manual_checksum": checksum,
                                  "index_id": manifest["index_id"], "action_evidence_ids": action_ids, "required_evidence_ids": ids,
                                  "review_status": "DRAFT", "scope_review_complete": False,
                                  "categories": {"unclassified_required_context": ids}}
    for sid, (qid, expected) in ACTION_RULES.items():
        node, question = flow["nodes"][sid], flow["nodes"][qid]
        rid = "rule_" + qid
        ids = objects([int(p[1:]) for p in question["source_pages"]])
        c["rules"][rid] = {"rule_id": rid, "predicate_type": "BOOLEAN", "fact_key": qid,
                           "operator": "EQ", "expected_value": expected, "unit": None, "origin": "MANUAL",
                           "source_evidence_ids": ids, "policy_version": None, "clarification_evidence_ids": ids,
                           "review_status": "DRAFT", "rule_version": "rules-v1", "rider_resolvable": True,
                           "clarification_question": question["text"]}
        add_step(sid, [int(p[1:]) for p in node["source_pages"]], node["text"], [ACTION_TAGS[sid]], "ACTION", [rid])
    by = {card["id"]: card for card in cards["cases"]}
    for intent, cid in LOOKUPS.items():
        card = by[cid]
        add_step("lookup_" + intent, [p["pdf_page"] for p in card["citations"]], card["gold_answer"], [intent], "LOOKUP", [])
    from registry_source_candidates import refine
    c = refine(c, evidence)
    # Never overwrite an authored registry or review ledger on a subsequent proposal run.
    target = destination / "candidate_registry.json"
    if target.exists():
        raise ValueError("Destination exists; propose a new version/directory instead")
    write(target, c)
    write(destination / "review_decisions.json", {"schema_version": "review-ledger-v1", "decisions": []})
    return c


CHECKS = {
    "source": ["edition_variant_fit", "source_url_checked", "market_confirmed"],
    "evidence": ["original_page_compared", "extraction_complete", "table_units_and_headers", "figure_context", "warning_text_complete"],
    "procedure": ["original_page_compared", "boundaries_and_order"],
    "step": ["original_page_compared", "every_claim_supported", "warning_and_prerequisite_scope", "no_inferred_diagnosis_or_order"],
    "rule": ["original_page_compared", "predicate_supported", "question_rider_resolvable"],
    "dependency": ["original_page_compared", "all_mandatory_objects", "table_figure_warning_scope"]}


def review(registry, decision):
    kind, target_id = decision["target_kind"], decision["target_id"]
    target = registry.target(kind, target_id)
    if decision["decision"] not in ("APPROVED", "REJECTED", "STALE"):
        raise ValueError("Invalid decision")
    if decision["target_digest"] != content_hash(target):
        raise ValueError("Target changed since review packet export")
    if decision.get("reviewer") == target.get("authored_by", registry.candidate.get("authored_by")):
        raise ValueError("Author cannot independently approve their own records")
    if not decision.get("reviewer") or not decision.get("notes"):
        raise ValueError("Reviewer identity and notes required")
    if decision["decision"] == "APPROVED":
        if decision.get("human_signoff") is not True or decision.get("independent_original_page_review") is not True or not decision.get("checked_source_spans"):
            raise ValueError("Independent original-page review required")
        if not all(decision.get("checks", {}).get(k) is True for k in CHECKS[kind]):
            raise ValueError("Complete review checklist required; record not-applicable explanations in notes")
        if kind == "step" and target.get("authoring_blockers"):
            raise ValueError("Resolve authoring blockers before reviewing the final step digest")
        if kind == "source" and not all(target.get(k) for k in ("edition", "variant", "source_uri")):
            raise ValueError("Confirm source metadata before approval")
        if kind == "procedure" and target.get("boundaries_checked") is not True:
            raise ValueError("Author procedure boundaries before approval")
        if kind == "dependency" and (target.get("scope_review_complete") is not True or not target.get("required_evidence_ids")):
            raise ValueError("Author a complete dependency scope before approval")
    stamped = {**decision, "timestamp": datetime.now(timezone.utc).isoformat(),
               "manual_checksum": registry.checksum, "index_id": registry.index_id, "registry_version": registry.version}
    return {**registry.reviews, "decisions": registry.reviews.get("decisions", []) + [stamped]}


def packet(registry, kind, target_id):
    target = registry.target(kind, target_id)
    ids = target.get("required_evidence_ids", target.get("evidence_ids", target.get("source_evidence_ids", [])))
    if kind == "evidence":
        ids = [target_id]
    return {"target_kind": kind, "target_id": target_id, "target_digest": content_hash(target),
            "target": target, "source_file": registry.source["file"], "manual_checksum": registry.checksum,
            "index_id": registry.index_id, "registry_version": registry.version,
            "original_page_objects": [{"evidence_id": eid, "provenance": registry.evidence[eid]["provenance"],
                                       "raw_object": registry.evidence[eid].get("raw_object")} for eid in ids],
            "decision_template": {"target_kind": kind, "target_id": target_id, "target_digest": content_hash(target),
                                  "reviewer": "", "decision": "REJECTED", "notes": "", "checked_source_spans": [],
                                  "independent_original_page_review": False, "human_signoff": False, "checks": {k: False for k in CHECKS[kind]}}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("propose", "validate", "packet", "record"))
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--registry", type=Path, default=Path("registry"))
    p.add_argument("--source", type=Path, default=Path("source_manifest.json"))
    p.add_argument("--kind", choices=tuple(CHECKS))
    p.add_argument("--id")
    p.add_argument("--decision", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.command == "propose":
        c = propose(args.index, args.registry)
        print(json.dumps({"draft_steps": len(c["steps"]), "version": c["version"]}))
        return
    r = EvidenceRegistry.load(args.registry, args.index, args.source)
    if args.command == "validate":
        print(json.dumps({"registry_version": r.version, "lock": r.lock, "source_ready": r.source_ready(),
                          "approved_steps": [sid for sid in r.candidate["steps"] if r.step_ready(sid)], "release_approved": False}))
    elif args.command == "packet":
        if not args.kind or not args.id or not args.output:
            p.error("packet requires --kind, --id and --output")
        write(args.output, packet(r, args.kind, args.id))
    else:
        if not args.decision:
            p.error("record requires --decision")
        write(args.registry / "review_decisions.json", review(r, read_json(args.decision)))


if __name__ == "__main__":
    main()
