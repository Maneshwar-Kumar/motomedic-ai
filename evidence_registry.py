"""Content-bound independent reviews layered over an immutable hosted index."""
from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from pathlib import Path

from controller_contracts import ApplicabilityRule, DependencyManifest, StepDefinition

SCHEMA_VERSION = "reviewed-registry-v1"
POLICY_VERSION = "controller-trd04-v1"
REVIEW_CHECKS = {
    "source": ("edition_variant_fit", "source_url_checked", "market_confirmed"),
    "evidence": ("original_page_compared", "extraction_complete", "table_units_and_headers", "figure_context", "warning_text_complete"),
    "procedure": ("original_page_compared", "boundaries_and_order"),
    "step": ("original_page_compared", "every_claim_supported", "warning_and_prerequisite_scope", "no_inferred_diagnosis_or_order"),
    "rule": ("original_page_compared", "predicate_supported", "question_rider_resolvable"),
    "dependency": ("original_page_compared", "all_mandatory_objects", "table_figure_warning_scope")}



def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def record(cls, raw):
    names = {f.name for f in fields(cls)}
    values = {k: v for k, v in raw.items() if k in names}
    for k in names:
        if k.endswith("_ids") or k in ("symptom_tags", "claims"):
            if k in values:
                values[k] = tuple(values[k])
    return cls(**values)


class EvidenceRegistry:
    """Trusted server-side registry. Rider/model input cannot supply review records.

    Review authenticity relies on private-repository access controls and code review.
    Content hashes prevent stale decisions; they are not digital signatures.
    """
    def __init__(self, candidate, reviews, evidence, source):
        if candidate.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported registry schema")
        self.candidate, self.reviews, self.source = candidate, reviews, source
        self.evidence = evidence
        self.checksum = candidate["manual_checksum"]
        self.index_id = candidate["index_id"]
        self.version = candidate["version"]
        self.refresh_lock()
        self.validate()

    def refresh_lock(self):
        # Policy/code updates invalidate paths without rebuilding document vectors.
        names = ("controller_contracts.py", "evidence_registry.py", "reviewed_controller.py",
                 "retrieval_policy.py", "online_retrieve.py", "reviewed_cache.py",
                 "generation_contracts.py", "generation_providers.py", "gemini_transport.py", "constrained_generator.py")
        root = Path(__file__).parent
        code = {name: hashlib.sha256((root / name).read_text(encoding="utf-8-sig").encode()).hexdigest()
                for name in names}
        self.lock = content_hash([self.candidate, self.reviews, self.source, POLICY_VERSION, code])

    @classmethod
    def load(cls, root, index_dir, source_path):
        root, index = Path(root), Path(index_dir)
        manifest = read_json(index / "manifest.json")
        candidate = read_json(root / "candidate_registry.json")
        if (manifest["index_id"] != candidate["index_id"] or
                manifest["source_sha256"].lower() != candidate["manual_checksum"].lower()):
            raise ValueError("Registry/index mismatch")
        evidence = {x["id"]: x for x in
                    (json.loads(line) for line in (index / "evidence.jsonl").read_text(encoding="utf-8").splitlines() if line)}
        return cls(candidate, read_json(root / "review_decisions.json"), evidence, read_json(source_path))

    def target(self, kind, target_id):
        if kind == "source":
            return self.source
        if kind == "evidence":
            return self.evidence[target_id]
        return self.candidate[{"step": "steps", "rule": "rules", "dependency": "dependencies", "procedure": "procedures"}[kind]][target_id]

    def approved(self, kind, target_id):
        target = self.target(kind, target_id)
        decisions = [d for d in self.reviews.get("decisions", [])
                     if d.get("target_kind") == kind and d.get("target_id") == target_id]
        if not decisions:
            return False
        decision = decisions[-1]
        author = target.get("authored_by", self.candidate.get("authored_by"))
        return bool(decision.get("decision") == "APPROVED" and
                    decision.get("independent_original_page_review") is True and
                    decision.get("human_signoff") is True and
                    decision.get("reviewer") and decision["reviewer"] != author and
                    decision.get("target_digest") == content_hash(target) and
                    decision.get("manual_checksum") == self.checksum and
                    decision.get("index_id") == self.index_id and
                    decision.get("registry_version") == self.version and
                    decision.get("checked_source_spans") and decision.get("timestamp") and
                    decision.get("notes") and
                    all(decision.get("checks", {}).get(k) is True for k in REVIEW_CHECKS[kind]))

    def validate(self):
        c = self.candidate
        if self.source["sha256"].lower() != self.checksum.lower():
            raise ValueError("Source checksum mismatch")
        for key in ("steps", "rules", "dependencies", "procedures"):
            if not isinstance(c.get(key), dict):
                raise ValueError("Missing registry contract")
        for sid, raw in c["steps"].items():
            step = record(StepDefinition, raw)
            if step.step_id != sid or step.manual_checksum != self.checksum:
                raise ValueError("Invalid step identity")
            if step.kind not in ("ACTION", "LOOKUP", "SAFETY_STOP"):
                raise ValueError("Invalid step kind")
            if not set(step.applicability_rule_ids + step.safety_rule_ids + step.repeat_rule_ids) <= c["rules"].keys():
                raise ValueError("Unresolved rule reference")
            dep = record(DependencyManifest, c["dependencies"][sid])
            if (dep.step_id != sid or dep.version != step.dependency_manifest_version or
                    dep.manual_checksum != self.checksum or dep.index_id != self.index_id or
                    set(dep.required_evidence_ids) != set(step.required_evidence_ids) or
                    set(dep.action_evidence_ids) != set(step.action_evidence_ids)):
                raise ValueError("Dependency/step mismatch")
            if len(set(dep.required_evidence_ids)) > 256:
                raise ValueError("Dependency work bound exceeded")
            referenced = set(dep.required_evidence_ids + step.next_step_evidence_ids + step.unresolved_evidence_ids)
            if not referenced <= self.evidence.keys():
                raise ValueError("Dependency references missing index objects")
            if not set(step.next_step_ids) <= c["steps"].keys():
                raise ValueError("Unresolved NEXT_STEP reference")
            if step.unresolved_route not in ("CONTINUE_DOCUMENTED", "ESCALATE") or (step.unresolved_route == "ESCALATE" and not step.unresolved_evidence_ids):
                raise ValueError("Unresolved route requires source evidence")
            if step.next_step_ids and not step.next_step_evidence_ids:
                raise ValueError("OEM order requires source evidence")
            if not set(step.action_evidence_ids) <= set(step.required_evidence_ids):
                raise ValueError("Action absent from dependency set")
            if step.parent_procedure_id and step.parent_procedure_id not in c["procedures"]:
                raise ValueError("Unresolved parent procedure")
            for category, ids in dep.categories.items():
                if not set(ids) <= set(dep.required_evidence_ids):
                    raise ValueError("Dependency category outside required set")
        for pid, procedure in c["procedures"].items():
            if (procedure.get("procedure_id") != pid or procedure.get("manual_checksum") != self.checksum or
                    not set(procedure.get("evidence_ids", [])) <= self.evidence.keys()):
                raise ValueError("Invalid procedure provenance")
        for rid, raw in c["rules"].items():
            rule = record(ApplicabilityRule, raw)
            if (rule.rule_id != rid or rule.predicate_type not in ("BOOLEAN", "ENUM", "NUMBER") or
                    rule.operator not in ("EQ", "NE", "LT", "LE", "GT", "GE")):
                raise ValueError("Non-allowlisted predicate")
            if rule.origin == "MANUAL":
                if not rule.source_evidence_ids:
                    raise ValueError("Manual rule has no evidence")
            elif rule.origin != "PRODUCT_POLICY" or not rule.policy_version:
                raise ValueError("Rule has no valid origin")
            if not set(rule.source_evidence_ids + rule.clarification_evidence_ids) <= self.evidence.keys():
                raise ValueError("Rule references unknown evidence")
            if rule.rider_resolvable and (not rule.clarification_question or not rule.clarification_evidence_ids):
                raise ValueError("Clarification has no source")

    def source_ready(self):
        required = ("manual_id", "motorcycle", "variant", "edition", "language", "source_uri")
        if self.source.get("applicability_policy", {}).get("version") != "owner-himalayan-bs6-v1":
            required += ("model_year", "market_or_region")
        return (all(self.source.get(k) for k in required) and
                self.approved("source", self.source["manual_id"]))

    def evidence_ready(self, eid):
        e = self.evidence.get(eid, {})
        return bool(e.get("source_sha256", "").lower() == self.checksum.lower() and
                    e.get("provenance") and self.approved("evidence", eid))

    def step(self, sid):
        raw = dict(self.candidate["steps"][sid])
        raw["review_status"] = "APPROVED" if self.approved("step", sid) else "DRAFT"
        return record(StepDefinition, raw)

    def rule(self, rid):
        raw = dict(self.candidate["rules"][rid])
        raw["review_status"] = "APPROVED" if self.approved("rule", rid) else "DRAFT"
        return record(ApplicabilityRule, raw)

    def step_ready(self, sid):
        if self.candidate["steps"][sid].get("authoring_blockers"):
            return False
        s = self.step(sid)
        dep = self.candidate["dependencies"][sid]
        # Missing/empty manifests and contextual parents cannot establish sufficiency.
        return bool(s.review_status == "APPROVED" and self.approved("dependency", sid) and
                    s.action_evidence_ids and s.required_evidence_ids and
                    (s.kind != "ACTION" or (s.parent_procedure_id and self.approved("procedure", s.parent_procedure_id) and
                     self.candidate["procedures"][s.parent_procedure_id].get("boundaries_checked") is True and
                     set(self.candidate["procedures"][s.parent_procedure_id]["evidence_ids"]) <= set(s.required_evidence_ids))) and
                    dep.get("scope_review_complete") is True and
                    not dep.get("categories", {}).get("unclassified_required_context") and
                    all(self.evidence_ready(eid) for eid in s.required_evidence_ids) and
                    all(self.rule(rid).review_status == "APPROVED" and
                        set(self.rule(rid).source_evidence_ids) <= set(s.required_evidence_ids) and
                        all(self.evidence_ready(eid) for eid in self.rule(rid).source_evidence_ids + self.rule(rid).clarification_evidence_ids)
                        for rid in s.applicability_rule_ids + s.safety_rule_ids + s.repeat_rule_ids) and
                    all(self.evidence_ready(eid) and eid in s.required_evidence_ids for eid in s.next_step_evidence_ids + s.unresolved_evidence_ids))

    def retrieval_manifest(self, sid):
        s = self.step(sid)
        status = "APPROVED" if self.step_ready(sid) else "DRAFT"
        return {"manual_checksum": self.checksum, "version": s.dependency_manifest_version,
                "review_status": status, "steps": {sid: {
                    "review_status": status, "action_evidence_ids": list(s.action_evidence_ids),
                    "required_evidence_ids": list(s.required_evidence_ids)}}}

    def reviewed_evidence(self):
        # Overlay only: never rewrite evidence.jsonl or its index checksum.
        return {eid: {**e, "review_status": "APPROVED" if self.evidence_ready(eid) else "UNREVIEWED",
                      "extraction_check_status": "PASSED" if self.evidence_ready(eid) else "PENDING"}
                for eid, e in self.evidence.items()}

    def evidence_view(self, index_id, evidence_id, *, audience="end_user"):
        if index_id != self.index_id:
            raise ValueError("Evidence/index mismatch")
        if audience == "end_user" and self.source.get("display_policy", {}).get("end_user_excerpts") is not True:
            raise PermissionError("End-user source display prohibited")
        if audience not in ("engineering", "end_user"):
            raise ValueError("Invalid audience")
        return self.evidence[evidence_id]

    def support_uri(self):
        route = self.source.get("oem_service_route")
        if (isinstance(route, dict) and route.get("verified") is True and
                route.get("checked_date") and (route.get("owner_requested") is True or route.get("market") == self.source["market_or_region"]) and
                (str(route.get("url", "")).startswith("https://") or
                 route.get("url") == "mailto:support@royalenfield.com")):
            return route["url"]
        return None
