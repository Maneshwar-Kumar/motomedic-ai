FROM docker.io/library/python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS dependencies
WORKDIR /app
COPY rider_ui/requirements-linux-amd64-py312.lock.txt /app/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /app/requirements.txt
FROM dependencies AS verified
COPY rider_ui /app/rider_ui
COPY controller_contracts.py /app/controller_contracts.py
RUN python -B -m unittest discover -s rider_ui/tests -p 'test_*.py' -v
FROM dependencies AS runtime
COPY --from=verified /app/requirements.txt /app/requirements.txt
COPY rider_ui/__init__.py rider_ui/app.py rider_ui/client.py rider_ui/render.py rider_ui/timings.py rider_ui/safeguards.py rider_ui/identity.py rider_ui/verified_sse.py rider_ui/public_gateway.py rider_ui/public_edge.py rider_ui/theme.css /app/rider_ui/
RUN python -B -c "from rider_ui.render import timing_caption; from rider_ui.client import RiderAPI"
RUN useradd --uid 10001 --create-home rider
USER rider
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EXPOSE 8080
CMD ["python", "-m", "rider_ui.public_gateway"]


