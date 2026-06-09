# Graph Report - .  (2026-06-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 719 nodes · 1411 edges · 42 communities (39 shown, 3 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 173 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `01357a6d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 39|Community 39]]

## God Nodes (most connected - your core abstractions)
1. `auth_headers()` - 39 edges
2. `User` - 31 edges
3. `emit()` - 25 edges
4. `KpiAlert` - 19 edges
5. `FastAPI` - 19 edges
6. `Trade` - 19 edges
7. `WebSocketHub` - 19 edges
8. `evaluate()` - 18 edges
9. `RiskEngine` - 16 edges
10. `VolatilityMonitor` - 13 edges

## Surprising Connections (you probably didn't know these)
- `test_audit_chain_tamper_detection()` --calls--> `_compute_row_hash()`  [INFERRED]
  tests/test_kpi_audit_completeness.py → app/audit/service.py
- `test_expired_jwt_returns_401()` --calls--> `create_access_token()`  [INFERRED]
  tests/test_auth_security.py → app/core/security.py
- `Account` --uses--> `User`  [INFERRED]
  tests/test_risk_engine.py → app/models/user.py
- `float` --uses--> `User`  [INFERRED]
  tests/test_risk_engine.py → app/models/user.py
- `int` --uses--> `User`  [INFERRED]
  tests/test_risk_engine.py → app/models/user.py

## Import Cycles
- 1-file cycle: `app/alerts/routes.py -> app/alerts/routes.py`
- 1-file cycle: `app/main.py -> app/main.py`
- 1-file cycle: `app/audit/routes.py -> app/audit/routes.py`
- 1-file cycle: `app/audit/service.py -> app/audit/service.py`
- 1-file cycle: `app/services/binance_service.py -> app/services/binance_service.py`
- 1-file cycle: `app/api_keys/service.py -> app/api_keys/service.py`
- 1-file cycle: `app/risk_engine/engine.py -> app/risk_engine/engine.py`
- 1-file cycle: `app/risk_engine/leverage.py -> app/risk_engine/leverage.py`
- 1-file cycle: `app/risk_engine/exposure.py -> app/risk_engine/exposure.py`
- 1-file cycle: `app/risk_engine/margin.py -> app/risk_engine/margin.py`
- 1-file cycle: `app/risk_engine/volatility.py -> app/risk_engine/volatility.py`
- 2-file cycle: `app/alerts/routes.py -> app/main.py -> app/alerts/routes.py`
- 2-file cycle: `app/audit/routes.py -> app/main.py -> app/audit/routes.py`
- 2-file cycle: `app/main.py -> app/realtime/ws_hub.py -> app/main.py`
- 3-file cycle: `app/alerts/routes.py -> app/api/deps.py -> app/main.py -> app/alerts/routes.py`
- 3-file cycle: `app/api/deps.py -> app/main.py -> app/audit/routes.py -> app/api/deps.py`
- 3-file cycle: `app/main.py -> app/services/market_stream.py -> app/realtime/ws_hub.py -> app/main.py`
- 3-file cycle: `app/main.py -> app/services/kline_stream.py -> app/realtime/ws_hub.py -> app/main.py`
- 3-file cycle: `app/main.py -> app/services/user_data_stream.py -> app/realtime/ws_hub.py -> app/main.py`

## Hyperedges (group relationships)
- **Infrastructure Stack** — docker_docker_compose_backend, docker_docker_compose_redis, docker_docker_compose_prometheus [EXTRACTED 1.00]

## Communities (42 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (48): Any, api_key_headers(), await_alert(), get_kline_range(), measure_latency(), AsyncClient, float, int (+40 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (50): AsyncSession, int, Request, str, AsyncSession, int, OrderCreate, Request (+42 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (37): ApiKeyCreate, ApiKeyResponse, Returned once on key creation or regeneration. The `secret` field is never store, Safe representation — never contains the raw secret., ApiKeyCreate, str, AsyncSession, int (+29 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (26): KpiAlert, AsyncSession, metrics(), AsyncSession, Decimal, int, AsyncSession, int (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (29): AsyncSession, Request, WebSocket, WebSocket, WebSocket, bool, int, str (+21 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (10): bool, Decimal, int, str, _adjusted_timestamp(), Close a position by placing a reduceOnly market order in the opposite direction., UMFutures subclass that injects the server-time-corrected timestamp     directl, Fetch Binance server time and correct local clock drift for all signed requests. (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (23): admin_token(), api_key_pair(), event_loop(), http_client(), placed_orders(), AsyncClient, bool, int (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (21): tests/test_risk_engine.py ────────────────────────── Unit tests for RiskEngine, R2: $15K notional moves into the 10K–100K bracket → cap steps to 5x., R3: $600K notional exceeds the $500K bracket → cap steps to 1x.     Global thre, R4: Professional tier, $10K notional, L=20 — approved at tier cap., R5: Institutional tier, $10K notional, L=50 — approved at tier cap., R9: balance=$50, required_margin=$1000/10=$100 → rejected., R10: Global cap is $10M; adding $200K to existing $9.9M → rejected., R11: Standard tier limit = 5% of $10M = $500K; adding $10K to $495K → rejected. (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (20): Decimal, int, str, liquidation_price(), maintenance_margin_rate(), margin_ratio(), Initial margin = notional / leverage., Return the maintenance margin rate (MMR) for a given leverage level. (+12 more)

### Community 9 - "Community 9"
Cohesion: 0.13
Nodes (14): float, str, float, int, str, Request, AlertingService, KPICollector (+6 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (19): max_lev(), float, int, str, tests/test_leverage_matrix.py ────────────────────────────── Unit tests for ge, Unknown tier string falls back to standard tier caps., $10,000 is exactly at the bracket-1 ceiling → tier cap applies., $10,001 crosses into bracket 2 → standard drops to 5x. (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.25
Nodes (11): ApiKeyService, Verify ``X-API-Key`` + ``X-API-Secret`` credentials.          Eagerly loads ``, Return ``(key_id, raw_secret, key_hash)``.          ``key_id``    — 32 hex cha, Create and persist a new API key.          Returns ``(ApiKey, raw_secret)``., Mark the key as inactive. The row is kept for audit purposes., Rotate the secret in-place. The previous secret is immediately invalidated., ApiKey, AsyncSession (+3 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (9): AsyncSession, int, str, hash_password(), FastAPI, get_trading_kpi(), get_candles(), get_price() (+1 more)

### Community 13 - "Community 13"
Cohesion: 0.16
Nodes (8): AuditLog, Audit logging service.  emit() is the single public entry-point.  It is synchr, BaseSettings, get_settings(), Settings, Binance mark price WebSocket stream service.  Subscribes to mark price updates, Binance User Data Stream service.  Maintains a persistent WebSocket connection, tests/seed_test_data.py ─────────────────────── One-time setup script: fund te

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (16): RiskEngine, VolatilityMonitor, evaluate(), make_account(), make_user(), Account, float, int (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.23
Nodes (16): auth_headers(), AsyncClient, str, tests/test_regulator_access.py ──────────────────────────────── Regulator inte, Trader role → GET /regulator/overview must return 403., Trader role must be denied all /regulator/* endpoints., Admin role must have access to all /regulator/* endpoints., Regulator role must have access to all /regulator/* endpoints. (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.21
Nodes (16): _compute_signature(), AsyncClient, str, tests/test_kpi_ledger.py ───────────────────────── KPI 8 — Ledger Snapshot Int, Snapshot must contain open_positions, recent_trades, recent_audit_entries., GET /regulator/exposure must also include a valid HMAC signature., Recompute HMAC-SHA256 over the sorted-keys JSON of the payload., GET /regulator/overview must include a 'signature' field. (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (4): bool, str, increment_liquidation_event(), UserDataStreamService

### Community 18 - "Community 18"
Cohesion: 0.26
Nodes (15): _get_audit_events(), AsyncClient, int, str, tests/test_kpi_audit_completeness.py ────────────────────────────────────── KP, POST /orders/{id}/cancel must produce an ORDER_CANCELLED audit entry., API key creation and deactivation must each produce an audit entry., GET /audit/verify-chain must return integrity=OK on an untampered chain. (+7 more)

### Community 19 - "Community 19"
Cohesion: 0.16
Nodes (16): get_auth_method(), get_db(), get_db_dep(), get_user_id(), get_user_role(), Route dependency that enforces role-based access control.      Usage::, Returns the authentication method used: 'jwt' or 'api_key'., Route dependency that enforces API key scope requirements.      JWT-authentica (+8 more)

### Community 20 - "Community 20"
Cohesion: 0.24
Nodes (6): Request, BaseHTTPMiddleware, increment_rate_limit_hit(), AuthMiddleware, LoggingMiddleware, RateLimitMiddleware

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (10): Account, Decimal, int, str, User, Decimal, int, str (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (9): Decimal, float, str, Volatility monitor.  Tracks the 1-hour candlestick range for each symbol as a, Record the range of a *closed* candle for the given symbol.          Only 1h c, Return a multiplier in (0, 1] to apply to the base max leverage.          Retu, Return the latest recorded 1h range % for a symbol, or None., KPI 9 — Tamper detection: directly modify a row in the DB and confirm     that (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.35
Nodes (7): Account, AsyncSession, float, int, Position, Fetch live balance from Binance and update the local account record., Return each position paired with its current unrealized PnL.

### Community 24 - "Community 24"
Cohesion: 0.26
Nodes (10): AsyncSession, datetime, int, str, get_audit_log(), list_audit_logs(), Walk the audit-log hash chain and verify integrity.      Returns ``{\"integrit, verify_audit_chain() (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.24
Nodes (5): float, int, str, Called by the Binance mark price WebSocket stream to update cached prices., Return OHLCV candles from Binance ascending by open_time.

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (11): AsyncClient, str, tests/test_kpi_uptime.py ───────────────────────── KPI 1 — API Uptime ≥ 99.95, GET /kpi/system must return an uptime field., Uptime value must be in the range [0.0, 100.0]., Confirm /health returns 200 — system is available during test window., GET /kpi/system must include latency_ms, error_rate, and uptime., test_health_endpoint_reachable() (+3 more)

### Community 27 - "Community 27"
Cohesion: 0.27
Nodes (7): apply_schema_compat_migrations(), kpi_stream_publisher(), lifespan(), market_stream_publisher(), Apply minimal compatibility migrations for legacy local databases., seed_initial_data(), KPI Threshold Alerting Service.  check_thresholds() is awaited directly inside

### Community 28 - "Community 28"
Cohesion: 0.40
Nodes (9): acknowledge_alert(), get_alert(), list_alerts(), KpiAlertResponse, AsyncSession, datetime, int, str (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.29
Nodes (9): AsyncClient, str, tests/test_kpi_auth_failures.py ──────────────────────────────── KPI 6 — API A, Submitting N bad-password logins must increase auth_failures in     GET /kpi/se, Requests with wrong API-key headers must also increment auth_failures., GET /kpi/security is accessible and returns required fields., test_auth_failure_counter_increments(), test_invalid_api_key_increments_counter() (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (9): AsyncClient, str, tests/test_kpi_error_rate.py ────────────────────────────── KPI 2 — API Error, 50 valid GET /market/price/BTCUSDT requests must all return 200., Invalid symbol, missing fields, or bad data must return 4xx,     never 5xx — un, GET /kpi/system must report error_rate < 0.1 (< 0.1 %)., test_kpi_error_rate_below_threshold(), test_malformed_requests_return_4xx_not_5xx() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (9): AsyncClient, str, tests/test_kpi_liquidation.py ────────────────────────────── KPI 5 — Liquidati, GET /regulator/liquidations must return 200 and a list., Each liquidation entry must contain the fields required by Chapter 3., KPI 5: liquidations / total_positions must be < 10 %.      Uses the current po, test_liquidation_entries_have_required_fields(), test_liquidation_rate_below_threshold() (+1 more)

### Community 32 - "Community 32"
Cohesion: 0.22
Nodes (6): ApiKey, Base, DeclarativeBase, Account, Position, Order

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (5): tests/generate_kpi_report.py ───────────────────────────── Run all KPI tests a, Execute the KPI test suite and return the parsed JSON report., Collapse individual test results into per-KPI summary rows.      Each row: {kp, run_tests(), summarise()

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (8): Backend Service, Prometheus Service, Redis Service, API Governance, Crypto Exchange POC Backend, Risk Engine, Binance Futures Connector, FastAPI

### Community 35 - "Community 35"
Cohesion: 0.29
Nodes (6): info, description, name, schema, item, variable

## Knowledge Gaps
- **42 isolated node(s):** `int`, `AsyncSession`, `WebSocket`, `int`, `bool` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `auth_headers()` connect `Community 15` to `Community 0`, `Community 16`, `Community 18`, `Community 26`, `Community 29`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.249) - this node is a cross-community bridge._
- **Why does `test_audit_chain_tamper_detection()` connect `Community 22` to `Community 1`, `Community 18`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `create_access_token()` connect `Community 4` to `Community 0`, `Community 12`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `auth_headers()` (e.g. with `test_deactivated_key_returns_401()` and `test_full_key_can_place_orders()`) actually correct?**
  _`auth_headers()` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `User` (e.g. with `AsyncSession` and `Request`) actually correct?**
  _`User` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `KpiAlert` (e.g. with `Base` and `AsyncSession`) actually correct?**
  _`KpiAlert` has 18 INFERRED edges - model-reasoned connections that need verification._
- **What connects `int`, `Route dependency that enforces role-based access control.      Usage::`, `Returns the authentication method used: 'jwt' or 'api_key'.` to the rest of the system?**
  _188 weakly-connected nodes found - possible documentation gaps or missing edges._