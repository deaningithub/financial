FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY . .

RUN mkdir -p /tmp/data /tmp/outputs /tmp/logs

ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=8080

ENV DATA_DIR=/tmp/data
ENV OUTPUT_DIR=/tmp/outputs
ENV LOG_DIR=/tmp/logs

EXPOSE 8080

CMD ["python", "-m", "financial_system.cli", "run"]
