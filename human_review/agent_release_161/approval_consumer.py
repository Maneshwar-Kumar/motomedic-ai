"""Offline consumer for exact-version owner-delegated agent release decisions.

No provider imports, key access, public source display or implicit session seeds.
This checks approved scopes and typed eligibility; it is not the deployed runner.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

RELEASE_SHA = "b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298"
MANUAL_SHA = "cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def object_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe_path(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), "Artifact path leaves project")
    return path


def predicate(rule, facts):
    """Do not coerce rider strings, bools/numbers, unknowns or unitless quantities."""
    key = rule["fact_key"]
    if key not in facts or facts[key] is None:
        return "UNKNOWN"
    got, expected = facts[key], rule["expected_value"]
    kind = rule["predicate_type"]
    if kind == "BOOLEAN":
        if type(got) is not bool or type(expected) is not bool:
            return "UNKNOWN"
    elif kind == "ENUM":
        if type(got) is not str or type(expected) is not str:
            return "UNKNOWN"
    elif kind == "NUMBER":
        if rule.get("unit"):
            if not isinstance(got, dict) or got.get("unit") != rule["unit"]:
                return "UNKNOWN"
            got = got.get("value")
        if type(got) not in (int, float) or not math.isfinite(got):
            return "UNKNOWN"
        if type(expected) not in (int, float) or not math.isfinite(expected):
            return "UNKNOWN"
    else:
        return "UNKNOWN"
    op = rule["operator"]
    operations = {"EQ": lambda: got == expected, "NE": lambda: got != expected,
                  "LT": lambda: got < expected, "LE": lambda: got <= expected,
                  "GT": lambda: got > expected, "GE": lambda: got >= expected}
    if op not in operations or (kind != "NUMBER" and op not in ("EQ", "NE")):
        return "UNKNOWN"
    return "TRUE" if operations[op]() else "FALSE"


class ApprovalConsumer:
    def __init__(self, root, manifest_path):
        self.root = Path(root).resolve()
        path = safe_path(self.root, manifest_path)
        manifest_raw = path.read_bytes()
        require(digest(manifest_raw) == RELEASE_SHA, "Release decision version changed")
        self.manifest = json.loads(manifest_raw)
        authority_path = self.root / "human_review/agent_release_161/owner_authority.json"
        self.authority_hash = digest(authority_path.read_bytes())
        authority = json.loads(authority_path.read_bytes())
        require(authority["human_signoff_required_for_this_workflow"] is False, "Authority policy mismatch")
        require(authority["release_coordinator"] == "/root/release_coordinator", "Wrong authority")
        require(digest((self.root / "royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf").read_bytes()) == MANUAL_SHA, "Actual manual changed")
        source_approval = self.manifest["source_manual_approval"]
        require(source_approval["decision"] == "APPROVED_AGENT_RELEASE" and source_approval["scope"] == "SOURCE_MANUAL_APPLICABILITY", "Selected manual lacks scoped coordinator approval")
        require(source_approval["authority_sha256"] == self.authority_hash and source_approval["manual_sha256"] == MANUAL_SHA, "Wrong source approval authority/manual")
        require(digest((self.root / "source_manifest.json").read_bytes()) == source_approval["source_manifest_sha256"], "Source metadata changed since approval")
        metadata_raw = safe_path(self.root, source_approval["checker_file"]).read_bytes()
        require(digest(metadata_raw) == source_approval["checker_file_sha256"], "Source metadata inspection changed")
        require(json.loads(metadata_raw)["verdict"] == "APPROVED_SELECTED_MANUAL_HIMALAYAN_BS6_SCOPE", "Independent metadata review did not pass")
        outputs = self.manifest["outputs"]
        require(outputs, "Missing approved artifacts")
        self.artifacts = {}
        for name, sha in outputs.items():
            raw = safe_path(self.root, name).read_bytes()
            require(digest(raw) == sha, "Changed approved artifact: " + name)
            if any(part.startswith("approved_package") for part in Path(name).parts) and name.endswith(".json"):
                basename = Path(name).name
                require(basename not in self.artifacts, "Conflicting package artifact basenames")
                self.artifacts[basename] = json.loads(raw)
        rows = self.manifest["records"]
        require(len(rows) == 161 and len({r["record_id"] for r in rows}) == 161, "All 161 unique decisions required")
        self.records = {r["record_id"]: r for r in rows}
        inventory_raw = (self.root / "human_review/agent_release_161/planner/plan_inventory.json").read_bytes()
        require(digest(inventory_raw) == "355d942b5eab39313e954e052419da3fa408cc7c4f9b18c08f5a359a0b84c154", "Changed dispatched inventory")
        expected_ids = {r["record_id"] for r in json.loads(inventory_raw)["records"]}
        require(set(self.records) == expected_ids, "Wrong 161 case identities")
        for r in rows:
            require(r["authority_sha256"] == self.authority_hash, "Decision authority hash mismatch")
            require(r.get("human_signoff") is not True, "Agent approval falsely represented as human signoff")
        self.registry = self.artifacts["candidate_registry.json"]
        self.sources = self.artifacts["source_objects.json"]["sources"]
        self.routes = {r["record_id"]: r for r in self.artifacts["trusted_routes.json"]["routes"]}
        self.contract = self.artifacts["execution_contract.json"]
        self.constraints = {r["record_id"]: r for r in self.artifacts["case_constraints.json"]["records"]}
        inventory_binding = self.manifest["checker_inventory"]
        final_raw = safe_path(self.root, inventory_binding["file"]).read_bytes()
        require(digest(final_raw) == inventory_binding["sha256"], "Changed final checker inventory")
        require(outputs.get(inventory_binding["file"]) == inventory_binding["sha256"], "Checker inventory is not release-bound")
        final_inventory = json.loads(final_raw)
        self.final_checks = {r["record_id"]: r for r in final_inventory["records"]}
        package_root = safe_path(self.root, self.manifest["approved_package"])
        for name, sha in final_inventory["package_outputs"].items():
            checked_path = safe_path(package_root, name)
            relative = checked_path.relative_to(self.root).as_posix()
            require(outputs.get(relative) == sha, "Final package differs from independent check")
        procedure_raw = (self.root / "human_review/agent_release_161/checker/procedure_review_v2.json").read_bytes()
        require(digest(procedure_raw) == "e7ac481ccf459789abd501fc75ae372b8af9aa2aa04c2c6f964caa74f1d15d4d", "Changed independent procedure checks")
        self.procedure_checks = {r["procedure_id"]: r for r in json.loads(procedure_raw)["records"]}
        self.check_bindings()

    def scope_ready(self, record_id, scope):
        row = self.records[record_id]
        return scope in row["approved_scopes"] and scope not in row["blocked_scopes"]

    def locate(self, locator):
        data = json.loads(safe_path(self.root, locator["file"]).read_bytes())
        key = locator.get("key")
        obj = None
        if isinstance(data, dict) and key in data:
            obj = data[key]
        elif isinstance(data, dict) and data.get("record_id") == key:
            obj = data
        else:
            groups = [data] if isinstance(data, list) else [data.get(k, {}) for k in ("records", "routes", "steps", "dependencies", "procedures")]
            for group in groups:
                if isinstance(group, dict) and key in group:
                    obj = group[key]
                    break
                if isinstance(group, list):
                    matches = [r for r in group if r.get("record_id") == key]
                    require(len(matches) <= 1, "Ambiguous object locator")
                    if matches:
                        obj = matches[0]
                        break
        require(obj is not None, "Object locator is missing")
        return obj[locator["field"]] if locator.get("field") else obj

    def source_closure(self, references, bound):
        require(set(references) <= set(bound), "Unbound source or policy reference")

    def check_bindings(self):
        for rid, row in self.records.items():
            require(row.get("human_signoff") is not True, "Agent review must not be labelled human")
            require(row["authority_sha256"] == self.authority_hash, "Changed coordinator authority")
            b = row["artifact_bindings"]
            fixture = self.locate(b["case_locator"])
            require(object_hash(fixture) == b["case_sha256"], rid + " changed session fixture")
            require(fixture["record_id"] == rid, "Wrong case fixture")
            proposal = self.locate(b["planner_case_locator"])
            require(object_hash(proposal) == b["planner_case_sha256"], rid + " changed canonical case")
            planner_raw = safe_path(self.root, b["planner_case_locator"]["file"]).read_bytes()
            require(digest(planner_raw) == row["planner_file_sha256"], "Planner artifact changed")
            report_path = row["checker_report_locator"]["file"]
            report_raw = safe_path(self.root, report_path).read_bytes()
            require(digest(report_raw) == row["checker_report_sha256"], "Independent checker report changed")
            check = self.locate(row["checker_report_locator"])
            require(check["record_id"] == rid, "Cross-case checker verdict")
            require(check.get("checker_actor") == "independent-source-checker", "Independent checker identity missing")
            if self.scope_ready(rid, "INITIAL_ROUTE"):
                final_check = self.final_checks[rid]
                require(final_check["final_check_verdict"] == "PASS_SCOPED_RELEASE" and final_check["sha256"] == row["checker_report_sha256"], "Initial scope lacks exact independent final pass")
                require(check.get("verdict") == "PASS_SCOPED_INITIAL_HANDLING", "Independent initial check did not pass")
                require(not check.get("structural_errors"), "Unresolved checker errors")
            answer = self.locate(b["canonical_answer_locator"])
            answer_sha = object_hash(answer) if isinstance(answer, (list, dict)) else digest(answer.encode("utf-8"))
            require(answer_sha == b["canonical_answer_sha256"], "Final canonical answer changed")
            require(self.routes[rid].get("step_id") == b.get("step_id"), "Evaluated step differs from approved step")
            if b.get("step_id"):
                step = self.registry["steps"][b["step_id"]]
                require(object_hash(step) == b["step_sha256"], rid + " changed approved step")
                require(step.get("canonical_record_id") == rid, "Cross-case step")
                require(check.get("final_step_sha256") == b["step_sha256"], "Checker did not inspect this step")
                dep = self.registry["dependencies"][b["dependency_id"]]
                require(object_hash(dep) == b["dependency_sha256"], rid + " changed dependencies")
                require(dep["step_id"] == b["step_id"] == b["dependency_id"], "Cross-case dependency identity")
                require(check.get("final_dependency_sha256") == b["dependency_sha256"], "Checker did not inspect these dependencies")
                self.source_closure(step.get("unresolved_evidence_ids", []) + step.get("next_step_evidence_ids", []), b["source_sha256s"])
                if step.get("parent_procedure_id"):
                    procedure = self.registry["procedures"][b["procedure_id"]]
                    require(b["procedure_id"] == step["parent_procedure_id"], "Wrong parent procedure")
                    require(object_hash(procedure) == b["procedure_sha256"], "Changed parent boundary")
                    require(row.get("procedure_boundary_approved") is True, "Unreviewed parent boundary")
                    attestation = self.procedure_checks[b["procedure_id"]]
                    require(attestation["procedure_sha256"] == b["procedure_sha256"] and attestation["verdict"] == "APPROVED_INITIAL_ACTION_BOUNDARY" and attestation["record_id"] == rid, "Unbound independent procedure review")
                    self.source_closure(procedure.get("evidence_ids", []), b["source_sha256s"])
                require(not step.get("next_step_ids"), "This terminal consumer cannot execute adaptive edges")
                require(set(step["required_evidence_ids"]) == set(dep["required_evidence_ids"]), "Incomplete step dependencies")
                require(set(step["required_evidence_ids"]) <= set(b["source_sha256s"]), "Unbound mandatory source")
                for claim in step.get("claims", []):
                    refs = claim.get("evidence_ids", []) + claim.get("policy_support_ids", [])
                    require(refs and set(refs) <= set(b["source_sha256s"]), "Unbound answer claim")
                    for span in claim.get("source_spans", []):
                        source = self.sources[span["evidence_id"]]
                        text = source.get("exact_text", "")
                        require(span.get("text_sha256") == digest(text.encode("utf-8")), "Changed claim source span text")
                        extent = span.get("text_span")
                        require(extent and len(extent) == 2 and 0 <= extent[0] <= extent[1] <= len(text), "Claim span outside source")
                rule_ids = set(step.get("applicability_rule_ids", []) + step.get("safety_rule_ids", []) + step.get("repeat_rule_ids", []))
                require(rule_ids <= set(b["rule_sha256s"]), "Unbound eligibility/safety rule")
                if step["kind"] == "SAFETY_STOP":
                    require(self.routes[rid]["initial_candidate_route"] == "SAFETY_STOP", "Safety stop downgraded")
            for rule_id, sha in b["rule_sha256s"].items():
                rule = self.registry["rules"][rule_id]
                require(object_hash(rule) == sha, "Changed approved predicate")
                refs = rule.get("source_evidence_ids", []) + rule.get("policy_source_ids", []) + rule.get("clarification_evidence_ids", [])
                self.source_closure(refs, b["source_sha256s"])
            for source_id, sha in b["source_sha256s"].items():
                require(object_hash(self.sources[source_id]) == sha, "Changed approved source")
                source = self.sources[source_id]
                if source.get("authority") == "OEM_MANUAL":
                    require(source.get("manual_sha256", "").lower() == MANUAL_SHA, "Wrong manual source")
            route = self.routes[b["route_id"]]
            require(object_hash(route) == b["route_sha256"], "Changed approved route")
            require(route["record_id"] == rid, "Cross-case route")
            require(object_hash(self.constraints[b["constraint_id"]]) == b["constraint_sha256"], "Changed initial/eligible route constraints")
            require(self.constraints[rid]["initial_route"] == row["initial_route"], "Wrong initial route")
            require(self.constraints[rid]["eligible_main_route"] == row["eligible_main_route"], "Wrong eligible main route")
            require(check.get("final_route_sha256") == b["route_sha256"], "Checker did not inspect this route")
            self.source_closure(route.get("source_ids", []) + route.get("policy_source_ids", []) + route.get("source_support_ids", []), b["source_sha256s"])
        require(self.contract["provider_calls_authorized"] is False, "This consumer does not authorize inference")
        require(self.contract["deployment_authorized"] is False, "Unexpected deployment grant")
        return {"records": len(self.records), "file_hashes_verified": True,
                "case_source_step_rule_dependency_bindings_verified": True,
                "manual_verified": True, "human_review_required": False,
                "provider_calls": 0, "deployed_runner_changed": False}

    def eligibility(self, record_id, facts, attempts=None):
        row = self.records[record_id]
        if not self.scope_ready(record_id, "INITIAL_ROUTE"):
            return {"eligibility": "FALSE", "reason": "Initial route lacks scoped coordinator approval"}
        route = self.routes[record_id]
        sid = route.get("step_id")
        if not sid:
            return {"eligibility": "UNKNOWN", "reason": "Policy route requires its separately reviewed trusted execution contract"}
        step = self.registry["steps"][sid]
        if step.get("safety_rule_ids"):
            return {"eligibility": "UNKNOWN", "reason": "Requires separately executed safety precedence; never authorize ordinary action here"}
        if step["kind"] == "ACTION":
            if attempts is None:
                return {"eligibility": "UNKNOWN", "reason": "Trusted typed attempt history required"}
            if any(a.get("step_id") == sid for a in attempts):
                return {"eligibility": "FALSE", "reason": "This terminal package authorizes no automatic repeat"}
        if step.get("repeat_rule_ids"):
            return {"eligibility": "UNKNOWN", "reason": "Repeat permission is outside this terminal consumer"}
        rules = step.get("applicability_rule_ids", [])
        results = {rid: predicate(self.registry["rules"][rid], facts) for rid in rules}
        verdict = "FALSE" if "FALSE" in results.values() else "UNKNOWN" if "UNKNOWN" in results.values() else "TRUE"
        return {"eligibility": verdict, "rule_results": results,
                "scope": "INITIAL_ROUTE", "automatic_follow_up_authorized": False,
                "provider_execution_authorized_by_this_consumer": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--manifest", default="human_review/agent_release_161/coordinator/release_manifest_v3.json")
    args = p.parse_args()
    consumer = ApprovalConsumer(args.root, args.manifest)
    print(json.dumps(consumer.check_bindings(), indent=2))


if __name__ == "__main__":
    main()
