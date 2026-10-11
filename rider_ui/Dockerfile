FROM python:3.12-slim
WORKDIR /app
COPY rider_ui/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY rider_ui/__init__.py rider_ui/app.py rider_ui/client.py rider_ui/safeguards.py rider_ui/theme.css /app/rider_ui/
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EXPOSE 8080
CMD ["sh", "-c", "python -m streamlit run rider_ui/app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true --global.developmentMode=false --server.enableXsrfProtection=true --server.enableCORS=true --server.maxUploadSize=5 --browser.gatherUsageStats=false"]


