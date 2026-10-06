# Development Quick Start

Run the backend and frontend in separate terminals. First-time backend setup (PostgreSQL, virtual environment, `.env`, migrations) is in `Backend/README.md`.

## Terminal 1 — FastAPI backend

macOS / Linux:

```bash
cd Dev/Backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 5000
```

Windows PowerShell:

```powershell
cd Dev/Backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 5000
```

Backend health endpoint: <http://127.0.0.1:5000/api/health> · API docs: <http://127.0.0.1:5000/docs>

## Terminal 2 — React frontend

```bash
cd Dev/Frontend
npm run dev
```

Frontend: <http://127.0.0.1:5173>

The page automatically calls the backend health endpoint and shows whether the service is healthy or unreachable.
