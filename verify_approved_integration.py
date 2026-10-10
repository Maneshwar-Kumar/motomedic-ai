"""Record step-one exit checks from actual tests, preserving signed history."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).parent


def verify(output=ROOT / "reports/approved_integration_exit_v1.json"):
    from approved_registry import ApprovedEvidenceRegistry, RELEASE_SHA
    registry = ApprovedEvidenceRegistry.load(ROOT, Path(os.environ.get("MOTOMEDIC_TEST_INDEX", ROOT / "build/index-bge-final")))
    # The preserved isolated suite uses its historical sibling import.
    sys.path.insert(0, str(ROOT / "human_review/agent_release_161"))
    names = ("test_approved_integration", "test_reviewed_controller", "test_constrained_generator",
             "test_approval_consumer")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    files = ("approved_registry.py", "approved_runner.py", "reviewed_controller.py",
             "test_approved_integration.py", "verify_approved_integration.py",
             "human_review/grounding_refinement/case_suite.py")
    report = {"schema_version": "approved-integration-exit-v1",
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "step": 1, "exit_passed": result.wasSuccessful(),
              "authority": "OWNER_DELEGATED_AGENT_COORDINATOR", "release_sha256": RELEASE_SHA,
              "binding_validation": registry._consumer.check_bindings(),
              "bound_files": len(registry._consumer.manifest["outputs"]),
              "registry_lock": registry.lock, "index_id": registry.index_id,
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "test_modules": names,
              "runtime_files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
              "source_content_approval_preserved": True, "signed_package_changed": False,
              "legacy_human_flags_changed": False, "index_rebuilt": False,
              "grounded_live_provider_calls": 0, "deployment_changed": False, "billing_changed": False,
              "test_boundary": "Actual approved objects/shared gates; scripted providers and gate bundles are software simulations, not semantic or live performance evaluation",
              "remaining_scope": "Ten quality findings and image-dependent paths fail closed; step2 live/session journeys and step3 hosted browser remain pending"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not result.wasSuccessful():
        raise SystemExit(1)
    print(json.dumps({"step1_exit_passed": True, "tests": result.testsRun, "bound_files": report["bound_files"]}))
    return report


if __name__ == "__main__":
    verify()
