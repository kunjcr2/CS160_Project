# Speech API

## Setup

- Add `OPENAI_API_KEY` to `.env`.
- Set `FAKE_AI=false` for real OpenAI calls.
- Install dependencies: `python -m pip install -r requirements-dev.txt`.
- Start: `uvicorn app.main:app --reload --port 5000`.
- API docs: `http://127.0.0.1:5000/docs`.

## Configuration

- STT model: `gpt-4o-mini-transcribe`.
- TTS model: `gpt-4o-mini-tts`.
- Default voice: `alloy`.
- Change values in `.env`.
- Restart the server after changes.

## Text-to-speech

- Endpoint: `POST /api/v1/ai/tts`.
- Body: JSON with `text`.
- Optional body field: `voice`.
- Response: MP3 audio.

```powershell
@'
{"text":"Hello from the voice assistant."}
'@ | curl.exe -sS -X POST "http://127.0.0.1:5000/api/v1/ai/tts" `
  -H "Content-Type: application/json" `
  --data-binary "@-" `
  --output reply.mp3 `
  --write-out "`nHTTP %{http_code} | %{content_type} | %{size_download} bytes`n"
```

- Success: `HTTP 200` and `audio/mpeg`.
- Play: `Start-Process .\reply.mp3`.

## Speech-to-text

- Endpoint: `POST /api/v1/ai/transcribe`.
- Form field: `audio`.
- Response: JSON with `text`.
- Supported: WAV, MP3, WebM, M4A, MP4.

```powershell
curl.exe -sS -X POST "http://127.0.0.1:5000/api/v1/ai/transcribe" `
  -F "audio=@reply.mp3;type=audio/mpeg" `
  --write-out "`nHTTP %{http_code} | %{content_type} | %{size_download} bytes`n"
```

- Success: `HTTP 200` and `application/json`.

## Timing

```powershell
$timer = [System.Diagnostics.Stopwatch]::StartNew()
$response = curl.exe -sS -X POST "http://127.0.0.1:5000/api/v1/ai/transcribe" -F "audio=@reply.mp3;type=audio/mpeg"
$timer.Stop()
$response
"Time: {0:N2} seconds" -f $timer.Elapsed.TotalSeconds
```

- This measures full request latency.
- Transcription rate = audio duration / request time.

## Tests

```powershell
python -m pytest tests\test_speech.py -q
```

- Tests use `FAKE_AI=true`.
- Tests do not call OpenAI.

## Streaming

- Current `/tts` waits for the full MP3.
- OpenAI TTS supports streamed audio chunks.
- Use `StreamingResponse` in FastAPI.
- Prefer WAV or PCM for lower latency.
