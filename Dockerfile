FROM python:3.11-slim

WORKDIR /app

ARG BINANCE_API_KEY
ARG BINANCE_API_SECRET

ENV BINANCE_API_KEY=${BINANCE_API_KEY}
ENV BINANCE_API_SECRET=${BINANCE_API_SECRET}

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

COPY app/ ./app/

WORKDIR /app/app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
