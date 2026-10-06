# Backend

FastAPI backend for the Voice Assistant for Older Adults, organized as MVC (see `plan.md` §4 and §11).

## Prerequisites

- Python 3.12 or newer (everyone on the team uses the same minor version)
- PostgreSQL running locally (no Docker), with `psql`

## 1. Create the databases (once)

```sql
-- in psql as the postgres superuser
CREATE USER cs160 WITH PASSWORD 'choose-a-password';
CREATE DATABASE voice_assistant OWNER cs160;
CREATE DATABASE voice_assistant_test OWNER cs160;
```

## 2. Set up the environment (once)

macOS / Linux:

```bash
cd Dev/Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then edit .env with your password
```

Windows PowerShell:

```powershell
cd Dev/Backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env   # then edit .env with your password
```

Never commit `.env`. It is in `.gitignore`.

## 3. Apply database migrations

```bash
alembic upgrade head
```

Schema changes only through Alembic (plan §25, rule 14). After changing a model in `app/model/entities/`:

```bash
alembic revision --autogenerate -m "describe the change"
# read the generated file in alembic/versions/ before applying it
alembic upgrade head
```

## 4. Run the server

```bash
uvicorn app.main:app --reload --port 5000
```

- Health check: <http://127.0.0.1:5000/api/health>
- Interactive API docs (the API contract): <http://127.0.0.1:5000/docs>

## 5. Test and lint

```bash
pytest
ruff check .
ruff format .
```

## Project structure (MVC)

```text
app/
├── main.py           # FastAPI app + composition root
├── config.py         # settings from .env
├── db.py             # engine + session
├── controllers/      # CONTROLLER: thin routers (conversation/ = orchestrator + dialog states)
├── views/            # server VIEW: schemas/, messages.py (all user-facing text)
├── model/            # MODEL: entities/, commands/, services/, subscribers/, repositories/
├── adapters/         # external systems behind interfaces: healthcare/, llm/, speech/
└── workers/          # reminder worker
alembic/              # migrations
scripts/seed.py       # demo data (Margaret)
tests/
```
