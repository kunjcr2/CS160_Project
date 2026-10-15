# Care Companion Frontend

Sprint 2 conversation screen, confirmation card, and medication/appointment reminders.

## Run Locally

```powershell
cd Dev/Frontend
npm ci
npm run dev
```

Open the URL printed by Vite (normally <http://127.0.0.1:5173>). Local development
defaults to **demo mode**, with a visible sample-data notice. No backend, database,
API key, or real patient data is needed. Demo changes live only in memory and reset
on reload. The collapsed Demo controls can reset reminders, simulate a server-side
missed dose, or fail the next request once to exercise retry behavior.

## Implemented

- Conversation history, typed messages, waiting state and retry without duplicated messages.
- Explicit confirmation/cancellation; a proposal blocks new messages until resolved.
- Medication Taken/Missed buttons only for `sent`; no optimistic success or duplicate submissions.
- Appointment reminders use OK and `acknowledged`, separately from medication reminders.
- UTC timestamps rendered in the browser's local timezone, including DST.
- Incoming reminder changes replace matching rows; new data is fetched on window focus.
- 404/409 handling, retryable connection errors, and malformed-response rejection.
- Keyboard controls, live announcements, 48px minimum buttons, larger text and responsive layout.

## Live Integration Status

On October 15 the fetched `origin/main` was `ecb0277`. Its FastAPI app only mounts
`/api/health`. The conversation, action and notification controllers are not in
that checkout. **Live end-to-end integration is not verified.** Team chat supplied
the medication contract; the notification envelope, action responses, auth and SSE
details below are provisional and must be compared with the merged FastAPI `/docs`.

Use `.env.local` with `VITE_DATA_MODE=live` to enable the HTTP adapter, then restart
Vite. Production builds default to live unless `VITE_DATA_MODE=demo` is explicitly
set during the build. Live failures never fall back to demo data.

Configuration (also listed in `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_DATA_MODE` | demo in dev, live in build | Explicit data source |
| `VITE_NOTIFICATIONS_PATH` | `/notifications` | Confirm full prefix with akiko; use `/api/v1/notifications` if needed |
| `VITE_NOTIFICATION_STREAM_PATH` | empty | Optional SSE URL after confirming its contract |

Vite proxies `/api` and `/notifications` to `http://127.0.0.1:5000`.
Production hosting needs equivalent routing. No polling timer is assumed while
the team finalizes delivery. With SSE unset, users can refresh and window focus
also refreshes. With SSE enabled, opening/reconnecting or receiving `message`,
`notification`, or `reminder_updated` triggers a GET snapshot. SSE payloads are
not applied directly. Other event names or transports need adapter changes.
Connections are closed on unmount. This does not provide notifications with the app closed.

### Notification Contract to Confirm

The adapter accepts a JSON array or `{ "notifications": [...] }`. Recognized kinds
are `medication_reminder` and `appointment_reminder`. A provisional example:

```json
{
  "id": "notification-uuid",
  "kind": "medication_reminder",
  "payload": {
    "id": "medication-reminder-uuid",
    "medication_name": "Lisinopril",
    "dosage": "10 mg",
    "due_at": "2026-10-13T15:00:00Z",
    "status": "sent",
    "message": "Time to take your Lisinopril, 10 mg."
  }
}
```

A flat envelope must supply `reminder_id` explicitly. The notification's own ID
is never used as a medication reminder ID. Unknown notification kinds are ignored;
invalid known reminders produce an error rather than sending to a guessed ID.

Confirmed medication writes: bodyless POST to
`/api/v1/medication-reminders/{reminderId}/taken` or `/missed`, returning the updated
reminder. Appointment OK currently uses `{notificationsPath}/{notificationId}/ack`
from plan.md, then re-fetches to verify `acknowledged`; this contract still needs confirmation.

### Conversation and Authentication to Confirm

- `POST /api/v1/ai/process`: `{ text, conversation_id? }`; adapter expects a string
  `reply` (or `response`/`text`), optional `conversation_id`, and optional
  `pending_action` (or `proposal`) with `{ id, summary, details?, expires_at? }`.
- `POST /api/v1/actions/{id}/confirm` or `/cancel`: adapter currently requires
  `{ status: "executed" | "cancelled", message: "..." }` before showing success.
- HTTP requests include cookies. `createApi` has a `getAccessToken` callback for
  the future session controller; the app does not yet supply a bearer token.
  SSE currently requires cookie authentication. Login/pairing and voice capture/TTS
  remain dependent on the backend contracts and are not claimed as complete.
- `models/api.js` is the only network layer. Hooks live in `controllers/`;
  reusable UI lives in `views/components/`, following plan.md.

## Verification

```powershell
npm test
npm run test:e2e
npm run build
```

Browser tests start isolated demo/live Vite servers on ports 5180/5181 and intercept
live API responses. They test UI contracts, not an actual backend or database.
They use installed Microsoft Edge by default. Set `PW_CHANNEL=chrome` to use Chrome.
For an environment with restricted temp access, set `PWTEST_CACHE_DIR` to a writable
directory, e.g. `$env:PWTEST_CACHE_DIR = "$PWD/.npm-cache/playwright-transform"`.
Screenshots are in ignored `test-results/`. The tests cover 1440px, 390px and 320px
viewports, larger text, confirmations, medication actions, automatic missed,
conflicts and retry. No database migrations are added by this frontend change.
