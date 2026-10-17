# The scoring engine as a container for Google Cloud Run (see DEPLOY.md).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Cloud Run keeps no files between restarts; data/ holds caches and the run log
# for the life of the instance only. Leads also go to Netlify Forms and email.
RUN mkdir -p data

# Cloud Run sets PORT (8080 by default).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips="*"
