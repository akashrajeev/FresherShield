# FresherShield: fresher job finder + scam checker (FastAPI, SerpApi).
#   docker build -t freshershield .
#   docker run --rm -p 8000:8000 -e SERPAPI_API_KEY=your_key -v fs-cache:/app/.cache freshershield
# Without a key the app runs in offline mode (cache only).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN useradd --create-home fs && mkdir -p .cache && chown fs .cache
USER fs

# The SerpApi response cache lives here; mount a volume to keep it (and your credits) across runs.
VOLUME ["/app/.cache"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/status')"
CMD ["python", "-m", "app.main"]
