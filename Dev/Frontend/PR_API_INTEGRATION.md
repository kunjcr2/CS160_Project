# Local integration against open PRs

Checked from fetched Git refs on November 13–14, 2026. These are development
contracts, not a guarantee that the final merged API will remain unchanged.

| Source | Pinned head | Used for |
| --- | --- | --- |
| main | 19ee658 | Already contains #5 and #16 |
| #11 | eddb086 | Proposal, pending recovery, confirm/cancel |
| #12 | e07e1d9 | Providers, slots, upcoming appointments |
| #13 | 666045a | Notification feed and reminder worker |
| #14 | 4bbd15d | Appointment reminder lifecycle |
| #15 | b9bb57e | Combined backend stack and tests |
| #17 | dc6376f | Login, refresh, sessions |
| #18 | babec7c | Pairing, access and consent |
| #19 | f8f6e13 | Shared mock healthcare provider |
| #21 | cacedf8 | Medication schedules, doses, Taken/Missed |

`pr/21` is already an ancestor of `pr/15`. It is unnecessary to copy individual
controllers or combine migrations by hand.

The frontend-only changes are in the normal `CS160_Project` checkout, branch
`frontend/conversation-ui`. The sibling `CS160-api-integration` checkout, branch
`integration/frontend-pr-apis`, combines that frontend base with PR #15 and has
the current frontend files copied into it. Its backend-only integration patches:

- Register MedicationReminderSource in the shared worker/feed and implement
  recent_for_user with user/time-window filtering and current statuses.
- Keep notification sentences in views/messages.py, including taken/missed wording.
- Accept content_type in the real STT adapter to match the upload endpoint.

These patches are local; do not push the combined integration branch into PR #20.
The backend owners can review them separately. No remote comments or PRs were sent.

## Running the combined checkout

From the sibling integration checkout, follow Dev/Backend/README.md to create a
virtual environment, install requirements-dev.txt, and configure a fresh local
PostgreSQL 18 database. Keep its test database separate. Set a random JWT_SECRET,
COOKIE_SECURE=false for localhost, and RUN_REMINDER_WORKER=true for due reminders.
No environment file or database credentials are copied into Git.

Run migrations and the existing seed script only against that intended database:

```powershell
cd Dev/Backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5000
```

In a second terminal, use either checkout's frontend (same code):

```powershell
cd Dev/Frontend
npm ci
$env:VITE_DATA_MODE = 'live'
npm run dev
```

Sign in with a seeded/test account or pairing code issued by the actual backend.
Select a provider and time, review, confirm, then inspect the upcoming list.
Check sent medication reminders, Taken/Missed, appointment OK and automatic missed.
The local test run has not established PostgreSQL migration/concurrency or real
OpenAI/microphone acceptance. Browser tests intercept API responses. The additional
backend `integration_checks` use mocked database rows/OpenAI and exercise the real
FastAPI routes/schema serialization without connecting to PostgreSQL.

## Remaining integration work

- PR #5 still returns AI intent rather than a saved pending_action. The explicit
  doctor/slot selection flow works around this gap using existing APIs; natural
  language alone cannot finish booking yet.
- FAKE_AI TTS returns placeholder bytes, not playable MP3. Real voice acceptance
  requires configured OpenAI and a real microphone/browser playback test.
- The medication worker now processes existing doses in this local integration;
  periodic replenishment beyond the initial generated horizon needs backend review.
- No implemented Help, queue, care-message or refill endpoint was found in these
  fetched PR heads. Those screens should use a later agreed contract.
- Account registration, caregiver management and adding medication are not part
  of the current older-adult frontend workflow.
