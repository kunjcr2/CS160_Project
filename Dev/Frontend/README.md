# Care Companion Frontend

React/Vite conversation, confirmations, reminders, and the first Sprint 3 voice UI.

## Status (November 13, 2026)

| Area | Implemented locally | Remaining acceptance work |
| --- | --- | --- |
| S2-15 | Conversation UI; action response adapter for PR #11 | AI intent-to-persisted-action integration and real backend testing |
| S2-16 | Notification polling; appointment OK; medication Taken/Missed; profile timezone and role checks | Shared Bearer authentication in Amar's controllers; medication source registration; real worker tests |
| S2-17 | Exact direct dependency versions, lockfile, setup README | Review and merge |
| Sprint 3 voice | Microphone capture, transcription review, reply playback, opt-in automatic reading, cancellation and text fallback | Test with real microphone, actual STT/TTS, and integrated backend |
| Auth integration | Pairing/email sign-in; single-flight refresh; cross-tab cookie lock; stale-session protection | Real auth API acceptance after PR #17/#18 merge |
| Sprint 3 remaining screens | Not implemented | Confirm Help, support queue, care messages and refill API contracts and team assignments |

This implements the frontend against the reviewed PR code. It does not merge
teammates' branches, migrate databases, or claim live end-to-end acceptance.
Remote main now includes PR #5 (AI conversation and speech) and PR #16 (the real
users table and first migration), in addition to the health endpoint.
Auth, actions, and notifications are still in open PRs, so main
alone cannot run this frontend's full live workflow. The local frontend branch
has been merged with that main locally; the Python cache/virtualenv ignore rules
from both branches were preserved. This branch includes the auth, reminder, and
voice frontend updates for PR #20; live integration is still pending.
Sprint 3 is not complete.

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
[PR #13](https://github.com/kunjcr2/CS160_Project/pull/13),
[PR #17](https://github.com/kunjcr2/CS160_Project/pull/17),
[PR #18](https://github.com/kunjcr2/CS160_Project/pull/18),
[PR #21](https://github.com/kunjcr2/CS160_Project/pull/21).

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

Known main blockers (verified November 7): the speech endpoint passes
`content_type` to `OpenAISpeechToText.transcribe`, but the real adapter currently
accepts only `audio` and `filename`. Real STT needs that backend mismatch fixed.
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

PR #21 still needs its medication source registered in PR #13's feed.
The older-adult medication list/add/daily-dose screens are not implemented.
Amar's action/notification branches still need integration with Zohreh's shared
Bearer authentication. Do not mark these as live-tested based on frontend mocks.

## Verification

November 13 local results: 25 unit tests passed, 27 Chrome offline browser tests
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
