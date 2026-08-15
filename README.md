# Vanguard-X

Autonomous web exploration tool. A Playwright-driven crawler walks a target site
while a FastAPI backend streams findings (console errors, failed requests,
broken images) over WebSocket to a React dashboard.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | Verified on 3.14 |
| Node.js | 18+ | Verified on 25.9 / npm 11.9 |

I have used NVIDIA - nemotron-3-ultra MODEL — see [LLM configuration](#llm-configuration).

---

## Setup

Two terminals: one for the backend, one for the frontend.

### 1. Backend

```bash
cd backend

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt

# REQUIRED: pip installs the Playwright library but not the browser binaries.
# Skipping this gives "Executable doesn't exist at ...chrome.exe" at run time.
playwright install chromium

cp .env.example .env      # Windows: copy .env.example .env
```

Then start it:

```bash
python main.py
```

Confirm it is up:

```bash
curl http://localhost:8000/health
# {"status":"ok","active_sessions":0,"websocket_clients":0}
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

Opens <http://localhost:3000>. The header chip should read **Connected**.

### 3. Run an exploration

Enter a start URL, set depth and max time, click **Start Exploration**.
Findings stream into the right-hand panel as they are detected.

A Chromium window opens by default so you can watch it. Set `HEADLESS=true` in
`.env` to run it invisibly.

---

## LLM configuration

I used NVIDIA - nemotron-3-ultra model

BASE_URL = https://openrouter.ai/api/v1
MODEL = nvidia/nemotron-3-ultra-550b-a55b:free


Set these in `backend/.env`:

```ini
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-v1-...
OPENAI_MODEL=openai/gpt-4o-mini
```

**OpenRouter model ids must be namespaced** (`vendor/model`). A bare
`gpt-4o-mini` returns 404 there. Confirm an id is live before relying on it:

```bash
curl -s https://openrouter.ai/api/v1/models | grep -o '"id":"[^"]*"' | head -40
```

If the endpoint is unreachable or the key is wrong, the engine logs the error,
disables LLM analysis after 3 consecutive failures, and completes the run
without it. It will not spam one error per step.

> Note: `analyze_state()` currently computes an analysis that
> `decide_next_action()` does not consume — element choice is still random. A
> working key therefore does not yet change exploration behaviour.

---

## Platform notes

**Windows: hot reload is disabled on purpose.** uvicorn selects the event loop in
`uvicorn/loops/asyncio.py`:

```python
if sys.platform == "win32" and not use_subprocess:
    return asyncio.ProactorEventLoop
return asyncio.SelectorEventLoop
```

`use_subprocess` is true whenever reload or multiple workers are enabled, so
`--reload` forces a `SelectorEventLoop` on Windows. That loop cannot spawn
subprocesses, and Playwright launches the browser as one — so every exploration
fails with `NotImplementedError` before the browser opens. Reload and Playwright
are mutually exclusive on Windows.

`RELOAD=true` enables it on Linux/macOS; on Windows it is ignored with a warning.

**Corporate networks.** Some proxies (e.g. Zscaler) block LLM aggregators under a
"Generative AI and ML Applications" category. If `curl https://openrouter.ai`
returns a proxy block page instead of JSON, the endpoint is unavailable on that
network — request an exception or use a different provider.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `NotImplementedError` in `_make_subprocess_transport`; browser never opens | Windows `SelectorEventLoop` (reload enabled) | Run `python main.py` with reload off (the default) |
| `Executable doesn't exist at ...chrome.exe` | Browser binaries not downloaded | `playwright install chromium` |
| Backend exits instantly, no error | `uvicorn.run(app, reload=True)` needs an import string | Fixed; use `python main.py` |
| `'str' object has no attribute 'content'` | `llm.agenerate([prompt])` needs `List[List[BaseMessage]]` | Fixed; uses `ainvoke` |
| Findings repeat many times | `get_page_state()` returns a rolling window of an append-only log | Fixed; findings are deduped by content |
| Findings show "Invalid Date" | Backend sent `created_at`, UI read `timestamp` | Fixed; payload carries both |
| Dashboard reconnects in a loop | Inline callbacks changed `useWebSocket`'s deps every render | Fixed; callbacks held in a ref |
| 410 `github_models_retirement_brownout` | GitHub Models is retired | Use another provider |
| Exploration runs past "Max Time" | `max_time` was collected but ignored | Fixed; the loop honours the budget |

---

## Docker

`docker-compose.yml` and both Dockerfiles exist but are **not verified**, and have
two known problems:

- `backend/Dockerfile` uses `python:3.9-slim`, older than current dependencies require.
- `frontend/Dockerfile` runs `npm run build` before compose supplies
  `REACT_APP_API_URL`; Create React App inlines env vars at build time, so that
  value never reaches the bundle.

Use the local setup above.

---

## Layout

```
backend/
  main.py                 FastAPI app, WebSocket hub, session endpoints
  exploration_engine.py   Exploration loop, findings detection, LLM analysis
  browser_automation.py   Playwright wrapper
  models.py, database.py  SQLAlchemy models and SQLite setup
  .env.example            Configuration template
frontend/src/
  components/Dashboard.tsx      Top-level view, WebSocket message handling
  components/ControlPanel.tsx   Run configuration
  components/FindingsPanel.tsx  Findings list
  hooks/useWebSocket.ts         Reconnecting WebSocket client
  services/api.ts               REST client
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service banner |
| GET | `/health` | Liveness, active session and client counts |
| POST | `/api/explore/start` | Start a run; returns `session_id` |
| WS | `/ws/{session_id}` | Streams `status`, `state_update`, `finding`, `complete`, `error` |

`services/api.ts` also declares `stopExploration`, `getSessionStatus`, and
`healthCheck`. Only `/health` exists on the backend; the stop and status
endpoints are not implemented, so those two calls would 404. Nothing in the UI
invokes them today.
