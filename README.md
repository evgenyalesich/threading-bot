# Threading Bot

Production-style trading workstation for:
- signal discovery (entry/exit points),
- backtesting on historical data,
- market scanning,
- semi-auto/manual order execution,
- account monitoring (balance, positions, trade history).

Stack:
- Backend: FastAPI, SQLAlchemy (async), Alembic, asyncpg, pandas, TA-Lib, python-binance
- Frontend: React + Vite + lightweight-charts
- Data: PostgreSQL
- Exchange: Binance (spot/futures, testnet/real)

## What This Project Solves

Threading Bot combines research and execution in one app:
- sync and store candles locally,
- run strategy analysis and backtest from the same dataset,
- visualize entries/exits and technical context on chart,
- submit bracket-like orders (entry + protective exits),
- monitor account state and recent trades.

## High-Level Architecture

```mermaid
flowchart LR
    UI[React Frontend] -->|REST /api/*| API[FastAPI Backend]
    UI -->|WS /api/stream| STREAM[Market Stream Service]
    API --> DB[(PostgreSQL)]
    API --> STRAT[Strategy Engine]
    API --> BT[Backtest Engine]
    API --> EX[Binance Exchange Adapter]
    EX --> BINANCE[(Binance API)]
    STREAM --> BINANCE
```

## Backend Modules

```mermaid
flowchart TD
    Router[API Routers] --> Services[Domain Services]
    Services --> Repos[Repositories]
    Repos --> DB[(PostgreSQL)]
    Services --> Strategies[Strategies]
    Services --> Exchange[Exchange Adapters]
    Exchange --> Binance[(Binance)]
```

Core directories:
- `backend/app/api/routes` REST endpoints
- `backend/app/services` business logic
- `backend/app/strategies` signal logic
- `backend/app/repositories` DB access layer
- `backend/alembic` migrations
- `frontend/src` dashboard UI

## Trading and Analysis Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant BX as Binance

    U->>FE: Run analysis/backtest
    FE->>BE: POST /api/analysis/run or /api/analysis/backtest
    BE->>DB: Load candles
    BE->>BE: Strategy + risk + execution simulation
    BE-->>FE: Signal/backtest stats
    U->>FE: Confirm order
    FE->>BE: POST /api/orders
    BE->>BX: Place order (+ protective orders)
    BE->>DB: Save order state
    BE-->>FE: Result
```

## Strategy and Backtest Engine

Current default strategy:
- Triple Screen style MTF logic (`three_screens_strategy.py`)
- trend timeframe + entry timeframe
- stop/take levels packed into `trade_plan`

Backtest improvements already integrated:
- intra-candle ambiguity mode (`pessimistic` / `optimistic`)
- slippage model (`slippage_bps`)
- fees model (`fee_bps`)
- partial TP handling
- equity-based metrics:
  - ending equity
  - max drawdown (abs + %)
  - Sharpe approximation
  - CAGR approximation
  - expectancy

## Supported Features

- historical sync to local DB
- real-time kline stream
- signal generation and scan
- backfill signals over history
- backtesting
- spot/futures order submission
- stop/breakeven update
- account summary:
  - spot balances
  - futures balances/positions
  - recent exchange trades

## Data Model (Simplified)

```mermaid
erDiagram
    CANDLES {
      string symbol
      string timeframe
      datetime open_time
      float open
      float high
      float low
      float close
      float volume
      string source
    }
    SIGNALS {
      int id
      string symbol
      string timeframe
      string signal_type
      float confidence
      json meta
      datetime created_at
    }
    ORDERS {
      int id
      string symbol
      string market
      string side
      string order_type
      float quantity
      string status
      float stop_loss
      float take_profit
      json take_levels
      datetime created_at
    }
    CANDLES ||--o{ SIGNALS : feeds
    SIGNALS ||--o{ ORDERS : triggers
```

## Requirements

- Windows 10/11 (PowerShell)
- Python 3.12+
- Node.js 18+
- PostgreSQL (local service)
- `uv` installed

## Environment Configuration

`backend/.env` example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/threading_bot
CORS_ORIGINS=http://localhost:5173
BINANCE_TESTNET=true

BINANCE_SPOT_TESTNET_API_KEY=
BINANCE_SPOT_TESTNET_API_SECRET=
BINANCE_FUTURES_TESTNET_API_KEY=
BINANCE_FUTURES_TESTNET_API_SECRET=

BINANCE_API_KEY=
BINANCE_API_SECRET=
```

Important:
- keep secrets only in local `.env`
- never commit exchange keys
- use separate keys for spot/futures testnet if available

## Quick Start (Windows)

From project root:

```powershell
.\dev-up.ps1
```

This script:
- syncs backend dependencies
- installs frontend dependencies
- runs Alembic migrations
- starts backend and frontend in separate PowerShell windows

Access:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

## Manual Start

Backend:

```powershell
cd backend
uv sync
$env:DEBUG='false'
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## DB Setup and Migrations

Create DB:

```sql
CREATE DATABASE threading_bot;
```

Apply migrations:

```powershell
cd backend
uv run alembic upgrade head
```

Check migration head:

```powershell
uv run alembic current
```

## API Entry Points

Core:
- `GET /api/health`
- `POST /api/market/sync`
- `GET /api/market/candles`
- `GET /api/market/indicators`

Signals/analysis:
- `POST /api/analysis/run`
- `POST /api/analysis/explain`
- `POST /api/analysis/backfill`
- `POST /api/analysis/scan`
- `POST /api/analysis/backtest`

Execution and account:
- `POST /api/orders`
- `GET /api/orders`
- `POST /api/orders/{id}/breakeven`
- `POST /api/orders/{id}/stop`
- `GET /api/account/summary`
- `GET /api/account/trades`

## Operational Workflow

1. Select market/pair/timeframe
2. Sync history
3. Run analysis and inspect trade plan
4. Run backtest for robustness check
5. Confirm order (semi-auto mode)
6. Monitor positions, balances, and trade outcomes
7. Iterate filters and strategy parameters

## Troubleshooting

`404` on frontend resources:
- ensure frontend dev server is running on `5173`
- verify `VITE_API_BASE` / `VITE_WS_BASE` if custom setup

Chart crash `data must be asc ordered by time`:
- fixed by data normalization/dedup in `ChartPanel`
- if it appears again, check upstream candle timestamp duplicates

`invalid_api_key`:
- verify selected `market` and `trade_env`
- verify corresponding key pair:
  - `BINANCE_SPOT_TESTNET_*` for spot testnet
  - `BINANCE_FUTURES_TESTNET_*` for futures testnet
- restart backend after `.env` changes

No balances/positions:
- futures testnet and spot testnet use separate wallets
- fund the proper testnet account

## Security Notes

- do not share `.env`
- rotate keys if leaked
- use read/trade permissions minimally
- restrict real account trading until testnet validation is stable

## Testing and Quality

Backend sanity check:

```powershell
uv run --project backend python -m compileall backend\app
```

Frontend build check:

```powershell
npm --prefix frontend run build
```

## Roadmap

- walk-forward validation endpoint/report
- richer risk analytics (exposure, VaR-like stress, regime detection)
- execution reconciliation with exchange fills
- strategy registry with multi-strategy orchestration

## License

MIT
