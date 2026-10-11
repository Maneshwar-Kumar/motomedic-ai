"""Read-only canonical navigation and retained-source/runtime integrity audit.

Uses only the standard library. Frozen historical report links are deliberately
not traversed: their older inputs remain available at the recorded Git revision.
Passing this audit is not factual, provider, deployment or release acceptance.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MANUAL = "royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf"
MANUAL_SHA = "cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89"
FREEZE = "reports/grounded_generation/v8/runtime_freeze.json"
FREEZE_SHA = "d7990e2fc2863c05f9c4332d4a2df76354be6fbfe49c2430bbbc7f83990c70e0"
HISTORICAL_RUNTIME = "reports/build/20261012/frozen_v8_runtime"
CURRENT_FREEZE = "reports/public_evaluator/20261012/serving_manifest_v10_2.json"
RELEASE = "human_review/agent_release_161/coordinator/release_manifest_v3.json"
RELEASE_SHA = "b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298"

NAVIGATION = (
    "README.md", "AGENTS.md", "CONTRIBUTING.md", "TODO.md",
    "docs/START_HERE.md", "docs/STATUS.md", "docs/PRD.md", "docs/TRD.md",
    "docs/ARCHITECTURE.md", "cloud/README.md", "rider_ui/README.md",
    "reports/README.md", "reports/reset/20261011/README.md",
)
CRITICAL = (
    MANUAL, "source_manifest.json", FREEZE, RELEASE,
    "human_review/agent_release_161/owner_authority.json",
    "human_review/agent_release_161/approval_consumer.py",
    "human_review/agent_release_161/test_approval_consumer.py",
    "human_review/agent_release_161/root_validation_v3.json",
    "cloud/deployment_status.json", "cloud/live_smoke.json", CURRENT_FREEZE,
    "reports/build/20261012/v8_preservation.json",
    "reports/build/20261012/serving_manifest_v9.json",
    "reports/build/20261012/serving_manifest_v9_1.json",
    "reports/public_evaluator/20261012/owner_scope_v1.json",
)
# Root runtime paths are compatibility inputs, not a template for new files.
ROOT_FILES = frozenset("""
.gitattributes .gitignore .dockerignore README.md AGENTS.md CONTRIBUTING.md TODO.md
approved_registry.py approved_runner.py approved_text_journeys.py
constrained_generator.py controller_contracts.py diagnose.py diagnosis_flow.json
evidence_registry.py gemini_transport.py generation_contracts.py
generation_providers.py golden_dialogues.json golden_dialogues.md golden_qa.json
golden_qa.md index_manual.py online_ingest.py online_retrieve.py
provisional_golden_cache.json registry_source_candidates.py registry_workflow.py
requirements-ingest.txt retrieval_policy.py retrieve_evidence.py reviewed_cache.py
reviewed_controller.py reviewed_graph_links.json session_store.py source_manifest.json
source_review_notes.json test_approved_integration.py test_budget_guard.py
test_conditional_retrieval.py test_constrained_generator.py test_diagnose.py
test_gemini_provider.py test_gemini_transport_bytes.py test_online_assembly.py
test_retrieve_evidence.py test_reviewed_controller.py test_text_journeys.py
verify_controller.py
""".split()) | {MANUAL}


def digest(path):
    with path.open("rb") as source:
        checksum = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def audit():
    actual = {path.name for path in ROOT.iterdir() if path.is_file()}
    missing = []
    broken = []
    integrity = []
    checked = 0
    for relative in NAVIGATION:
        page = ROOT / relative
        if not page.is_file():
            missing.append(relative)
            continue
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", page.read_text(encoding="utf-8-sig")):
            target = target.strip().strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            link = unquote(target.split("#", 1)[0])
            if not link:
                continue
            checked += 1
            resolved = (page.parent / link).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                broken.append({"page": relative, "target": target})

    missing_critical = [relative for relative in CRITICAL if not (ROOT / relative).is_file()]
    if (ROOT / MANUAL).is_file() and digest(ROOT / MANUAL) != MANUAL_SHA:
        integrity.append({"path": MANUAL, "reason": "MANUAL_SHA256_MISMATCH"})

    runtime_count = 0
    approved_count = 0
    for relative, expected, field, required_count in (
        (FREEZE, FREEZE_SHA, "file_sha256", 64),
        (RELEASE, RELEASE_SHA, "outputs", 187),
    ):
        path = ROOT / relative
        if not path.is_file():
            continue
        if digest(path) != expected:
            integrity.append({"path": relative, "reason": "PINNED_MANIFEST_SHA256_MISMATCH"})
            continue
        try:
            bindings = json.loads(path.read_text(encoding="utf-8"))[field]
            if not isinstance(bindings, dict) or len(bindings) != required_count:
                raise ValueError("Unexpected binding inventory")
            for name, sha in bindings.items():
                # v8 remains exact historical evidence. Current serving inputs
                # are independently checked below against the v10 inventory.
                resolved_name = (HISTORICAL_RUNTIME + "/" + name) if field == "file_sha256" else name
                bound = (ROOT / resolved_name).resolve()
                if not bound.is_relative_to(ROOT) or not bound.is_file():
                    integrity.append({"path": name, "reason": "BOUND_FILE_MISSING_OR_OUTSIDE_ROOT"})
                elif digest(bound) != sha:
                    integrity.append({"path": name, "reason": "BOUND_FILE_SHA256_MISMATCH"})
                elif field == "file_sha256":
                    runtime_count += 1
                else:
                    approved_count += 1
        except (OSError, UnicodeError, KeyError, TypeError, ValueError) as error:
            integrity.append({"path": relative, "reason": "INVALID_BINDING_MANIFEST", "detail": str(error)})

    current_count = 0
    try:
        from tools.serving_release import verify
        current = verify(ROOT)
        current_count = len(current["file_sha256"])
    except (OSError, UnicodeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        integrity.append({"path": CURRENT_FREEZE, "reason": "CURRENT_SERVING_BINDING_FAILED", "detail": str(error)})

    unexpected = sorted(actual - ROOT_FILES)
    return {
        "schema_version": "repository-structure-audit-v4",
        "ok": not (unexpected or missing or broken or missing_critical or integrity),
        "unexpected_root_files": unexpected,
        "missing_navigation_files": missing,
        "broken_navigation_links": broken,
        "missing_critical_source_files": missing_critical,
        "integrity_errors": integrity,
        "local_links_checked": checked,
        "root_file_count": len(actual),
        "runtime_freeze_files_verified": runtime_count,
        "current_serving_files_verified": current_count,
        "approved_output_files_verified": approved_count,
        "note": "Canonical navigation, byte-exact historical v8 snapshots and v9/v9.1 manifests, current v10 inputs and original scoped approval paths. Not factual or deployment acceptance.",
    }


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
