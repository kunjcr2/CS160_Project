# Development Quick Start

Run the backend and frontend in separate PowerShell terminals.

## Terminal 1 — Flask backend

```powershell
cd Dev/Backend
./.venv/bin/python.exe app.py
```

Backend health endpoint: <http://127.0.0.1:5000/api/health>

## Terminal 2 — React frontend

```powershell
cd Dev/Frontend
npm run dev
```

Frontend: <http://127.0.0.1:5173>

The page automatically calls the backend health endpoint and shows whether the service is healthy or unreachable.
