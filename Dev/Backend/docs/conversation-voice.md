# Conversation and voice API

The controller recognizes appointment, medication reminder, prescription refill,
and human-help intents. OpenAI emits one structured function call. The backend
validates its arguments and calls the matching `propose_*` function. The result
is a **proposal only**. No appointment, reminder, refill, or transfer happens in
these endpoints. When the action services are merged, they must create a pending
action and require the separate confirm endpoint before executing it.

## Text

`POST /api/v1/ai/process` takes:

```json
{"text":"Refill my lisinopril","language":"en","unclear_turns":0}
```

It returns `reply`, `proposal`, `readback`, `language`, `unclear_turns`, and
`offer_human_help`. The client shows the read-back for recognition verification.
It must not treat the read-back question as action confirmation. Pass the returned
`unclear_turns` into the next request; after three unclear turns the assistant
offers human help. An explicit request for a person returns a `human_help`
proposal and still requires the user's consent before a handoff is created.
After an offer, a clear "yes" with `unclear_turns: 3` also returns that proposal.

`language` supports English (`en`) and Spanish (`es`), including region tags such
as `es-MX`. Other language codes fall back to English. The same language controls
the model instruction and the server's prompts.

## Voice

`POST /api/v1/ai/voice` takes multipart `audio` plus optional `language` and
`unclear_turns` fields. It transcribes the audio, runs the same controller, and
returns the transcript, response fields above, base64 MP3 in `audio_base64`, and
measured `transcription_ms`. If synthesis fails, `audio_base64` is null and the
text response remains available. The spoken response includes the read-back when
there is a complete proposal.

The standalone `POST /api/v1/ai/transcribe` and `POST /api/v1/ai/tts` endpoints
remain available. Audio input accepts WAV, MP3, WebM, M4A, and MP4 up to 10 MiB.

Set `FAKE_AI=true` for deterministic offline intent and speech tests. Set it to
`false` and configure `OPENAI_API_KEY` to use OpenAI. The transcription model is
configurable with `OPENAI_STT_MODEL`; the default is `gpt-4o-mini-transcribe`.
Measure real input latency and word accuracy against representative recordings
before claiming the 1.5-second target; CI fakes cannot establish either metric.
