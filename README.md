# Personal Voice AI

Speak to an AI assistant and hear replies in your own cloned voice. The pipeline is speech-to-text (Sarvam), then the LLM (Groq or xAI), then cloned speech (Sarvam). See [Documentation.md](Documentation.md) for the full design.

## Setup

Requires conda, Node.js and PostgreSQL. Copy `.env.example` to `.env` and fill it in.

```powershell
conda activate environ
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m app.seed --email you@example.com
```

The last command prompts for the password you will log in with.

```powershell
cd ..\frontend
npm install
```

## Run

In one terminal:

```powershell
conda activate environ
cd backend
uvicorn app.main:app --reload
```

In another:

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173. API docs are at http://localhost:8000/docs.

## Check the providers

These scripts call the real APIs and use credits. Run them from `backend/`.

```powershell
python poc/check_llm.py
python poc/check_stt.py my_question.m4a --language en-IN
python poc/check_sarvam_voice_clone.py --sample my_voice.m4a --i-own-this-voice
python poc/check_pipeline.py my_question.m4a
python poc/check_sarvam_voice_clone.py --delete
```

Only clone a voice you have the right to use. Recordings are ignored by Git.

## Choose the speech-to-text provider

`STT_PROVIDER` in `.env` selects it:

- `sarvam` (the default) uses Saaras and needs a valid `SARVAM_API_KEY`.
- `groq` uses Whisper and needs only your Groq key. It has no Odia support, so Odia falls back to auto-detection.

Cloned speech always needs Sarvam. Without a working Sarvam key, the app gives text replies.

## Test

```powershell
cd backend
python -m pytest
```

Tests use fake providers and an in-memory database, so they call no paid APIs.

## Switch to xAI Grok

In `.env`, set `LLM_PROVIDER=xai` and `XAI_API_KEY` to your xAI key. Each provider only ever receives its own key.

## Rate limits

Defaults are 10 login attempts per minute per IP address, 5 voice enrollments per hour per user, and 30 conversation turns per minute per user. Override them with `LOGIN_ATTEMPTS_PER_MINUTE`, `ENROLLMENTS_PER_HOUR` and `TURNS_PER_MINUTE`.

The counters live in one server process, so running several workers needs a shared store such as Redis. Behind a proxy, every client shares one IP address until the proxy's forwarded address is trusted.
