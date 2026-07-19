FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system redteam && adduser --system --ingroup redteam redteam

# requirements.lock is the reproducible production install target.
COPY requirements.lock pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps . \
    && mkdir -p /app/reports \
    && chown -R redteam:redteam /app

USER redteam

EXPOSE 8080
CMD ["uvicorn", "redteam_benchmark.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
