FROM qdrant/qdrant:v1.19.2
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
COPY boot.py /qdrant/boot.py
ENV QDRANT__SERVICE__HTTP_PORT=6333 QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__TELEMETRY_DISABLED=true
ENTRYPOINT ["python3", "/qdrant/boot.py"]
