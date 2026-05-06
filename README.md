# Crypto Exchange POC Backend

Research-only simulation backend for a crypto exchange proof-of-concept, focused on:

- API governance (auth, rate limiting, logging)
- Risk-based leverage control (tiered leverage + margin + exposure + liquidation simulation)
- KPI observability (Prometheus metrics + KPI API)

## Tech Stack

- FastAPI (Python)
- PostgreSQL
- Redis
- Prometheus
- Docker Compose

## Project Structure

```text
crypto-exchange-poc-backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── order.py
│   │   │   ├── account.py
│   │   │   ├── market.py
│   │   │   ├── kpi.py
│   ├── services/
│   │   ├── order_service.py
│   │   ├── account_service.py
│   │   ├── market_service.py
│   ├── risk_engine/
│   │   ├── leverage.py
│   │   ├── margin.py
│   │   ├── exposure.py
│   │   ├── engine.py
│   ├── models/
│   │   ├── user.py
│   │   ├── account.py
│   │   ├── order.py
│   │   ├── trade.py
│   ├── schemas/
│   │   ├── order.py
│   │   ├── account.py
│   │   ├── market.py
│   │   ├── kpi.py
│   ├── middleware/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   ├── logging.py
│   ├── kpi/
│   │   ├── collector.py
│   │   ├── aggregator.py
│   ├── metrics/
│   │   ├── prometheus.py
├── docker/
│   ├── docker-compose.yml
│   ├── prometheus.yml
├── requirements.txt
├── README.md
```

## Run

From the `docker` directory:

```bash
docker-compose up
```

Backend: `http://localhost:8000`
Prometheus: `http://localhost:9090`

## Binance Testnet Setup

This backend is wired to Binance Spot Testnet for market prices and order placement.

1. Create Spot Testnet API credentials from Binance Testnet.
2. In the `docker` directory, create a `.env` file:

```env
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret
```

3. Start services:

```bash
docker compose up
```

If credentials are not set, market endpoints still try Testnet public price calls, but order placement/cancel to Testnet will return an error.

## API Governance

### Authentication

- Issue JWT via `POST /auth/token` with API key payload:
  - `beginner-key`
  - `intermediate-key`
  - `advanced-key`
- Use JWT on protected endpoints:
  - `Authorization: Bearer <access_token>`

### Rate limiting

- Redis-backed limit: `100 requests/minute` per API key
- Returns `429` when exceeded

### Logging

Each request logs:

- endpoint
- latency
- status code

## Core Endpoints

- `POST /auth/token` issue JWT access token
- `POST /orders` create and execute order (risk checks + Binance Testnet order placement)
- `POST /orders/{order_id}/cancel?user_id=...` cancel order (if not yet filled)
- `GET /account/{user_id}` account + margin + positions
- `GET /market/price/{symbol}` current Binance Testnet price (fallback to local simulation)
- `POST /market/tick` refresh market prices from Binance Testnet (fallback to local simulation)

## Risk Engine Logic

### Tier leverage limits

- `beginner` → max `5x`
- `intermediate` → max `10x`
- `advanced` → max `20x`

### Margin formula

`RequiredMargin = OrderSize * Price / Leverage`

Order rejected if:

- insufficient balance for required margin
- global exposure threshold exceeded

The engine tracks:

- total exposure per user
- global exposure

Liquidation simulation:

- if margin ratio `< liquidation threshold`, positions are marked liquidated

## Metrics and KPI

### Prometheus Metrics

Exposed at `GET /metrics`:

- `api_request_latency_seconds`
- `api_error_total`
- `api_requests_total`
- `liquidation_events_total`
- `auth_failures_total`
- `rate_limit_hits_total`

### KPI API

- `GET /kpi/system`
- `GET /kpi/trading`
- `GET /kpi/security`

Example response shape:

```json
{
  "latency_ms": 85,
  "error_rate": 0.02,
  "uptime": 99.95
}
```

## Notes

- This is a simulation system for research purposes only.
- It is not a production exchange backend.
