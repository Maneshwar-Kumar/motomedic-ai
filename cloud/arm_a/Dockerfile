# Backend image for the section-template answer path (serving manifest v11).
# Inherit the exact packaged query model and dependency assets; never ingest or embed the manual.
# The build context must hold the committed serving inputs, arm_a_release.json and the pinned
# section index at build/section-index. Preparing that context is a later owner-scoped step.
FROM us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a8946299f34177aeda76cadbbd7fce0a33c5fd8f574438d823281ee78eb045e4
USER root
COPY --chown=motomedic:motomedic . /app
RUN python -B tools/check_installed_serving_release.py /app
USER motomedic
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "1200", "--access-logfile", "-", "cloud.arm_a.app:load_production()"]
