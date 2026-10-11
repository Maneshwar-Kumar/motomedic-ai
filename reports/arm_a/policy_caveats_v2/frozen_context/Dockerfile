FROM us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:9d92653a7984cea1a21f132752d961dbd1eb79140380d6d30773ea5ae3cf0969
USER root
COPY --chown=motomedic:motomedic . /app
RUN python -B -c "from pathlib import Path; import unittest; import test_approved_integration as f; f.ROOT=Path('/app'); f.INDEX=Path('/app/build/index'); suite=unittest.defaultTestLoader.loadTestsFromNames(['cloud.arm_a.test_api', 'cloud.arm_a.test_store', 'cloud.arm_a.test_composer', 'cloud.arm_a.test_policy_caveats', 'test_approved_integration', 'test_text_journeys', 'test_constrained_generator', 'cloud.arm_a.test_rider_contract', 'cloud.arm_a.test_question_wiring', 'rider_ui.tests.test_client', 'rider_ui.tests.test_identity', 'rider_ui.tests.test_verified_sse']); r=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not r.wasSuccessful())"
USER motomedic
RUN MOTOMEDIC_VALIDATION_HOSTED=cloudbuild python -B /app/tools/validate_policy_caveats.py
