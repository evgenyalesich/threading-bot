# Threading Bot

## Tech Stack
- Backend: FastAPI, SQLAlchemy (async), Alembic, asyncpg, pandas, TA-Lib, python-binance
- Frontend: React + Vite + lightweight-charts
- Database: PostgreSQL
- Exchange: Binance (spot/futures, testnet/real)

## RU: О проекте
Threading Bot это торговый воркспейс для:
- поиска точек входа/выхода,
- бэктестинга на истории,
- сканирования рынка,
- полуавтоматического/ручного исполнения сделок,
- мониторинга баланса, позиций и истории трейдов.

## EN: About
Threading Bot is a trading workstation for:
- entry/exit signal discovery,
- historical backtesting,
- market scanning,
- semi-automatic/manual execution,
- balance, position, and trade-history monitoring.

## RU: Архитектура
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

## EN: Architecture
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

## RU: Структура проекта
- `backend/app/api/routes` REST endpoints
- `backend/app/services` бизнес-логика
- `backend/app/strategies` стратегии сигналов
- `backend/app/repositories` слой доступа к БД
- `backend/alembic` миграции
- `frontend/src` UI

## EN: Project Structure
- `backend/app/api/routes` REST endpoints
- `backend/app/services` domain services
- `backend/app/strategies` strategy logic
- `backend/app/repositories` DB access layer
- `backend/alembic` migrations
- `frontend/src` UI

## RU: Поток анализа и исполнения
```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant BE as Backend
    participant DB as PostgreSQL
    participant BX as Binance
    U->>FE: Запуск анализа/бэктеста
    FE->>BE: POST /api/analysis/run или /api/analysis/backtest
    BE->>DB: Загрузка свечей
    BE->>BE: Стратегия + risk + симуляция исполнения
    BE-->>FE: Сигнал/статистика
    U->>FE: Подтверждение ордера
    FE->>BE: POST /api/orders
    BE->>BX: Размещение ордера (+ защитные)
    BE->>DB: Сохранение состояния
    BE-->>FE: Результат
```

## EN: Analysis and Execution Flow
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
    BE-->>FE: Signal/stats
    U->>FE: Confirm order
    FE->>BE: POST /api/orders
    BE->>BX: Place order (+ protective exits)
    BE->>DB: Persist order state
    BE-->>FE: Result
```

## RU: Бэктест и метрики
Поддерживается:
- intra-candle режим (`pessimistic` / `optimistic`)
- проскальзывание (`slippage_bps`)
- комиссии (`fee_bps`)
- partial TP
- equity-based метрики: ending equity, max drawdown (abs/%), Sharpe, CAGR, expectancy

## EN: Backtest and Metrics
Supported:
- intra-candle mode (`pessimistic` / `optimistic`)
- slippage (`slippage_bps`)
- fees (`fee_bps`)
- partial TP handling
- equity-based metrics: ending equity, max drawdown (abs/%), Sharpe, CAGR, expectancy

## RU: Требования
- Windows 10/11 (PowerShell)
- Python 3.12+
- Node.js 18+
- PostgreSQL
- `uv`

## EN: Requirements
- Windows 10/11 (PowerShell)
- Python 3.12+
- Node.js 18+
- PostgreSQL
- `uv`

## RU: Переменные окружения (`backend/.env`)
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

## EN: Environment (`backend/.env`)
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

## RU: Быстрый запуск (Windows)
```powershell
.\dev-up.ps1
```
Скрипт:
- ставит backend/frontend зависимости,
- применяет миграции,
- запускает backend/frontend в отдельных окнах.

Frontend: `http://localhost:5173`  
Backend: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

## EN: Quick Start (Windows)
```powershell
.\dev-up.ps1
```
This script:
- installs backend/frontend dependencies,
- runs migrations,
- starts backend/frontend in separate PowerShell windows.

Frontend: `http://localhost:5173`  
Backend: `http://localhost:8000`  
Docs: `http://localhost:8000/docs`

## RU: Ручной запуск
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

## EN: Manual Start
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

## RU: База и миграции
Создать БД:
```sql
CREATE DATABASE threading_bot;
```
Применить миграции:
```powershell
cd backend
uv run alembic upgrade head
```
Проверить ревизию:
```powershell
uv run alembic current
```

## EN: Database and Migrations
Create DB:
```sql
CREATE DATABASE threading_bot;
```
Apply migrations:
```powershell
cd backend
uv run alembic upgrade head
```
Check current revision:
```powershell
uv run alembic current
```

## RU: API (основное)
- `GET /api/health`
- `POST /api/market/sync`
- `GET /api/market/candles`
- `GET /api/market/indicators`
- `POST /api/analysis/run`
- `POST /api/analysis/explain`
- `POST /api/analysis/backfill`
- `POST /api/analysis/scan`
- `POST /api/analysis/backtest`
- `POST /api/orders`
- `GET /api/orders`
- `POST /api/orders/{id}/breakeven`
- `POST /api/orders/{id}/stop`
- `GET /api/account/summary`
- `GET /api/account/trades`

## EN: API (core)
- `GET /api/health`
- `POST /api/market/sync`
- `GET /api/market/candles`
- `GET /api/market/indicators`
- `POST /api/analysis/run`
- `POST /api/analysis/explain`
- `POST /api/analysis/backfill`
- `POST /api/analysis/scan`
- `POST /api/analysis/backtest`
- `POST /api/orders`
- `GET /api/orders`
- `POST /api/orders/{id}/breakeven`
- `POST /api/orders/{id}/stop`
- `GET /api/account/summary`
- `GET /api/account/trades`

## RU: Рабочий сценарий
1. Выбрать рынок/пару/таймфрейм.
2. Синхронизировать историю.
3. Запустить анализ, проверить trade plan.
4. Прогнать бэктест.
5. Подтвердить ордер.
6. Следить за балансом/позициями/историей.

## EN: Typical Workflow
1. Select market/pair/timeframe.
2. Sync history.
3. Run analysis and inspect trade plan.
4. Run backtest.
5. Confirm order.
6. Monitor balances/positions/history.

## RU: Troubleshooting
- `404` ресурсы: проверь что frontend запущен на `5173`.
- `invalid_api_key`: проверь `market`/`trade_env` и корректные ключи (`SPOT_TESTNET` vs `FUTURES_TESTNET`).
- Нет баланса/позиций: в testnet отдельные кошельки spot/futures.

## EN: Troubleshooting
- `404` resources: ensure frontend runs on `5173`.
- `invalid_api_key`: verify `market`/`trade_env` and correct key pair (`SPOT_TESTNET` vs `FUTURES_TESTNET`).
- Empty balances/positions: spot and futures testnet wallets are separate.

## RU: Безопасность
- Не коммитить `.env`.
- Ротировать ключи при утечке.
- Использовать минимум прав у API ключей.

## EN: Security
- Never commit `.env`.
- Rotate keys if leaked.
- Use least-privilege API key permissions.

## RU: Проверка качества
```powershell
uv run --project backend python -m compileall backend\app
npm --prefix frontend run build
```

## EN: Quality Checks
```powershell
uv run --project backend python -m compileall backend\app
npm --prefix frontend run build
```

## License
MIT
