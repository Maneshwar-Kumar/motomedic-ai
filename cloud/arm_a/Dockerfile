FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
WORKDIR /app
COPY cloud/arm_a/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app
# Hosted build downloads the exact pinned query model; no manual ingestion or embedding.
RUN HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 python cloud/arm_a/package_models.py
RUN useradd --uid 10001 --create-home motomedic && chown -R motomedic:motomedic /app
USER motomedic
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "1", "--timeout", "180", "--access-logfile", "-", "cloud.arm_a.app:load_production()"]
