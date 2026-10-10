from pathlib import Path as _ReleasePath
if (_ReleasePath(__file__).resolve().parent / "release_manifest.json").exists():
    raise RuntimeError("Approved package immutable: create a new version for revisions")
"""Build a constrained, isolated package; release decisions are written separately."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshot_v3"
OUT = HERE / "approved_package"

def load(name):
    return json.loads((SNAP / name).read_text(encoding="utf-8"))

def save(name, data):
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (OUT / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()

def build():
    OUT.mkdir(exist_ok=True)
    registry = load("candidate_registry.json")
    routes = load("trusted_routes.json")
    branches = load("branch_dependencies.json")
    corrections = []
    for step_id, step in registry["steps"].items():
        previous = step.get("unresolved_route")
        step["unresolved_route"] = "ESCALATE_NO_APPROVED_NEXT_STEP"
        step["next_step_ids"] = []
        step["next_step_evidence_ids"] = []
        step["repeat_rule_ids"] = []
        step["runtime_authorized"] = False
        step["approval_required_scopes"] = ["SOURCE_CONTENT", "INITIAL_ROUTE"]
        step["adaptive_continuation_authorized"] = False
        corrections.append({"step_id":step_id,"previous_unresolved_route":previous,
                            "new_unresolved_route":step["unresolved_route"],
                            "reason":"No executable, independently verified next-step edges exist in this snapshot."})
    for branch in branches["branches"]:
        branch["runtime_authorized"] = False
        branch["execution_scope"] = "REFERENCE_TEXT_ONLY_NOT_EXECUTABLE_BRANCH"
    registry["release_authority"] = "AGENT_COORDINATOR"
    registry["runtime_authorized"] = False
    routes["runtime_authorized"] = False
    for route in routes["routes"]:
        route["release_authority"] = "AGENT_COORDINATOR"
        route["runtime_authorized"] = False
        route.pop("requires_actual_formal_approval", None)
        route["requires_exact_scope_approval"] = True
    contract = {
        "schema_version":"agent-approved-scoped-execution-contract-v1",
        "authority":"AGENT_COORDINATOR", "approval_consumer_required":True,
        "source_checksum":registry["manual_checksum"],
        "case_selection":"Exact case ID plus confirmed case intent; synthetic fixtures are not live intent classifiers.",
        "initial_rule_evaluation":"TRUE/FALSE/UNKNOWN; every required predicate must be TRUE; false blocks action; unknown permits one source-derived clarification only when reviewed question exists.",
        "unknown_without_reviewed_question":"Withhold action; report ambiguous applicability or system/source gap according to cause.",
        "dependency_evaluation":"Exact approved source and dependency hashes; all mandatory objects present; warning/units/context retained.",
        "attempts":"Immutable typed attempts; ACTION_COMPLETED_UNRESOLVED never implies OBSERVED_NORMAL; corrections supersede rather than delete.",
        "repeat":"No automatic repeat; no adaptive next step authorized by this package.",
        "follow_up":"Keep separate unresolved issues; on unresolved/normal/abnormal outcome with no approved edge, refer to authorised service without claiming OEM diagnostic order.",
        "resolved":"Record rider-reported symptom resolution only; retain mandatory service warnings and other open issues.",
        "figures":"No end-user PDF, excerpt or figure display under this package; figure-dependent spatial instructions require separately bound verified visual evidence and applicable display permission.",
        "safety":"Known approved safety stop retains warning and precedes model or retrieval failure.",
        "provider":"No provider construction/key access/live model calls authorized by this package alone.",
        "deployment_authorized":False,
        "case_approval_required":True,
    }
    outputs = {}
    for name, data in [("candidate_registry.json",registry),("trusted_routes.json",routes),
                       ("branch_dependencies.json",branches),("source_objects.json",load("source_objects.json")),
                       ("execution_contract.json",contract),("corrections.json",corrections)]:
        outputs[name] = save(name,data)
    save("package_manifest.json",{"schema_version":"isolated-agent-scope-package-v1","outputs":outputs,
                                   "approval_status":"AWAITING_INDEPENDENT_FINAL_CHECK"})
    print(json.dumps(outputs,indent=2))

if __name__ == "__main__":
    build()
