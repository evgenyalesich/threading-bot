# Threading Bot

Modular trading bot with a FastAPI backend, Postgres storage, and a React dashboard.

## Architecture
- `backend/`: FastAPI + SQLAlchemy async + strategy services
- `frontend/`: React UI (Vite + lightweight-charts)
- `infra/`: Postgres docker-compose

## Prerequisites
- Linux
- `uv` installed
- Node.js 18+
- Docker (optional, for Postgres)

## Setup
### 1) Python + backend
```bash
cd backend
uv python install 3.13.5
uv venv --python 3.13.5
source .venv/bin/activate
uv pip install -e .
cp .env.example .env
```

If `ta-lib` fails to build, install system dependencies first:
```bash
sudo apt-get install -y ta-lib
```

### 2) Postgres
Use Docker:
```bash
cd infra
docker compose up -d
```
Or point `DATABASE_URL` in `backend/.env` to your local Postgres.

### 3) Frontend
```bash
cd frontend
npm install
npm run dev
```

## Run
### Backend
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm run dev
```

To change API/WS endpoints, copy `frontend/.env.example` to `frontend/.env`.

### Migrations
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

To auto-create tables without migrations (dev only), set `DB_AUTO_CREATE=true` in `backend/.env`.

### Single entrypoint
Build the frontend and run the combined server:
```bash
cd frontend
npm run build
cd ..
python run.py
```

## Notes
- Do **not** hardcode exchange API keys. Keep them in `backend/.env`.
- For historical data, use a `yfinance` symbol (e.g. `BTC-USD`).
- Trading symbols for Binance differ (e.g. `BTCUSDT`). Mapping is handled via `/api/symbols`.
- For testnet streaming, override `BINANCE_WS_SPOT_URL` / `BINANCE_WS_FUTURES_URL` in `backend/.env`.
- Example: `BINANCE_WS_SPOT_URL=wss://testnet.binance.vision/ws`
- For testnet REST, override `BINANCE_REST_SPOT_URL` / `BINANCE_REST_FUTURES_URL`.
- Binance testnet often uses separate API keys for spot vs futures:
  - spot testnet: set `BINANCE_SPOT_TESTNET_API_KEY/SECRET` (falls back to `BINANCE_TESTNET_API_KEY/SECRET`)
  - futures testnet: set `BINANCE_FUTURES_TESTNET_API_KEY/SECRET` (falls back to `BINANCE_TESTNET_API_KEY/SECRET`)

## Useful endpoints
- REST health: `GET /api/health`
- Sync history: `POST /api/market/sync`
- List pairs: `GET /api/market/pairs?market=spot&quote=USDT`
- Run analysis: `POST /api/analysis/run`
- Mappings CRUD: `GET/POST/PUT/DELETE /api/symbols`
- WebSocket stream: `ws://localhost:8000/api/stream?symbol=BTC-USD&timeframe=15m&market=spot`
# theadinf-
