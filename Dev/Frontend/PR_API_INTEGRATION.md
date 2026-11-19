# Local integration against open PRs

## November 19: PR #38 frontend integration implemented

Rechecked remote main (`14c055ccf72a1c8295e14593061b10c5f95a2a2c`) and PR #38
(`44e9ae3e994c10e526bd25e5fbdf3821721e1c63`, still open). The contract review below
now has frontend implementations in `models/requestApi.js`, `CareRequests.jsx`,
`SupportQueue.jsx` and `Appointments.jsx`. Earlier disabled-capability notes are
historical and no longer describe the frontend.

- Authenticated Help/refill proposals use `request_help` / `request_refill` and
  server read-back. Confirmation validates status, action type and saved request ID.
  A failed command in HTTP 200 is an error, not a successful request.
- Help accepts an optional 300-character summary. Live users receive a submission
  receipt; demo-only Help history remains separate because no own-history API exists.
- Queue fields/statuses match PR #38. Support agents and admins get a separate
  workspace. Poll/manual refresh, claim/resolve and 409 recovery are implemented.
  Live UI offers unresolved filters only, not a fabricated resolved archive.
- Refills map nested medication data, display `status_message`, poll status, prevent
  duplicate open requests and refresh remaining counts after confirmation.
- Appointment cancellation and same-provider rescheduling use the Command pipeline;
  selecting a time never mutates a booking. Successful changes refresh reminders.
- PR #31 intent suggestions route users to the appropriate care form. Help summaries
  can be reviewed before sending; repeated unclear turns offer human assistance.
  STT remains transcribe → editable text → AI → review, with existing TTS controls.

Validation uses mocked HTTP responses matching the pinned schemas: 47 unit tests,
66 Chrome offline browser cases and production build. This is frontend validation,
not PostgreSQL migration/transaction acceptance or actual microphone/OpenAI testing.
Backend files, migrations and remote branches were not changed. Neither local backend
checkout was upgraded in this task; run a backend with PR #38 and merged #31/#34,
apply its migrations in the intended database, and seed it before real acceptance.

Remaining external gaps: older-adult Help progress/history API; care-message AI
proposal (the manual message screen works); real database/voice acceptance. No
automatic refill-ready push is exposed; the implemented read polling checks status.

## November 18: PR #38 contract review (not yet wired locally)

The November 17 missing-contract finding below is superseded by
[PR #38](https://github.com/kunjcr2/CS160_Project/pull/38), by Akiko0210, head
`44e9ae3e994c10e526bd25e5fbdf3821721e1c63`. It is open and unmerged at this check.
The inspected main tree (`14c055ccf72a1c8295e14593061b10c5f95a2a2c`) does not
contain its assistance/refill controllers. PR #31 is merged, but AI intents are
still separate from persisted action proposals.

Verified in controllers, Commands, schemas, and router registration (all paths
below are prefixed with `/api/v1` and use existing Bearer authentication):

| Operation | Verified contract |
| --- | --- |
| Propose Help | `POST /actions`, `action_type: "request_help"`, payload `{older_adult_id, summary, reason: "user_request"}`; summary optional, maximum 300 characters |
| Propose refill | `POST /actions`, `action_type: "request_refill"`, payload `{older_adult_id, medication_id}` |
| Execute/cancel | Existing `POST /actions/{id}/confirm` or `/cancel`; confirm can return HTTP 200 with action status `failed`, so inspect status |
| Refill history | `GET /older-adults/{id}/refills`; each row has nested `medication`, `status`, `status_message`, `created_at` |
| Agent queue | `GET /assistance/queue`; only unresolved requests, oldest first; `support_agent` and `admin` allowed |
| Take/resolve | `PATCH /assistance/{id}`, body `{status: "in_progress"}` or `{status: "resolved"}`; conflicting claims can return 409 |

Local differences to address before enabling live mode:

- `careRequests.js` still disables all three live capabilities. Demo action types
  are not backend types. Add authenticated adapters and validate returned actions.
- Help uses a 500-character required summary locally; the backend allows an optional
  300-character summary and permits only one unresolved request per older adult.
- Help status is `open`, not local `waiting`. Queue fields are `older_adult_name`
  and `assigned_to_name`, not `display_name` and `assigned_to`. The response has
  no agent ID; do not infer ownership from a displayed name.
- The live queue does not provide resolved history. The demo's Resolved/All filters
  must not imply a complete live archive. Admin access needs a matching workspace.
- Refills use `requested`, `in_progress`, `ready`, not local `submitted`; names and
  doses are nested under `medication`. Show the backend's `status_message` and
  refresh medication counts after successful confirmation (one refill is consumed).
- **No older-adult Help history/detail endpoint exists in this PR.** The local
  `listHelpRequests()` history is demo-only. Do not call the agent-only queue as an
  older adult. Request a read endpoint, or show only the confirmed submission receipt
  until one exists; ongoing progress/history cannot be verified from that receipt.
- Pharmacy behavior is still simulated by the backend. No ready notification is
  implemented; status reads refresh the mock pharmacy's progress.

This review does not enable capabilities or alter application behavior. The primary
local backend checkout also predates these feature controllers. Running PR #38
requires its normal backend setup and both new migrations in an intended local
database. No migrations, merges, pushes or remote comments were performed here.
PR #20 still points to `1c1814a`; the newer messaging and three-screen work remains
uncommitted in this local checkout, so those screens are not on PR #20 yet.

## November 17: Help, support queue and refill screens

Inspected the GitHub main tree at `9c9a2c0db3c609c81c8c647d1f4b21e2036c5b5f`,
[PR #31](https://github.com/kunjcr2/CS160_Project/pull/31) tools at
`45c6d7d038892aed0acab94fd6bbad0a92ad0cb5`, and PR #34's mounted routers at
`01fc2e789616c33bf95ebfcb85a15b1b019ff958`. No implemented Help, support queue or
refill route/Command was found. PR #31 `refill` and `human_help` proposals are
validated AI intents, not saved actions. They now produce a readable availability
notice instead of an invalid confirmation or a fabricated action ID.

The three screens and their demo workflows are implemented. Live adapters return
`service_unavailable` without a network write. Capability flags are false for live
and true only for the explicit demo adapter. The demo action types
`demo_request_help` / `demo_request_refill`, queue statuses `waiting` /
`in_progress` / `resolved`, and refill status `submitted` are frontend fixtures,
**not agreed backend schemas**. No backend source or migration was changed.

Before live integration, the backend owner must provide:

| Area | Contract still needed |
| --- | --- |
| Help | Persisted proposal/confirmation payload, consented summary limit, own-request list and status schema |
| Support queue | Agent authorization, queue/filter schema, atomic claim/resolve behavior, assignment ownership, conflict response and polling/push delivery |
| Refills | Actual refill Command payload, medication eligibility/count semantics, history/status schema, duplicate handling and failure result |

The existing `GET /api/v1/older-adults/{id}/medications` is used to display real
medications. Missing `refills_remaining` means unknown, never assumed eligible.
The no-refills path opens the already implemented PB-07 doctor-message form and
still requires provider selection, review and confirmation. Caregiver patient
selection is not implemented and caregiver IDs are never used as patient IDs.

Manual demo acceptance: confirm a Help request, take/resolve it through **Preview
support queue**, return to Help and refresh history; cancel/confirm a Lisinopril
refill; select Metformin (zero refills) and open the editable doctor message.
Demo state resets on page reload. This is UI/demo acceptance only; real support
handoff, pharmacy integration, persistence and live API authorization remain untested.

Validation: 40 unit tests, all 52 Chrome offline browser tests, and the production
build passed. New cases cover confirm/cancel, expired proposals, duplicate refills,
queue state transitions and failed-update recovery, unavailable live services,
unknown refill counts, role isolation, and 320px/larger-text layout. The browser
screenshots were inspected; API responses are mocked and requests are demo-only.

## November 16: care-message contract

The frontend now also targets [PR #34](https://github.com/kunjcr2/CS160_Project/pull/34),
head `01fc2e789616c33bf95ebfcb85a15b1b019ff958`. This PR has not been merged into
the local integration checkout described below. Run that backend branch (with
its normal setup and `alembic upgrade head`) to test the new messaging screen.
The existing local medication/speech patches are not part of this frontend change.

- `POST /api/v1/actions`: `action_type: "send_care_message"`,
  `payload: {older_adult_id, provider_id, body}`; body limit 2,000 characters.
- Show `summary_text`, then explicitly confirm/cancel the returned action ID.
- `GET /api/v1/older-adults/{id}/messages`: array of
  `{id, provider, body, status, created_at}`; status is `sent` or `failed`.
- Delivery failure may return HTTP 200 with `action.status="executed"` and
  `action.result={ok:false,message_id,...}`. The frontend treats this as failure.
- PR #34 uses a mock messaging provider; the UI does not imply real delivery.
- This screen uses the current older adult's profile ID. Caregiver selection,
  replies/read receipts, and AI/voice care-message proposals are outside this change.

Frontend verification: 33 unit tests, 43 Chrome offline browser tests and a
production build passed. Responses are mocked; no PostgreSQL acceptance or real
message delivery is claimed. No backend files were changed for this screen.

## November 14: earlier integration snapshot

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
- No implemented Help, queue or refill endpoint was found in these earlier
  fetched PR heads. Care messaging is now covered separately by PR #34 above.
- Account registration, caregiver management and adding medication are not part
  of the current older-adult frontend workflow.
