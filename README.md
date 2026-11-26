# MacroHFT-Inspired Trading Terminal

A locally hosted algorithmic-trading research and execution terminal built with **React, TypeScript, FastAPI, Python, and MetaTrader 5**.

The application combines a trading terminal, market-data charts, strategy signals, risk-managed order execution, backtesting, portfolio analytics, and market simulations. It is designed to connect to a locally installed MetaTrader 5 desktop terminal. When MT5 is unavailable, the backend can still serve imported historical market data for charting and research.

> **Important:** This is a research and educational project, not a financial-advice service or a profitable trading system. The included strategy performed poorly in testing; treat its signals as experimental. Start with a demo account. Never connect a funded account unless you fully understand and have independently tested the execution and risk controls.

---

## Contents

- [Features](#features)
- [Architecture and entry points](#architecture-and-entry-points)
- [Requirements](#requirements)
- [MetaTrader 5 setup](#metatrader-5-setup)
- [Installation](#installation)
- [Running the application](#running-the-application)
- [Backend usage](#backend-usage)
- [Frontend usage](#frontend-usage)
- [Historical data and strategy models](#historical-data-and-strategy-models)
- [Configuration](#configuration)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Safety notes](#safety-notes)

## Features

- **Trading terminal:** market charts, symbol/timeframe selection, live bid/ask ticks, positions, and order panel.
- **MetaTrader 5 integration:** reads account status, symbols, ticks, bars, positions, and deal history; supports order submission and position closing.
- **Risk controls:** order validation, position sizing, stop-loss/take-profit handling, configurable risk limits, and account-mode checks.
- **Strategy research:** model-generated signals, regime/agent explanations, confidence information, and research results.
- **Backtesting:** historical strategy evaluation with configurable capital, risk, ATR stops/targets, spread, slippage, and cooldown.
- **Simulation Lab:** Monte Carlo simulations, Black–Scholes calculations and Greeks, strategy replay, and what-if scenarios. Simulated/theoretical results are not live market forecasts.
- **Portfolio and trade history:** account/position analytics and available deal/trade records.
- **Auto-trader:** explicitly started strategy execution with trade limits and a stop/stop-and-close control. It is off by default.
- **Chart tools and indicators:** technical indicators, chart drawings, support/resistance and price-alert tools.
- **Persistent settings and history:** SQLite by default, configurable through `DB_URL`.

## Architecture and entry points

The project runs as two local development servers:

| Component | Entry point | Default address |
|---|---|---|
| Backend API | `backend/app/main.py` (`app.main:app`) | `http://127.0.0.1:8000` |
| Backend interactive API docs | FastAPI / Swagger UI | `http://127.0.0.1:8000/docs` |
| Backend OpenAPI schema | FastAPI | `http://127.0.0.1:8000/openapi.json` |
| Frontend | `frontend` (Vite) | `http://localhost:5173` |
| Live tick stream | Backend WebSocket `/ws/ticks` | `ws://localhost:8000/ws/ticks?symbol=EURUSD` |

The frontend makes requests to `/api/...` and opens `/ws/...`. The Vite development server proxies these paths to the backend at `localhost:8000`; therefore, during local development, open the frontend at **`http://localhost:5173`**, not the backend URL.

**MT5 connection model:** the Python backend connects to the MetaTrader 5 desktop terminal running on the same Windows machine. The browser frontend does not connect directly to the broker or MT5.

## Requirements

### Required

- **Windows 10/11** for the full MetaTrader 5 integration. The official Python `MetaTrader5` package is Windows-only.
- **Python 3.12 recommended** (the supplied Windows launcher creates a Python 3.12 virtual environment; backend code requires Python 3.10 or newer).
- **Node.js LTS** and npm.
- **MetaTrader 5 desktop application** installed locally.
- A broker-provided **MetaTrader 5 demo account** and working internet connection for live prices/trading.
- Git (optional, for cloning and version control).

### Python backend packages

Installed from `backend/requirements.txt`:

- FastAPI and Uvicorn
- SQLAlchemy
- NumPy and pandas
- python-dotenv
- httpx, pytest, python-multipart
- MetaTrader5 (installed on Windows only)

### Frontend packages

Installed from `frontend/package.json`:

- React and React DOM
- TypeScript
- Vite and the React Vite plugin
- lightweight-charts

No separate database server is required when using the default SQLite configuration.

## MetaTrader 5 setup

1. Install the **MetaTrader 5 desktop terminal** from your broker or the official MetaTrader 5 distribution.
2. Open MT5 and sign in using a **demo trading account**. You need an MT5 account, not merely a broker website login.
3. Confirm that the terminal is connected and that quotes are updating.
4. Enable the terminal's **Algo Trading** control if you intend to test order execution. Broker/account permissions may also affect trading.
5. Keep MT5 open on the same Windows machine while running the backend.
6. In MT5, make sure the instrument you want to use is available in Market Watch. Broker symbol names can differ (for example, a broker may use a suffix).

### Do I need to put my MT5 account details in `.env`?

Usually, **no**. The preferred setup is to leave the `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, and `MT5_PATH` values empty. The Python integration will initialize the locally installed terminal and use its already logged-in account.

If you need to specify a particular terminal/account, copy `backend/.env.example` to `backend/.env` and fill in the relevant values:

```env
MT5_LOGIN=your_demo_login_number
MT5_PASSWORD=your_demo_password
MT5_SERVER=your_broker_server_name
MT5_PATH=C:\Path\To\terminal64.exe
```

Keep `.env` private. **Never commit account passwords, API keys, or other credentials to GitHub.**

## Installation

Clone the repository, then open a terminal in the project directory (the directory containing `backend` and `frontend`).

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_FOLDER>
```

### 1. Set up the backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks virtual-environment activation, either adjust the current-user execution policy as appropriate or activate from Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

If Python 3.12 is not installed, install it from [python.org](https://www.python.org/downloads/) and ensure the Python launcher is available. Python 3.10+ is required by the backend code, but the included Windows launcher specifically requests Python 3.12.

### 2. Set up the frontend

Open a **second terminal** in the project root:

```powershell
cd frontend
npm install
```

## Running the application

Start the backend first, then the frontend. Keep both terminal windows running.

### Backend

From the project root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend entry target: `app.main:app`  
Backend host: `127.0.0.1`  
Backend port: `8000`

For access from another device on the same trusted network, the bind host can be changed to `0.0.0.0`, but do not expose the trading API publicly without adding authentication, access controls, HTTPS, and appropriate network restrictions.

### Frontend

In a second terminal, from the project root:

```powershell
cd frontend
npm run dev
```

Open:

**http://localhost:5173**

### Windows quick-launch scripts

The repository also includes:

- `run_backend.bat` — creates the backend virtual environment if needed, installs dependencies on first run, creates `.env` from `.env.example`, and starts FastAPI.
- `run_frontend.bat` — installs frontend dependencies if needed and starts Vite.

You can double-click each script or run it from Command Prompt. Start `run_backend.bat` first, then `run_frontend.bat`.

### Verify that the backend is running

Open:

- `http://127.0.0.1:8000/docs` — interactive API documentation.
- `http://127.0.0.1:8000/api/status` — MT5 connection/account status.
- `http://127.0.0.1:8000/api/timeframes` — supported chart timeframes.

A running backend does not necessarily mean MT5 is connected. Check `/api/status` for the actual terminal/account connection state.

## Backend usage

The backend is a FastAPI application. The frontend uses it automatically, but you can also call the API directly from Swagger UI, curl, Postman, or another client.

### Interactive API documentation

Go to **http://127.0.0.1:8000/docs** while the backend is running. Expand an endpoint, choose **Try it out**, provide the required parameters/body, and execute the request.

### Main API routes

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/status` | MT5 terminal/account connection status and trading permission |
| `POST` | `/api/mt5/reconnect` | Attempt to reconnect to the local MT5 terminal |
| `GET` | `/api/timeframes` | List supported chart timeframes |
| `GET` | `/api/symbols` | List MT5 symbols, or symbols available in stored data |
| `GET` | `/api/bars?symbol=EURUSD&tf=M5&count=1000` | Retrieve chart bars from MT5 or stored history |
| `GET` | `/api/tick?symbol=EURUSD` | Get the latest MT5 tick |
| `WS` | `/ws/ticks?symbol=EURUSD` | Stream tick updates over WebSocket |
| `GET` | `/api/data` | List locally stored historical-data inventory |
| `POST` | `/api/data/import?symbol=EURUSD&tf=M5` | Import a historical CSV file |
| `GET` / `PUT` | `/api/settings` | Read or update application settings |
| `GET` / `PUT` | `/api/risk/config` | Read or update risk configuration |
| `POST` | `/api/orders/size` | Calculate volume from account equity, risk setting, and stop loss |
| `POST` | `/api/orders/validate` | Validate an order without submitting it |
| `POST` | `/api/orders` | Submit an order through the execution/risk checks |
| `GET` | `/api/positions` | Retrieve open MT5 positions |
| `POST` | `/api/positions/{ticket}/close` | Request closure of a position |
| `GET` | `/api/strategy/signal?symbol=EURUSD&tf=M5` | Get a model signal for the latest closed bar |
| `GET` | `/api/strategy/results` | Read strategy result data, if generated |
| `GET` | `/api/strategy/comparison` | Read model/config comparison results, if generated |
| `GET` | `/api/strategy/walkforward` | Read walk-forward results, if generated |
| `POST` | `/api/backtest` | Run a backtest on stored historical data |
| `GET` | `/api/auto/status` | Check auto-trader status |
| `POST` | `/api/auto/start` | Start the auto-trader explicitly |
| `POST` | `/api/auto/stop` | Stop it; optionally request closing its positions |
| `POST` | `/api/sim/montecarlo` | Run a Monte Carlo simulation |
| `POST` | `/api/sim/blackscholes` | Run Black–Scholes calculations |
| `POST` | `/api/sim/replay` | Run a strategy replay |
| `POST` | `/api/sim/scenario` | Run a what-if scenario |
| `GET` | `/api/portfolio` | Retrieve portfolio analytics |
| `GET` | `/api/trades` | Retrieve trade-history analytics |

For exact request schemas and optional parameters, use `/docs` or `/openapi.json`; those definitions are the authoritative reference for the running version.

### Example API calls

Check MT5 status:

```bash
curl http://127.0.0.1:8000/api/status
```

Get EURUSD M5 bars:

```bash
curl "http://127.0.0.1:8000/api/bars?symbol=EURUSD&tf=M5&count=500"
```

Reconnect to MT5:

```bash
curl -X POST http://127.0.0.1:8000/api/mt5/reconnect
```

Get the strategy signal:

```bash
curl "http://127.0.0.1:8000/api/strategy/signal?symbol=EURUSD&tf=M5"
```

**Order execution:** use `/api/orders/validate` first, inspect the response, and only then submit to `/api/orders`. A successful HTTP response is not a guarantee that the broker filled the order; inspect the returned execution result and the MT5 terminal.

### Import historical data without MT5

The backend can use stored CSV history if MT5 is disconnected. The import endpoint expects a multipart file upload:

```bash
curl -X POST \
  "http://127.0.0.1:8000/api/data/import?symbol=EURUSD&tf=M5" \
  -F "file=@EURUSD_M5.csv"
```

The CSV must be in a format understood by the project's history parser. MT5-exported bar data is the intended input. After import, use `/api/data` to check the stored inventory and `/api/bars` to retrieve it.

Historical data can support charts, research, and backtesting. It does **not** provide live ticks or enable order execution when MT5 is disconnected.

## Frontend usage

Open **http://localhost:5173** after both servers are running.

The frontend is a Vite development app. Its proxy configuration in `frontend/vite.config.ts` forwards:

- `/api` requests to `http://localhost:8000`
- `/ws` WebSocket connections to `ws://localhost:8000`

Useful frontend scripts:

```bash
npm run dev       # Start the local development server
npm run build     # Type-check and create the production build in frontend/dist
```

The application includes terminal, research, backtesting, simulation, portfolio, trade-history, and settings views. Exact controls and available data depend on whether MT5 is connected and whether the required historical data/model result files exist.

## Historical data and strategy models

### Importing data

Backtesting requires historical bars in the backend database. Import a suitable CSV through `POST /api/data/import` or use the application's data workflow. The backtest endpoint currently requires at least **1,000 stored bars** for the selected symbol/timeframe.

### Training a model

From the `backend` directory, provide a suitable M5 CSV file:

```bash
python train.py EURUSD_M5.csv --tf M5 --steps 3000
```

Supported training timeframes are `M5`, `M15`, and `H1`. M15 and H1 data are resampled from the supplied M5 CSV.

Optional drift-neutral training:

```bash
python train.py EURUSD_M5.csv --tf M5 --steps 3000 --dn
```

The script writes a model under `backend/models/`, for example `strategy_M5.pkl`. The API looks for timeframe-specific model files and, for M5, can also fall back to `models/strategy.pkl`.

### Compare configurations

```bash
python compare.py EURUSD_M5.csv 3000
```

This trains and evaluates multiple timeframe/drift-neutral configurations, selects using validation results, and writes comparison output and a selected model. Review the script's printed output and generated JSON before interpreting the results.

### Walk-forward evaluation

```bash
python walkforward.py EURUSD_M5.csv
```

This is a longer-running evaluation. It writes `models/walkforward.json` for the Research view. Runtime depends on the machine and dataset.

**Model files:** only load `.pkl` model files from sources you trust. Python pickle files can execute code when loaded. Do not download and load untrusted model artifacts.

## Configuration

The backend reads environment variables from `backend/.env`. Start with:

```env
# Leave MT5_* empty to use the already logged-in local terminal.
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
MT5_PATH=

# Safety defaults
DEMO_ONLY=true
ALLOW_REAL_TRADING=false

# Local SQLite database
DB_URL=sqlite:///./data/app.db
```

| Variable | Meaning |
|---|---|
| `MT5_LOGIN` | Optional MT5 account login number |
| `MT5_PASSWORD` | Optional MT5 account password |
| `MT5_SERVER` | Optional broker server name |
| `MT5_PATH` | Optional path to the MT5 terminal executable |
| `DEMO_ONLY` | Blocks real-account trading when `true` |
| `ALLOW_REAL_TRADING` | Explicit real-account opt-in flag; must not be enabled casually |
| `DB_URL` | SQLAlchemy database URL; SQLite is the default |

The default configuration is deliberately demo-only. A real account is blocked unless both `DEMO_ONLY=false` and `ALLOW_REAL_TRADING=true` are configured. Do not change these safeguards for ordinary development or testing.

The database is created automatically on backend startup. With the default URL, it is stored at `backend/data/app.db`.

## Project structure

```text
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point and core API routes
│   │   ├── config.py            # Environment configuration
│   │   ├── db.py                # SQLAlchemy models and database setup
│   │   ├── mt5/                 # MetaTrader 5 gateway
│   │   ├── market_data/         # Historical data import and retrieval
│   │   ├── execution/           # Order execution and auto-trader
│   │   ├── risk/                # Risk validation and position sizing
│   │   ├── strategy/            # Strategy and signal logic
│   │   ├── backtesting/         # Backtest engine and runner
│   │   ├── simulations/         # Simulation implementations
│   │   ├── portfolio/           # Portfolio analytics
│   │   ├── sim_api.py           # Simulation API routes
│   │   └── portfolio_api.py     # Portfolio/trade API routes
│   ├── models/                  # Local trained model artifacts
│   ├── tests/                   # Backend tests
│   ├── requirements.txt
│   ├── .env.example
│   ├── train.py
│   ├── compare.py
│   └── walkforward.py
├── frontend/
│   ├── src/
│   │   ├── components/          # Trading UI components
│   │   ├── pages/               # Terminal, Research, Backtest, etc.
│   │   └── services/            # API client and settings helpers
│   ├── package.json
│   └── vite.config.ts
├── run_backend.bat
├── run_frontend.bat
└── README.md
```

## Troubleshooting

### Frontend says backend is unavailable

- Confirm the backend terminal is still running.
- Open `http://127.0.0.1:8000/docs` to check the API.
- Confirm that Uvicorn is using port `8000`.
- Restart the frontend after changing Vite proxy settings.

### MT5 shows disconnected

- Confirm MT5 is installed, open, and logged in.
- Check that the terminal is connected to the broker and quotes are updating.
- Confirm the backend is running on Windows and that the Python environment installed the `MetaTrader5` package.
- If using explicit credentials, check `backend/.env` and the terminal path.
- Call `POST /api/mt5/reconnect`, then check `GET /api/status`.

### `MetaTrader5 package not installed (Windows only)`

The MetaTrader5 Python package is Windows-only. Run the backend using a supported Windows Python environment and reinstall `backend/requirements.txt` there. Historical CSV features may still be usable without MT5.

### No strategy model / model not found

Train a model using `backend/train.py` or place the required trusted model artifact in `backend/models/`. Ensure the selected timeframe matches the model filename. Some Research result endpoints also require their corresponding JSON output files to have been generated.

### Backtest says not enough stored data

Import a valid historical CSV for the selected symbol and timeframe. The current backtest route requires at least 1,000 stored bars.

### Port already in use

Stop the process already using port `8000` or `5173`, or configure a different server port and update the Vite proxy accordingly.

## Safety notes

- Keep `DEMO_ONLY=true` and `ALLOW_REAL_TRADING=false`.
- Use a demo account for development and testing.
- Auto-trading is not enabled automatically; it must be started explicitly from the application/API.
- The auto-trader has a stop control, but software controls cannot eliminate execution, connectivity, broker, or market risk.
- Backtests and simulations are not guarantees of future performance. Results depend on data quality, assumptions, spread, slippage, and model design.
- Do not expose the backend API directly to the public internet. The current project configuration is a local development setup and does not include production-grade authentication.
- Do not commit `.env`, account credentials, database files containing private information, or untrusted model files.

---

## License

Add the license you intend to use for this repository before distributing or reusing the project. Until a license is added, do not assume that others have permission to reuse, modify, or redistribute the code.
