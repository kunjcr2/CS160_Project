# Care Companion Frontend

React/Vite care screens with authenticated API adapters, explicit confirmations,
medication reminders, turn-based voice, care messages, refills and support requests.

## Status (November 19, 2026)

| Area | Implemented locally | Remaining acceptance work |
| --- | --- | --- |
| S2-15 / appointments | Conversation; provider/slot search; booking, cancellation and same-doctor rescheduling; confirmation and pending-action recovery | Integrated PostgreSQL acceptance |
| S2-16 | Notification polling; appointment OK; medication Taken/Missed; medication schedules and daily doses; profile timezone and role checks | Medication feed/worker patch review and real worker tests |
| S2-17 | Exact direct dependency versions, lockfile, setup README | Review and merge |
| Sprint 3 voice | Microphone capture, transcription review, reply playback, opt-in automatic reading, cancellation and text fallback | Test with real microphone, actual STT/TTS, and integrated backend |
| Auth integration | Pairing/email sign-in; single-flight refresh; cross-tab cookie lock; stale-session protection | Real PostgreSQL auth acceptance |
| PB-07 care messages | Doctor selection, text draft, explicit review/confirm, sent/failed history against PR #34 | Acceptance against PR #34 with PostgreSQL; voice proposals remain deferred |
| PB-06 Help and support queue | PR #38 Help proposals/confirmation; submitted receipt; agent/admin queue, claim/resolve, conflict handling and polling | Real API acceptance; older-adult Help history is not provided by this backend |
| PB-04 refills | PR #38 proposals, confirmation and history; status polling; remaining-count refresh; doctor-message fallback | Real API and simulated-pharmacy acceptance |
| AI suggestions | PR #31 intent routing to care forms and repeated-failure Help offer; explicit review before actions | Actual OpenAI recognition quality; care-message voice intent is not exposed yet |

The frontend now targets PR #38 (`44e9ae3`) for Help, queue, refills and appointment
changes, PR #34 for messages, and merged PR #31 for AI suggestions. The inspected
remote main is `14c055c`; PR #38 is still open. Run a backend containing those
contracts, not the old backend in this primary local checkout. The sibling
`integration/frontend-pr-apis` checkout is also an older snapshot and has not been
updated by this frontend change. See [integration notes](PR_API_INTEGRATION.md).
No remote PRs were merged and no existing databases were migrated. This is not a
claim of real backend end-to-end acceptance or completion of the whole team sprint.

## Run Locally

Use Node.js 22.12+ (or Node 20.19+) and npm. Browser tests use installed Chrome or Edge.

```powershell
cd Dev/Frontend
npm ci
npm run dev
```

Open the Vite URL, normally http://127.0.0.1:5173. Development defaults to **demo**
with an explicit sample-data banner. No real data is saved. Demo reminder controls
remain available; microphone and reply playback are disabled in demo because
there is no speech backend. Live failures never fall back to demo.

Direct dependencies are exact versions. The lockfile is committed, and
`.npmrc` has `save-exact=true`. Use `npm ci` for reproducible installation.
Vite 8.3.5 includes the patch update made during the October 23 audit.
Keep both manifests together when intentionally updating dependencies.

## Live Setup

Follow the [backend README](../Backend/README.md) for the virtual environment,
PostgreSQL, migrations and server setup. A backend integration checkout must
include the relevant PRs below. Do not bypass authorization with a development
user header to make frontend integration appear complete.

Start FastAPI from Dev/Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5000
```

Set `VITE_DATA_MODE=live` in `.env.local`, then restart Vite. Live mode first
restores a session, or displays pairing-code/email sign-in. Existing caregiver
accounts and pairing codes must be created through the backend. Account creation
and caregiver pairing-code issuance are not included in this UI.

| Variable | Default | Purpose |
| --- | --- | --- |
| VITE_DATA_MODE | demo in development; live in builds | Explicit data source |
| VITE_NOTIFICATIONS_PATH | /api/v1/notifications | PR #13 notification feed |

Vite proxies /api to http://127.0.0.1:5000. Production hosting needs equivalent
same-origin routing and HTTPS for microphone capture. Localhost is supported.
Never place an OpenAI key in a frontend environment variable.
Use the running backend's /docs to verify what is actually mounted.
A passing /api/health response does not verify feature readiness.

## Reviewed API Contracts

Sources: [PR #5](https://github.com/kunjcr2/CS160_Project/pull/5),
[PR #11](https://github.com/kunjcr2/CS160_Project/pull/11),
[PR #12](https://github.com/kunjcr2/CS160_Project/pull/12),
[PR #13](https://github.com/kunjcr2/CS160_Project/pull/13),
[PR #17](https://github.com/kunjcr2/CS160_Project/pull/17),
[PR #18](https://github.com/kunjcr2/CS160_Project/pull/18),
[PR #21](https://github.com/kunjcr2/CS160_Project/pull/21).
Care-message contracts were checked separately against
[PR #34](https://github.com/kunjcr2/CS160_Project/pull/34), head `01fc2e7`.

All routes below use /api/v1.

| Route | Frontend behavior |
| --- | --- |
| POST /auth/login | Email/password; access token response |
| POST /auth/pair | Eight-digit code; access token response |
| POST /auth/refresh | Restore/refresh with HttpOnly cookie |
| POST /auth/logout | Accepts 204, clears signed-in screen |
| GET /users/me | Profile role, name and timezone |
| POST /ai/transcribe | Multipart field audio; response {text} |
| POST /ai/process | JSON {text, language: "en"}; response {reply, proposal} |
| POST /ai/tts | JSON {text}; binary audio/mpeg response |
| POST /actions/{id}/confirm or /cancel | Response {action, message}; verify action.id and action.status |
| GET /actions/pending | Restore a saved confirmation before allowing a new request |
| GET /providers; GET /slots?provider_id&from&to&limit | Search available times in a date range of at most 31 days |
| POST /actions | Propose book_appointment with the exact returned slot_id; never auto-confirm |
| GET /appointments | List upcoming appointments; refresh after confirmation |
| POST /actions with action_type=send_care_message | Payload {older_adult_id, provider_id, body}; show returned confirmation card before sending |
| GET /older-adults/{id}/messages | Provider, body, sent/failed status and created_at; newest first |
| GET /older-adults/{id}/medications | Show prescribed medications and local schedules |
| GET /older-adults/{id}/medication-reminders?date=YYYY-MM-DD | Show the selected date's doses; default date uses the profile timezone |
| GET /notifications | Flat notification array; id is reminder ID |
| POST /appointment-reminders/{id}/acknowledge | Verify returned reminder is acknowledged |
| POST /medication-reminders/{id}/taken or /missed | No body; verify returned dose status |

Access tokens stay in memory, not localStorage. Requests include credentials.
A 401 on an authenticated feature request attempts one shared refresh and one
retry. Within an API instance, concurrent requests (including StrictMode session
restores) await the same promise. A late 401 reuses an already-refreshed token.
Across same-origin tabs/API instances, the browser's Web Locks API serializes
refresh, login/pairing, and logout. Each tab refreshes using the latest HttpOnly
cookie after the previous operation completes; tokens are not broadcast or
written to browser storage. See the [Web Locks specification](https://www.w3.org/TR/web-locks/).

Live authentication requires a browser with Web Locks over HTTPS or localhost.
If unavailable, the UI reports the problem without sending an unsafe refresh.
Use one canonical frontend origin: locks do not coordinate different ports or
hostnames even when cookies might be shared. Waiting for another tab is limited
to 30 seconds; each auth network request has a 15-second timeout.

Only an authentication rejection expires the session; network/5xx failures
remain retryable errors. Old responses cannot refresh or overwrite a session
after a local login/logout. Cross-tab logout does not immediately erase another
tab's screen; that tab discovers session expiry on its next rejected request or
reload (backend access-token revocation behavior still applies).
There is no blind retry of failed or timed-out mutations. Errors with
detail.code/message preserve the backend message, including medication too_early.

PR #5's semantic proposal (kind, doctor/date_hint or medication/time_hint) has
no persisted action ID. The UI displays the reply and an explicit unsaved notice,
not a working Confirm button. It never invents an ID or creates an action using
guessed slot/medication data. A future pending_action object with id and
summary_text can use the existing confirmation card. A 200 action response
with action.status=failed is an error, not a successful booking.

## Voice Behavior

- Record a complete utterance, then send the recording to /ai/transcribe.
- The transcript is appended to the existing draft without automatically sending.
  Users review/edit it and explicitly send it to /ai/process.
- Recordings stop at 60 seconds, with a 10 MiB client size limit. Supported
  MediaRecorder formats are WebM/Opus, WebM and MP4, selected by browser capability.
- Microphone permission is requested only on Record. Cancel, logout and unmount
  stop tracks, discard the recording and abort pending voice work.
- Each assistant reply has Play/Stop. Read replies aloud is opt-in and off initially.
  Only one audio response plays at a time; object URLs are released.
- STT and AI allow 60 seconds; TTS allows 90 seconds. Cancel stops pending playback.
  The API's 2,000-character limit is respected without silently truncating text.
- Microphone, network, empty transcription, audio decoding and autoplay failures
  leave text input/replies available. No client-side action is triggered by speech.
- Audio is not stored locally or uploaded until recording stops. Cancel before
  stopping discards it; cancelling an already-sent request cannot undo server receipt.

This is turn-based speech, not streaming or a hands-free confirmation flow.
English only; multilingual and speech-rate settings are not wired to PR #5.

Speech integration issue: the speech endpoint passes
`content_type` to `OpenAISpeechToText.transcribe`, but the real adapter currently
accepts only `audio` and `filename`. The isolated integration branch fixes that
signature; the frontend branch does not include the backend patch.
The fake TTS adapter returns placeholder bytes rather than a playable MP3, so it
cannot be used to validate browser audio playback. Frontend tests mock speech.

## Reminder Behavior

While the page is visible, poll every 20 seconds; refresh on focus or manually.
No SSE/WebSocket is assumed, and this does not notify while the app is closed.
Only the backend decides when a reminder changes to missed. Responses replace
matching reminders, so refresh does not create duplicate banners.

Taken/Missed appear only for sent doses and an older_adult profile. Appointment
reminders use OK. The profile timezone formats UTC timestamps. A mutation response
without message retains the banner's existing backend message.

The isolated integration branch registers PR #21's medication source in PR #13's
feed and worker. These backend patches still need teammate review. The older-adult
medication list and daily-dose screens use PR #21 directly, including status updates
every 20 seconds while open. A failed refresh disables stale dose buttons until a
successful refresh. Adding medications, caregiver patient selection, Help,
support queues and refill requests are not implemented. Shared Bearer authentication
is already in the combined backend PR head. Do not mark this as live-tested based
on frontend mocks.

## Appointment Selection and Recovery

Open **Find appointments**, choose a doctor/date range, and select **Review this time**.
This calls POST /actions; only the confirmation card's **Confirm** calls /confirm.
The exact server slot ID is retained. A slot conflict or failed action is shown as
an error, and the appointment list is refreshed after resolution. No AI intent is
converted into an invented slot. Pending confirmations are restored on sign-in or
page reload. A failed pending lookup blocks new requests until retry succeeds;
a lost proposal response triggers recovery instead of blindly replacing the action.

## Message My Doctor (PB-07)

Open **My care → Message my doctor**, choose a doctor, and type up to 2,000
characters. **Review message** creates `send_care_message` using the signed-in
older adult's ID, the selected provider's ID and the trimmed body. The server's
summary is displayed in a **REVIEW MESSAGE** card. Only **Confirm** calls the
confirm endpoint; Cancel never sends. A successful send refreshes history and
clears the submitted draft; cancellation and failure retain it. Drafts survive
panel changes in memory, but are not saved to browser storage or across sign-out.

PR #34's messaging provider is a mock: even live API mode does not deliver to a
real doctor. The screen labels this explicitly. The history endpoint includes
both sent and failed records. There are no replies or read receipts.

An executed action is not enough to report success: PR #34 can return
`action.status="executed"` with `action.result.ok=false` when delivery fails.
The adapter checks `ok` and `message_id`, preserves backend errors/guardrail
messages, and refreshes history after a terminal failure. Retrying a lost confirm
response uses the same action ID; it never automatically creates a second message.
Saved pending messages are restored after a page reload, including their full
server read-back. New proposals stay blocked until the pending action is resolved.

This first screen is for the signed-in older adult (plus explicit demo mode).
Caregiver patient selection is not implemented; a caregiver ID is never substituted
for older_adult_id. AI/voice care-message proposals remain deferred. To use the
real API, run a backend containing PR #34 and its migration; the older local
integration checkout does not contain #34 yet. A 404 does not fall back to samples.

## Help, support queue and prescription refills

Open **My care → Help**, **Prescription refills**, or **Preview support queue**
in demo mode. The queue preview is explicitly a simulation. A signed-in
`support_agent` or `admin` instead gets a separate support workspace; the app does not load
older-adult conversations, pending actions or notifications for that role.

- Help shares only the optional summary (maximum 300 characters) the user reviews and confirms, not the
  conversation transcript. Cancellation retains the draft and creates no request.
- The demo queue starts with one sample request. Create a Help request, then
  preview the queue, view its details, take it, and mark it resolved. Return to
  Help to see the updated status. Queue failures require a refresh before retry.
- Refill selection shows available counts, blocks zero/unknown counts and stopped
  medications, and offers **Contact my doctor**. This opens an editable message
  draft; it never sends automatically or overwrites an existing message draft.
- A confirmed demo refill is only **Submitted for review**. It does not mean a
  pharmacy received or approved it. Duplicate pending requests are blocked.
- Demo requests live in memory and reset on reload. Nothing is sent to a real
  agent, doctor or pharmacy. Existing confirmation, cancellation and expiry checks
  apply, and inputs/queue controls support a 320px viewport and larger text.

In live mode, `src/models/requestApi.js` implements the verified PR #38 contracts:

| Operation | API (all prefixed with /api/v1) |
| --- | --- |
| Help proposal | `POST /actions`, type `request_help`, payload `{older_adult_id, summary, reason}` |
| Refill proposal | `POST /actions`, type `request_refill`, payload `{older_adult_id, medication_id}` |
| Confirm / reject proposal | `POST /actions/{id}/confirm` / `/cancel` |
| Refill history | `GET /older-adults/{id}/refills` |
| Unresolved support queue | `GET /assistance/queue` |
| Claim / resolve | `PATCH /assistance/{id}`, body `{status: "in_progress"}` or `{status: "resolved"}` |
| Cancel appointment proposal | `POST /actions`, type `cancel_appointment`, payload `{appointment_id}` |
| Reschedule proposal | `POST /actions`, type `reschedule_appointment`, payload `{appointment_id, slot_id}` |

Refill statuses are `requested`, `in_progress`, `ready`; the backend's status
sentence is displayed. Medication counts reload after confirmation. Refill history
and the unresolved support queue poll every 20 seconds while visible, with manual
refresh and focus refresh. Queue status starts at `open`; claiming conflicts require
a refresh. Resolved rows disappear from the live queue; there is no live archive.

PR #38 does not expose an older-adult Help history/detail endpoint. Live Help shows
only a verified submission receipt for this session, with a clear progress/history
limitation. It never reads the agent-only queue using an older-adult account.
Caregiver patient management is outside the implemented older-adult workflow.

Appointment changes are available only for future booked visits. Rescheduling locks
the original doctor and uses the opaque slot ID from the server. Creating a proposal
does not change the visit; confirm refreshes appointments and reminders. A failed
office call leaves the original visit intact. AI/voice intents open the matching
care form for explicit selection and review; they never invent persisted action IDs.
Repeated unclear replies carry `unclear_turns` back to the AI and offer Help when
`offer_human_help` is true. This does not automatically send a transcript or request.

All failures stay in live mode: no sample fallback or fabricated success. These API
contracts still use a simulated pharmacy/provider. Real pharmacy or doctor delivery
is not claimed.

## Verification

November 19 local results: 47 unit tests passed, 66 Chrome offline browser tests
passed, and the production build passed. The normal dev-server browser run was
blocked by this environment (Edge launch failure; Chrome localhost network
access denied). Real backend and microphone acceptance remain pending.

```powershell
npm test
$env:PW_CHANNEL = "chrome"
npm run test:e2e
npm run build
```

Browser tests start isolated demo/live servers on 5180/5181 and intercept HTTP
responses. Voice tests simulate MediaRecorder and Audio for deterministic tests;
they do not verify microphone hardware, recognition quality or real MP3 decoding.
Manually verify those on the integrated backend before marking voice complete.

If the test environment cannot reach local HTTP servers, use offline browser
tests: set `PW_OFFLINE_BUILD=1` and run `npm run test:e2e`. The runner builds demo
and live artifacts, then Playwright serves them from disk using route fixtures.
Browser locks and cookies are real; API/media responses remain mocked. Offline
mode exercises production bundles; the normal Vite mode also exercises React's
development StrictMode. In PowerShell:

```powershell
$env:PW_CHANNEL = "chrome"
$env:PW_OFFLINE_BUILD = "1"
npm run test:e2e
Remove-Item Env:PW_OFFLINE_BUILD
```

Tests include permission denial, cancel/discard, transcription failure/retry,
review-before-send, blocked playback, pairing/logout, profile timezone, polling,
role restrictions, confirmations, reminder conflicts, and desktop/390px/320px layout.
Auth regression tests also cover late 401 responses, transient refresh failures,
cancellation, stale responses after logout/login, and two tabs rotating a shared
HttpOnly cookie with real browser locks. HTTP responses remain mocked; these
tests do not establish acceptance against the real auth service/PostgreSQL.
Screenshots are under ignored test-results/. Test caches use isolated .npm-cache
directories to avoid Windows file locks. PW_CHANNEL defaults to msedge; Chrome
can be selected above. PWTEST_CACHE_DIR can override the transform-cache path.
