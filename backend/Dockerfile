# backend/Dockerfile
FROM python:3.11-slim

# system deps needed for some python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl gcc libsqlite3-dev sqlite3 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

WORKDIR /app

# copy requirements first for better caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy app code
COPY app ./app

# create model_data dir (mounted as volume by compose/run)
RUN mkdir -p /app/model_data && chown -R root:root /app/model_data

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
