# 📈 AI Stock Analysis Tool (FastAPI)

A real-time stock charting and AI-powered analysis web application built with **FastAPI**. It supports multi-market stock search (US / KR / HK), interactive candlestick charts with technical indicators and harmonic pattern detection, and deep AI analysis powered by **Google Gemini**.

---

## Table of Contents

- [System Architecture](#system-architecture)
  - [Tech Stack](#tech-stack)
  - [Project Structure](#project-structure)
  - [Module Overview](#module-overview)
- [Process Flow](#process-flow)
  - [Stock Search & Chart Loading](#1-stock-search--chart-loading)
  - [AI Analysis (SSE Streaming)](#2-ai-analysis-sse-streaming)
  - [DCF Analysis (SSE Streaming)](#3-dcf-analysis-sse-streaming)
  - [Telegram Notification](#4-telegram-notification)
  - [Authentication](#5-authentication-google-oauth)
- [Server Startup](#server-startup)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Installation](#installation)
  - [Running the Server](#running-the-server)
- [UI Usage Guide](#ui-usage-guide)
  - [Sidebar — Stock Search](#1-sidebar--stock-search)
  - [Chart Area](#2-chart-area)
  - [Indicators Panel](#3-indicators-panel)
  - [AI Analysis Section](#4-ai-analysis-section)
  - [Telegram Integration](#5-telegram-integration)

---

## System Architecture

### Tech Stack

| Layer        | Technology                                                |
| ------------ | --------------------------------------------------------- |
| **Backend**  | Python 3.10+, FastAPI, Uvicorn                            |
| **AI Model** | Google Gemini 2.5 Flash (via `google-genai` SDK)          |
| **Data**     | yfinance (market data & news), pandas, numpy              |
| **Charts**   | Plotly.js (client-side rendering)                         |
| **Auth**     | Google OAuth 2.0 (Authlib) + JWT (PyJWT)                  |
| **Alerts**   | Telegram Bot API                                          |
| **Frontend** | Vanilla HTML / CSS / JavaScript (Single Page Application) |

### Project Structure

```
FastAPI/
├── main.py                      # Application entry point (FastAPI app setup)
├── requirements.txt             # Python dependencies
├── .gitignore
│
├── routers/                     # API route handlers
│   ├── __init__.py
│   ├── stock.py                 # Stock data & search endpoints
│   ├── analysis.py              # AI / DCF analysis endpoints (SSE)
│   ├── auth.py                  # Google OAuth login/logout endpoints
│   └── telegram.py              # Telegram message sending endpoint
│
├── services/                    # Business logic layer
│   ├── __init__.py
│   ├── stock_service.py         # Data loading, indicators, harmonic pattern detection
│   ├── analysis_service.py      # Gemini AI prompt construction & API calls
│   ├── search_service.py        # Multi-market stock search (US/KR/HK)
│   ├── auth_service.py          # OAuth config, JWT token management
│   └── telegram_service.py      # Telegram Bot API integration
│
├── static/                      # Frontend assets (served at /static)
│   ├── index.html               # Main SPA page
│   ├── app.js                   # Client-side logic (chart, search, analysis)
│   └── style.css                # Styling (dark theme, responsive)
│
├── data/                        # Static data files
│   └── krx_stocks.csv           # Korean Exchange (KRX) stock list
│
└── prompt/                      # Reference prompt documents
    ├── harmonic pattern(ab=cd).md
    └── harmonic pattern 3 - 5-0와 Reciprocal AB=CD.md
```

### Module Overview

#### Routers (API Layer)

| Router                | Prefix          | Description                                           |
| --------------------- | --------------- | ----------------------------------------------------- |
| `routers/stock.py`    | `/api/stock`    | Stock search, OHLCV data + indicators, news retrieval |
| `routers/analysis.py` | `/api/analysis` | AI & DCF analysis via Server-Sent Events (SSE)        |
| `routers/auth.py`     | `/api/auth`     | Google OAuth 2.0 login, callback, user info, logout   |
| `routers/telegram.py` | `/api/telegram` | Send analysis results to Telegram                     |

#### Services (Business Logic Layer)

| Service                        | Responsibility                                                                                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `services/stock_service.py`    | Downloads OHLCV data via yfinance, computes RSI / SMA / Bollinger Bands, detects AB=CD harmonic patterns, converts DataFrame to Plotly-compatible JSON |
| `services/analysis_service.py` | Constructs compact prompts (harmonic guide + DCF guide) and calls Gemini 2.5 Flash for AI & DCF analysis                                               |
| `services/search_service.py`   | Multi-market stock search — US (yfinance search), KR (local CSV + yfinance fallback), HK (built-in list)                                               |
| `services/auth_service.py`     | Manages Google OAuth 2.0 configuration, JWT token creation and verification (24h expiry)                                                               |
| `services/telegram_service.py` | Sends messages via Telegram Bot API with automatic chunking for long messages (4000 char limit)                                                        |

---

## Process Flow

### 1. Stock Search & Chart Loading

```
┌──────────┐    GET /api/stock/search?q=apple&market=US    ┌──────────────┐
│  Browser  │ ──────────────────────────────────────────▶  │  stock.py     │
│ (app.js)  │ ◀──────────────────────────────────────────  │  (Router)     │
│           │    { results: [{symbol, name, market}] }     └──────┬───────┘
│           │                                                     │
│           │    GET /api/stock/data?symbol=AAPL&period=1y         ▼
│           │ ──────────────────────────────────────────▶  ┌──────────────┐
│           │                                              │ stock_service │
│           │                                              │  .load_data() │
│           │                                              │  + indicators │
│           │                                              │  + harmonic   │
│           │ ◀──────────────────────────────────────────  │  detection    │
│           │    { dates[], ohlc[], rsi[], sma[],           └──────────────┘
│           │      bollinger{}, harmonic_pattern{},
│           │      company_name }
│           │
│           │    GET /api/stock/news?symbol=AAPL
│           │ ──────────────────────────────────────────▶  News via yfinance
└──────────┘
```

**Steps:**

1. User types a stock name → 300ms debounce triggers autocomplete search (`/api/stock/search`)
2. User selects a stock → full chart data request (`/api/stock/data`)
3. Backend downloads OHLCV data via yfinance, computes technical indicators (RSI-14, SMA-20, Bollinger Bands), detects AB=CD harmonic patterns
4. Frontend renders a Plotly candlestick chart with overlaid harmonic pattern (if detected)
5. News is fetched in parallel (`/api/stock/news`) and displayed in the sidebar

### 2. AI Analysis (SSE Streaming)

```
┌──────────┐   GET /api/analysis/ai/stream?symbol=AAPL&period=1y&news_text=...
│  Browser  │ ─────────────────────────────────────────────────────────────────▶
│ (SSE)     │
│           │ ◀── event: step  { step:1, label:"Loading data...",    status:"running" }
│           │ ◀── event: step  { step:1, label:"Data loaded",        status:"done", elapsed:1.2 }
│           │ ◀── event: step  { step:2, label:"Preparing data...",  status:"running" }
│           │ ◀── event: step  { step:2, label:"Data prepared",      status:"done", elapsed:0.1 }
│           │ ◀── event: step  { step:3, label:"Calling Gemini...",  status:"running" }
│           │ ◀── event: step  { step:3, label:"AI analysis done",   status:"done", elapsed:8.5 }
│           │ ◀── event: step  { step:4, label:"Complete (9.8s)",    status:"done" }
│           │ ◀── event: result { content:"...", confidence_score:92, analysis_type:"AI" }
└──────────┘
```

**Steps:**

1. The frontend opens an `EventSource` connection to the SSE endpoint
2. Backend streams progress events for each step (data loading → indicator calculation → Gemini API call → completion)
3. The UI displays animated step indicators with elapsed time
4. Final result contains the full AI analysis report (technical analysis + harmonic pattern interpretation + news sentiment + trading strategy)

### 3. DCF Analysis (SSE Streaming)

Same SSE pattern as AI analysis, but the prompt instructs Gemini to perform a **Discounted Cash Flow (DCF)** valuation:

- **Step 1:** Load stock OHLCV data
- **Step 2:** Retrieve company information (name, fundamentals) via yfinance
- **Step 3:** Call Gemini with the compact DCF prompt (Narrative → Reverse DCF → Forward DCF → Comps → Sensitivity → So What)
- **Step 4:** Stream the final result with 10 Key Points format

### 4. Telegram Notification

```
┌──────────┐    POST /api/telegram/send                    ┌──────────────────┐
│  Browser  │ ──────────────────────────────────────────▶  │  telegram.py      │
│           │    { message: "analysis content..." }        │  → telegram_svc   │
│           │ ◀──────────────────────────────────────────  │  → Telegram API   │
│           │    { success: true }                         └──────────────────┘
└──────────┘
```

After an analysis completes, users can forward the result to their Telegram chat with a single button click. Long messages are automatically split into 4000-character chunks.

### 5. Authentication (Google OAuth)

```
Browser → GET /api/auth/login → Redirect to Google OAuth consent screen
Google  → GET /api/auth/callback → Server creates JWT → Set HttpOnly cookie → Redirect to /
Browser → GET /api/auth/me → Returns { logged_in, email, name }
Browser → POST /api/auth/logout → Delete cookie
```

- OAuth 2.0 flow via **Authlib** with OpenID Connect
- JWT tokens (HS256, 24h expiry) stored in HttpOnly cookies
- Session middleware required for OAuth state management

---

## Server Startup

### Prerequisites

- **Python 3.10+** installed
- **pip** package manager
- A **Google Gemini API Key** ([Get one here](https://aistudio.google.com/app/apikey))
- _(Optional)_ Google OAuth 2.0 credentials for login feature
- _(Optional)_ Telegram Bot Token and Chat ID for notification feature

### Environment Variables

Create a `.env` file in the **parent directory** of `FastAPI/` (i.e., at the project root `ChartTool/.env`):

```env
# Required — Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# Optional — Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
REDIRECT_URI=http://localhost:8000/api/auth/callback

# Optional — JWT Secret (defaults to a built-in value if not set)
JWT_SECRET=your_jwt_secret_key

# Optional — Telegram Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

> **Note:** The application loads `.env` from `Path(__file__).parent.parent / ".env"`, which resolves to the directory one level above `FastAPI/`.

### Installation

```bash
# Navigate to the FastAPI directory
cd FastAPI

# Create and activate a virtual environment (recommended)
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Server

```bash
# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: **http://localhost:8000**

| Option     | Description                                 |
| ---------- | ------------------------------------------- |
| `--reload` | Auto-restarts the server on code changes    |
| `--host`   | Bind address (`0.0.0.0` for all interfaces) |
| `--port`   | Port number (default: `8000`)               |

The interactive API documentation is available at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## UI Usage Guide

The application follows a **sidebar + main content** layout optimized for both desktop and mobile.

### 1. Sidebar — Stock Search

| Element             | Description                                                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Google Login**    | Click the "Google 로그인" button to authenticate via Google OAuth 2.0                                                                                              |
| **Market Selector** | Dropdown to choose the target market: 🇺🇸 **US**, 🇰🇷 **KR** (Korea), 🇭🇰 **HK** (Hong Kong)                                                                          |
| **Ticker Input**    | Type a stock name or ticker symbol. An autocomplete dropdown appears after 300ms of typing. Use **↑/↓ arrow keys** to navigate suggestions and **Enter** to select |
| **Period Selector** | Choose the chart data range: 1 month, 3 months, 6 months, 1 year (default), or 2 years                                                                             |
| **Search Button**   | Click to load the selected stock's chart and data                                                                                                                  |
| **News Panel**      | Displays recent news articles for the selected stock (fetched from yfinance)                                                                                       |

> **Mobile:** Tap the **☰** hamburger button at the top-left corner to toggle the sidebar.

### 2. Chart Area

- **Candlestick Chart** — Displays OHLCV (Open, High, Low, Close, Volume) data via Plotly.js
- **Technical Overlays:**
  - **SMA-20** (Simple Moving Average) — yellow line
  - **Bollinger Bands** (Upper / Lower) — boundary band overlay
- **Harmonic Pattern Overlay** (when detected):
  - **A → B → C → D** connected with dashed lines
    - Bullish patterns: **cyan** lines
    - Bearish patterns: **red** lines
  - Each pivot point is labeled (A, B, C, D)
  - **PRZ (Potential Reversal Zone)** is highlighted as a semi-transparent rectangle
- **Dynamic Title** — Automatically shows the company name and ticker: `📈 {Company Name} ({TICKER}) Real-time Chart & AI Analysis`

### 3. Indicators Panel

Located to the right of the chart (or below on mobile), this panel displays:

| Card                 | Content                                                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Current Price**    | Latest closing price of the selected stock                                                                                          |
| **RSI (14)**         | Relative Strength Index — values above 70 indicate overbought, below 30 indicate oversold                                           |
| **Harmonic Pattern** | Detected pattern type (e.g., "Bullish AB=CD") with C-retracement and BC-extension ratios. Shows "No pattern detected" if none found |

### 4. AI Analysis Section

Two analysis modes are available (buttons activate after stock data is loaded):

#### 🤖 AI Analysis

- Performs a comprehensive **technical analysis** using Gemini AI
- Covers: current price position, RSI interpretation, Bollinger Band analysis, harmonic pattern PRZ scenarios, news sentiment impact, and a complete trading strategy (entry, target, stop-loss)
- Progress is displayed as animated step indicators with elapsed time per step

#### 💰 DCF Analysis

- Performs a **Discounted Cash Flow valuation** using Gemini AI
- Output follows a structured "10 Key Points" format:
  1. Final Verdict
  2. Narrative Definition
  3. Reverse DCF Insight
  4. Reality Check
  5. DCF Fair Value
  6. Comparables Conclusion
  7. Key Variables
  8. What the Market Is Missing
  9. Biggest Risk
  10. Upside Catalyst
- Includes probability-weighted fair value (Bull/Base/Bear scenarios)

#### Analysis Progress Display

When an analysis is running, a step-by-step progress UI is shown:

```
✅ Step 1: Data Loading          (1.2s)
✅ Step 2: Data Preparation      (0.1s)
⏳ Step 3: Calling Gemini AI...  (running)
○  Step 4: Complete
```

Each step transitions from ⏳ (running) to ✅ (done) with the elapsed time.

### 5. Telegram Integration

After any analysis completes, click the **📨 "텔레그램으로 전송하기"** (Send to Telegram) button to forward the full analysis report to your configured Telegram chat. A toast notification confirms success or failure.

> **Prerequisite:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` must be set in the `.env` file.

---

## API Reference

| Method | Endpoint                   | Description                                                     |
| ------ | -------------------------- | --------------------------------------------------------------- |
| GET    | `/`                        | Serves the main SPA page (`index.html`)                         |
| GET    | `/api/stock/search`        | Search stocks by name or ticker (`q`, `market`)                 |
| GET    | `/api/stock/data`          | Get OHLCV data + indicators (`symbol`, `period`)                |
| GET    | `/api/stock/news`          | Get recent news for a stock (`symbol`)                          |
| GET    | `/api/analysis/ai/stream`  | AI technical analysis via SSE (`symbol`, `period`, `news_text`) |
| GET    | `/api/analysis/dcf/stream` | DCF valuation analysis via SSE (`symbol`, `period`)             |
| GET    | `/api/auth/login`          | Initiate Google OAuth login                                     |
| GET    | `/api/auth/callback`       | Google OAuth callback handler                                   |
| GET    | `/api/auth/me`             | Get current user info                                           |
| POST   | `/api/auth/logout`         | Logout (clear auth cookie)                                      |
| POST   | `/api/telegram/send`       | Send a message to Telegram (`message`)                          |

---

## License

This project is for personal/educational use.
