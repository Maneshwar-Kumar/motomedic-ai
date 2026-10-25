FROM python:3.12-slim AS dependencies
WORKDIR /app
COPY rider_ui/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
FROM dependencies AS verified
COPY rider_ui /app/rider_ui
COPY controller_contracts.py /app/controller_contracts.py
RUN python -B -m unittest discover -s rider_ui/tests -p 'test_*.py' -v
FROM dependencies AS runtime
COPY --from=verified /app/requirements.txt /app/requirements.txt
COPY rider_ui/__init__.py rider_ui/app.py rider_ui/client.py rider_ui/safeguards.py rider_ui/identity.py rider_ui/verified_sse.py rider_ui/theme.css /app/rider_ui/
RUN useradd --uid 10001 --create-home rider
USER rider
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EXPOSE 8080
CMD ["sh", "-c", "python -m streamlit run rider_ui/app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true --global.developmentMode=false --server.enableXsrfProtection=true --server.enableCORS=true --server.maxUploadSize=5 --browser.gatherUsageStats=false"]


