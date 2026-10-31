# Personal Voice AI — Development Documentation

> Build a conversational AI application that listens to the user's speech, understands it with Grok, and responds using the user's own cloned voice — without ElevenLabs.

**Document version:** 1.1 (provider details checked against the official Sarvam and xAI docs)  
**Date:** 31 October 2026  
**Recommended MVP stack:** React + TypeScript, FastAPI, Sarvam AI, xAI Grok, PostgreSQL

---

## Implementation status

Milestones 0 to 4 are built. These decisions differ from the plan below:

- **LLM provider:** the application runs on Groq by default, using Chat Completions and the model `openai/gpt-oss-120b`. xAI Grok remains supported through the Responses API; set `LLM_PROVIDER=xai`. Where this document says "Grok", read "the configured LLM".
- **Database:** `.env` uses `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD` and `DB_NAME`, with a local PostgreSQL server. `DATABASE_URL` is still accepted, and Docker Compose is optional.
- **FFmpeg:** supplied by the `imageio-ffmpeg` Python package, so no separate installation is needed.
- **Audio retention:** voice samples and spoken messages are not stored after processing. Only generated replies are stored.
- **Saving messages:** a turn's messages are saved after the LLM replies and before voice generation, so a failed LLM call leaves nothing to duplicate on retry.
- **Speech-to-text:** Sarvam is the default. `STT_PROVIDER=groq` selects Groq Whisper as an alternative.
- **Rate limits:** login, enrollment and conversation turns are limited in-process, ahead of Milestone 6.
- **Sessions:** tokens carry a per-user version, so logging out or changing the password revokes them. This ends all of the user's sessions on logout. `POST /api/v1/me/password` changes the password.
- **Request protection:** state-changing requests from an origin outside `CORS_ORIGINS` are refused, oversized or length-less bodies are refused before parsing, and API docs are hidden in production. In production, add the site's real origin to `CORS_ORIGINS`.
- **Audio decoding:** uploads are decoded from temporary files that are deleted immediately, only from an allowed list of formats, and only up to a length limit.
- **Reply length:** LLM replies are capped by `LLM_MAX_OUTPUT_TOKENS` (default 2048).

**Verified live:** the Groq LLM, Sarvam speech-to-text with the async client, Groq Whisper, PostgreSQL, and a spoken turn through a real browser.

**Tested only against mocked responses in the providers' documented formats:** Sarvam voice enrollment, cloned speech and voice deletion, and the xAI LLM. Milestone 0 is incomplete until the Sarvam voice operations pass using a recording of the voice owner (see section 18). Streaming in Milestone 5 should wait for those real cloned-speech timings. The rest of Milestones 5 and 6 has not started.

---

## 1. Product overview

### 1.1 Objective

Build a web application where a user can:

1. Record a voice sample through the browser.
2. Create a reusable voice profile from that sample.
3. Speak to an AI assistant through a microphone.
4. Transcribe the user's speech.
5. Send the transcript and conversation context to Grok.
6. Convert Grok's response into speech using the user's cloned voice.
7. Play the generated audio and continue the conversation.

The application should not depend on ElevenLabs.

### 1.2 Provider strategy

Use the user's existing API credentials:

| Capability | Provider / service | Responsibility |
|---|---|---|
| Speech-to-text (STT) | Sarvam Saaras | Convert microphone audio into text |
| Voice enrollment | Sarvam Instant Voice Cloning | Create a reusable voice profile |
| Cloned text-to-speech (TTS) | Sarvam Voice Cloning | Speak generated text in the enrolled voice |
| LLM | xAI Grok API | Understand the message and generate a response |
| Backend | FastAPI | Orchestrate providers and protect credentials |
| Frontend | React + TypeScript | Recording, chat, playback and settings |
| Database | PostgreSQL | Users, voice profiles, sessions and messages |
| Optional cache | Redis | Short-lived session state and rate limiting |
| Audio storage | Local storage for development; object storage for production | Store user-approved audio files |

**Important:** Sarvam currently documents Instant Voice Cloning as a beta capability. Confirm that it is enabled for your account, your subscription supports it, and the relevant endpoints work with your API key before building the rest of the product around it.

### 1.3 MVP scope

The first working version should support:

- One authenticated user (multi-user authentication can follow).
- One saved voice profile.
- Microphone recording and audio upload.
- Voice enrollment through Sarvam.
- Text chat with Grok.
- Voice chat using the chained STT → LLM → cloned TTS pipeline.
- Conversation history.
- Audio playback.
- Clear loading, error and retry states.

Do not start with phone calls, multi-agent orchestration, custom model training, or complex real-time interruption handling. Validate the core pipeline first.

---

## 2. Architecture

### 2.1 High-level architecture

```mermaid
flowchart TD
    U[User] --> FE[React Web Application]
    FE -->|HTTPS / WebSocket| API[FastAPI Backend]

    API --> AUTH[Authentication and Validation]
    API --> DB[(PostgreSQL)]
    API --> STT[Sarvam Saaras STT]
    API --> LLM[xAI Grok API]
    API --> VC[Sarvam Voice Cloning]

    STT -->|Transcript| API
    API -->|Prompt + conversation context| LLM
    LLM -->|Assistant response text| API
    API -->|Text + saved voice_id| VC
    VC -->|Generated audio| API
    API -->|Audio response / stream| FE
    FE --> PLAYER[Audio Player]
```

### 2.2 Voice enrollment flow

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant API as FastAPI
    participant Sarvam

    User->>Browser: Confirm consent and record a clean voice sample
    Browser->>API: Upload audio file + consent confirmation
    API->>API: Record consent; validate size and duration; convert to WAV
    API->>Sarvam: POST /voices/create
    Sarvam-->>API: voice_id + reference_text
    API->>API: Save provider voice_id and metadata
    API-->>Browser: Voice profile created
    Browser-->>User: Show ready status
```

### 2.3 Conversation flow (MVP)

```mermaid
sequenceDiagram
    participant User
    participant Browser
    participant API as FastAPI
    participant STT as Sarvam STT
    participant LLM as xAI Grok
    participant TTS as Sarvam Voice Clone

    User->>Browser: Speak into microphone
    Browser->>API: Upload recorded audio
    API->>STT: Transcribe audio
    STT-->>API: Transcript
    API->>API: Load conversation history
    API->>LLM: System prompt + history + transcript
    LLM-->>API: Assistant response text
    API->>API: Save transcript and assistant response
    API->>TTS: Text + saved voice_id + language_code
    TTS-->>API: Generated audio
    API->>API: Store audio and link it to the assistant message
    API-->>Browser: Transcript + response text + audio (or audio error)
    Browser-->>User: Display text and play audio
```

### 2.4 Why use a chained pipeline first?

The initial pipeline is:

`Microphone → STT → Grok → Voice-cloned TTS → Playback`

Advantages:

- Each provider can be tested independently.
- Failures can be isolated to a specific stage.
- Transcripts and LLM responses are inspectable.
- Easier to measure latency and provider costs.
- No need to build a complex real-time media system before validating the product.

The first version can record a complete utterance and submit it. Streaming can be introduced after the basic flow works.

---

## 3. Provider integration

### 3.1 Sarvam AI

Official documentation:

- API introduction: https://docs.sarvam.ai/api-reference/introduction
- Voice cloning overview: https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/overview
- Create voice: https://docs.sarvam.ai/api-reference/voice-cloning/create-voice
- Generate cloned speech: https://docs.sarvam.ai/api-reference/voice-cloning/clone
- STT documentation: https://docs.sarvam.ai/api-reference/speech-to-text
- Delete voice: https://docs.sarvam.ai/api-reference/voice-cloning/delete-voice
- Commercial licensing and consent: https://docs.sarvam.ai/api/getting-started/commercial-licensing
- SDKs and libraries: https://docs.sarvam.ai/api/getting-started/sdks

#### 3.1.1 Authentication

Sarvam uses the `api-subscription-key` header.

```http
api-subscription-key: YOUR_SARVAM_API_KEY
```

Base URL:

```text
https://api.sarvam.ai
```

Never expose this key in React or browser code.

#### 3.1.2 Voice enrollment

The documented endpoint is:

```http
POST https://api.sarvam.ai/voices/create
Content-Type: multipart/form-data
api-subscription-key: YOUR_SARVAM_API_KEY
```

The request uses multipart form data. The documented fields include:

| Field | Required | Purpose |
|---|---|---|
| `file` | Yes | Reference voice audio file |
| `name` | Yes | Name for the saved voice, 1–100 characters |
| `language` | Yes | BCP-47 code of the reference audio, such as `en-IN` |
| `style` | No | Optional style, such as `conversational` |
| `gender` | No | Optional metadata |

The API documentation currently recommends a clean, single-speaker reference sample of around 10–15 seconds. The create endpoint documents a maximum file size of 50 MB. Check the latest API limits before implementation.

Constraints that affect the design:

- **WebM is not an accepted enrollment format.** Accepted formats are WAV (recommended), MP3, FLAC, OPUS, AAC, MULAW, ALAW and LINEAR16. Browsers commonly record WebM, so convert every enrollment recording to WAV on the backend.
- **A successful response has HTTP status 201**, with `data.voice_id`, `data.status` and `data.reference_text`. A `data.status` of `saved` means the voice is ready; map it to the local `ready` status.
- **Saved voices are capped per organization.** The Starter plan allows 50; over the cap, the API returns 403 `TIER_LIMIT_REACHED`.
- **Poor samples can be rejected.** The API returns 422 when audio fails quality validation, so show the user a re-record prompt rather than a generic error.
- **The API has no consent field.** Sending `consent` to this endpoint returns 400 because it is Studio-only. Sarvam's licensing page requires you to confirm your rights to the voice, so the application must capture and store its own consent record (see section 11). Sarvam's docs do not say how API-created voices satisfy the dashboard consent step; confirm this with Sarvam before any commercial use.

Illustrative Python SDK usage:

```python
from sarvamai import SarvamAI

client = SarvamAI(
    api_subscription_key="YOUR_SARVAM_API_KEY"
)

with open("reference.wav", "rb") as audio_file:
    result = client.voice_cloning.create_voice(
        file=audio_file,
        name="my-personal-voice",
        language="en-IN",
        style="conversational",
    )

voice_id = result.data.voice_id
print(voice_id)
```

Persist the returned `voice_id` in PostgreSQL. Do not create a new voice on every conversation.

#### 3.1.3 Generate speech using the saved voice

Documented endpoint:

```http
POST https://api.sarvam.ai/voices/clone
```

The request is multipart form data. Provide exactly one of:

- `voice_id`: an existing saved voice; or
- `ref_audio`: an inline reference audio clip.

For this application, use `voice_id`.

Illustrative SDK usage:

```python
import base64
from sarvamai import SarvamAI

client = SarvamAI(
    api_subscription_key="YOUR_SARVAM_API_KEY"
)

result = client.voice_cloning.convert(
    voice_id="YOUR_SAVED_VOICE_ID",
    text="Hello! How can I help you today?",
    language_code="en-IN",
)

with open("response.wav", "wb") as output_file:
    output_file.write(base64.b64decode(result.audio_b64))
```

Read `audio_b64`; the `audio` field is a deprecated alias of it. Output defaults to WAV at 24,000 Hz, and `output_audio_codec` and `speech_sample_rate` can change this.

Always send `language_code`. Sarvam's API reference marks it as required, while its overview and FAQ say it can be omitted. Twelve codes are supported: `as-IN`, `bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `od-IN`, `pa-IN`, `ta-IN` and `te-IN`. STT supports more languages than this, so limit the language setting to these twelve.

The one-shot clone endpoint rejects `text` over 1,000 characters with a 400, and usage is billed per character. Therefore:

- Strip any Markdown from the reply before synthesis.
- Split longer replies at sentence boundaries.
- Do not join WAV chunks by concatenating bytes, because each chunk has its own header. Merge them with FFmpeg or Python's `wave` module.

Do not assume the one-shot response format is identical to the streaming endpoint: one-shot returns JSON containing base64 audio, whereas `/voices/clone/stream` returns a binary audio stream.

#### 3.1.4 Streaming cloned speech

Sarvam documents:

- `POST /voices/clone/stream` for HTTP audio streaming (SDK: `convert_stream`), limited to 1,000 characters per request.
- `GET /voices/clone/ws` for WebSocket streaming (SDK: `voice_cloning_streaming`), limited to 2,500 characters per `text` message.

Streaming supports only `mp3` (default), `wav`, `linear16`, `mulaw` and `alaw`.

Use one-shot generation for the first milestone. Later, evaluate streaming to reduce perceived response latency.

The Sarvam SDK version required for the documented voice-cloning surface is currently `sarvamai >= 0.1.37`; the latest release on PyPI at the time of writing is 0.1.41. Pin and test a compatible version in the project rather than installing an unbounded dependency in production.

In FastAPI, use `AsyncSarvamAI` rather than `SarvamAI`, so that provider calls do not block the event loop. The SDK documentation says both clients expose the same method names and arguments, but shows no async voice-cloning example, so confirm this in Milestone 0.

#### 3.1.5 Delete and list voices

- `DELETE /voices/delete/{voice_id}` returns 204 with no body, and 404 if the voice does not exist (SDK: `delete_voice`). Note that the path is not `DELETE /voices/{voice_id}`.
- `GET /voices` lists voices, newest first, with optional `search`, `gender`, `accent`, `limit` (default 50, maximum 200) and `offset` parameters (SDK: `list_voices`).

Use a name search to reconcile an enrollment that timed out (see section 10).

#### 3.1.6 Speech-to-text

Use Sarvam Saaras to transcribe recorded microphone audio.

```http
POST https://api.sarvam.ai/speech-to-text
Content-Type: multipart/form-data
api-subscription-key: YOUR_SARVAM_API_KEY
```

| Field | Value for this application |
|---|---|
| `file` | The recorded utterance. WebM is accepted here, unlike enrollment |
| `model` | `saaras:v4` (the current default); keep it configurable |
| `language_code` | The conversation language, or `unknown` to auto-detect |

The response contains `transcript`, `language_code` and `request_id`.

This endpoint is described as being for audio under 30 seconds; longer audio belongs on the separate Batch API. Stop browser recording before 30 seconds in the MVP. The API works best with 16 kHz audio, and multi-channel audio is merged to mono.

Keep STT behind a service interface so the provider can be changed without rewriting conversation logic.

Example service contract:

```python
from typing import Protocol

class SpeechToTextProvider(Protocol):
    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        language_code: str = "unknown",
    ) -> str:
        ...
```

### 3.2 xAI Grok

Official documentation:

- Developer documentation: https://docs.x.ai/
- API reference: https://docs.x.ai/developers/rest-api-reference
- Responses API: https://docs.x.ai/developers/rest-api-reference/inference/responses
- Comparison with Chat Completions: https://docs.x.ai/developers/model-capabilities/text/comparison
- Models: https://docs.x.ai/developers/models

Grok is responsible for conversational intelligence. It does not need to generate the cloned audio; Sarvam handles that stage.

The current docs brand the platform as "SpaceXSI", but the documented API hosts and paths are still on `x.ai`.

#### 3.2.1 API configuration

xAI API configuration:

```text
Base URL: https://api.x.ai/v1
Endpoint: /responses
Authentication: Authorization: Bearer <XAI_API_KEY>
```

xAI's docs say new integrations should use the Responses API rather than Chat Completions, which remains available as its stateless predecessor.

`grok-4.7` is the model xAI currently recommends for general use. Check your account's available model IDs before relying on it. Model IDs and API capabilities can change.

#### 3.2.2 Example request

```python
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ["XAI_API_KEY"],
    base_url="https://api.x.ai/v1",
)

async def generate_reply(system_prompt: str, messages: list[dict]) -> str:
    response = await client.responses.create(
        model=os.environ["XAI_MODEL"],
        instructions=system_prompt,
        input=messages,
        store=False,
    )

    content = response.output_text
    if not content:
        raise RuntimeError("Grok returned an empty response")

    return content
```

PostgreSQL is the source of truth for conversation history, so send the relevant history in `input` on every request rather than using `previous_response_id`.

Set `store=False` because Responses are otherwise stored by xAI for 30 days, and these transcripts may be sensitive. The docs describe the field but show no example of it, so confirm its behavior in Milestone 0.

Use the OpenAI-compatible SDK interface only for endpoints and features supported by xAI. Keep the model name configurable.

#### 3.2.3 Conversation prompt

Use a system prompt that defines the assistant's behavior, not a prompt that claims the model has literally become the user.

```text
You are a helpful personal voice assistant.

Reply in {conversation_language}.

Communication style:
- Speak naturally and clearly.
- Prefer concise answers unless the user asks for detail.
- Use conversational language suitable for spoken responses.
- Avoid unnecessary Markdown, tables, URLs, and long lists in spoken answers.
- If a question is ambiguous, ask one focused clarification.
- Never claim to be the account owner or impersonate another person.
- Do not invent facts or claim to have performed actions that were not performed.
```

Voice identity and conversational personality are separate concerns. A cloned voice reproduces vocal characteristics; the LLM prompt controls the assistant's response style.

For the MVP, use one language per conversation, taken from the user's language setting, for the STT `language_code`, the prompt's `{conversation_language}` and the TTS `language_code`. This keeps the reply language and the synthesis language in agreement.

---

## 4. Backend design

### 4.1 Recommended folder structure

```text
personal-voice-ai/
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   │   ├── AudioRecorder.tsx
│   │   │   ├── VoiceEnrollment.tsx
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── AudioPlayer.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Enrollment.tsx
│   │   │   ├── Conversation.tsx
│   │   │   └── Settings.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── hooks/
│   │   └── types/
│   └── tsconfig.json
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── health.py
│   │   │       ├── auth.py
│   │   │       ├── voices.py
│   │   │       ├── conversations.py
│   │   │       └── audio.py
│   │   ├── schemas/
│   │   │   ├── voice.py
│   │   │   ├── conversation.py
│   │   │   └── message.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── voice_profile.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── audio_asset.py
│   │   │   └── provider_request.py
│   │   ├── services/
│   │   │   ├── providers/
│   │   │   │   ├── sarvam_stt.py
│   │   │   │   ├── sarvam_voice.py
│   │   │   │   └── grok_llm.py
│   │   │   ├── voice_service.py
│   │   │   └── conversation_service.py
│   │   ├── repositories/
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   └── utils/
│   │       └── audio.py
│   ├── alembic/
│   ├── poc/
│   ├── tests/
│   ├── alembic.ini
│   └── requirements.txt
│
├── storage/
│   └── .gitkeep
├── .env
├── .env.example
├── docker-compose.yml
├── .gitignore
└── README.md
```

### 4.2 Provider abstraction

Avoid coupling application logic directly to provider SDK objects.

```python
from typing import Protocol

class VoiceProvider(Protocol):
    async def create_voice(
        self,
        audio_bytes: bytes,
        filename: str,
        name: str,
        language: str,
    ) -> dict:
        ...

    async def synthesize(
        self,
        voice_id: str,
        text: str,
        language_code: str,
    ) -> bytes:
        ...

    async def delete_voice(self, voice_id: str) -> None:
        ...
```

Create a separate STT interface and LLM interface. Provider adapters translate your internal application contracts into Sarvam and xAI requests.

Benefits:

- Swap providers without rewriting business logic.
- Mock providers during tests.
- Normalize errors and outputs.
- Keep provider-specific request details out of API routes.

The code above is an interface example, not a complete Sarvam SDK adapter. Confirm the installed SDK's exact synchronous or asynchronous method signatures.

### 4.3 Configuration

`backend/app/core/config.py` should load environment variables using Pydantic Settings. Keep `.env` in the repository root, where Docker Compose also reads it, and resolve its path from the location of `config.py` rather than the current working directory.

Example `.env.example`:

```dotenv
APP_ENV=development
APP_NAME=Personal Voice AI
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voice_ai
SESSION_SECRET=replace_me

SARVAM_API_KEY=replace_me
SARVAM_STT_MODEL=saaras:v4
XAI_API_KEY=replace_me
XAI_BASE_URL=https://api.x.ai/v1
XAI_MODEL=grok-4.7

MAX_AUDIO_UPLOAD_MB=20
MAX_UTTERANCE_SECONDS=29
AUDIO_STORAGE_DIR=storage
CORS_ORIGINS=http://localhost:5173
```

Do not put real credentials in `.env.example`. Add `.env` to `.gitignore`. Never commit API keys, audio recordings, or generated voice data.

---

## 5. API design

All application endpoints are served by FastAPI. The browser must call your backend, not Sarvam or xAI directly with secret keys.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/auth/login` | Start a session (sets an HTTP-only cookie) |
| POST | `/api/v1/auth/logout` | End the session |
| POST | `/api/v1/voices` | Upload audio and create voice profile |
| GET | `/api/v1/voices` | List the current user's profiles |
| GET | `/api/v1/voices/{profile_id}` | Get profile metadata |
| DELETE | `/api/v1/voices/{profile_id}` | Delete the provider voice, then the local profile |
| POST | `/api/v1/conversations` | Create a conversation |
| GET | `/api/v1/conversations` | List conversations |
| GET | `/api/v1/conversations/{id}/messages` | Get conversation history |
| POST | `/api/v1/conversations/{id}/messages` | Send text and receive text/audio response |
| POST | `/api/v1/conversations/{id}/audio` | Upload speech and receive transcript + response |
| GET | `/api/v1/audio/{audio_id}` | Retrieve authorized generated audio |
| DELETE | `/api/v1/audio` | Delete all of the user's generated audio, keeping message text |
| DELETE | `/api/v1/conversations/{id}` | Delete a conversation and its audio |
| POST | `/api/v1/conversations/{id}/messages/{message_id}/audio` | Retry voice generation for a reply |
| GET / PATCH | `/api/v1/me` | Read the current user; update the language setting |
| GET | `/api/v1/languages` | List the languages supported by voice cloning |

`{profile_id}` is the local profile UUID, never the provider's voice ID. Use cookie sessions rather than bearer tokens, because a browser `<audio src>` request cannot attach an `Authorization` header. Set the cookie as `HttpOnly` and `SameSite=Lax`, and as `Secure` in production.

### 5.1 Voice enrollment request

```http
POST /api/v1/voices
Content-Type: multipart/form-data
```

Form fields:

- `name`: display name.
- `language`: e.g. `en-IN`.
- `file`: audio file.
- `consent_confirmed`: must be `true`, or the request is rejected with 400.

Example response:

```json
{
  "id": "local-profile-uuid",
  "name": "My Voice",
  "provider": "sarvam",
  "status": "ready",
  "language": "en-IN"
}
```

Do not expose the provider's `voice_id` in public responses unless there is a clear product reason.

### 5.2 Text conversation request

```http
POST /api/v1/conversations/{conversation_id}/messages
Content-Type: application/json
```

```json
{
  "content": "Explain retrieval augmented generation.",
  "voice_profile_id": "local-profile-uuid",
  "generate_audio": true
}
```

Example response:

```json
{
  "user_message": {
    "id": "message-uuid",
    "content": "Explain retrieval augmented generation."
  },
  "assistant_message": {
    "id": "message-uuid",
    "content": "RAG combines information retrieval with language models..."
  },
  "audio": {
    "id": "audio-uuid",
    "url": "/api/v1/audio/audio-uuid",
    "content_type": "audio/wav"
  },
  "audio_error": null
}
```

If voice generation fails after Grok has responded, still return 200 with both messages, `"audio": null` and an `audio_error` object, so that the client can show the text and offer a retry.

### 5.3 Audio conversation request

```http
POST /api/v1/conversations/{conversation_id}/audio
Content-Type: multipart/form-data
```

Form fields:

- `file`: recorded audio.
- `voice_profile_id`: local voice profile ID.

Example response:

```json
{
  "user_message": {
    "id": "message-uuid",
    "content": "What is a vector database?"
  },
  "assistant_message": {
    "id": "message-uuid",
    "content": "A vector database stores and searches vector embeddings..."
  },
  "audio": {
    "id": "audio-uuid",
    "url": "/api/v1/audio/audio-uuid",
    "content_type": "audio/wav"
  },
  "audio_error": null
}
```

`user_message.content` is the transcript.

### 5.4 Error format

Use one error format on every endpoint. `stage` tells the client which part of the pipeline failed:

```json
{
  "error": {
    "code": "transcription_failed",
    "message": "We could not transcribe that recording. Please try again.",
    "stage": "transcribing",
    "retryable": true
  }
}
```

Use response schemas throughout. Do not return local filesystem paths.

---

## 6. Database design

Use PostgreSQL with SQLAlchemy 2.x and Alembic migrations.

### 6.1 Tables

#### users

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| email | VARCHAR | Unique |
| password_hash | VARCHAR | Never store raw password |
| created_at | TIMESTAMPTZ | Creation time |

#### voice_profiles

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| provider | VARCHAR | `sarvam` |
| provider_voice_id | VARCHAR, nullable | Saved provider voice ID; null until enrollment succeeds |
| name | VARCHAR | Display name |
| language | VARCHAR | BCP-47 code |
| reference_text | TEXT, nullable | Transcript returned by the provider |
| status | VARCHAR | pending, ready, failed, deleted |
| consent_confirmed_at | TIMESTAMPTZ | When the user confirmed the right to clone this voice |
| consent_text_version | VARCHAR | Version of the consent wording shown |
| created_at | TIMESTAMPTZ | Creation time |

Add a unique constraint or appropriate index for provider voice IDs and user ownership.

#### conversations

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| title | VARCHAR | Conversation title |
| created_at | TIMESTAMPTZ | Creation time |
| updated_at | TIMESTAMPTZ | Last activity |

#### messages

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key |
| conversation_id | UUID | FK to conversations |
| role | VARCHAR | user or assistant |
| content | TEXT | Transcript or assistant text |
| audio_asset_id | UUID, nullable | FK to audio_assets |
| created_at | TIMESTAMPTZ | Creation time |

#### audio_assets

| Column | Type | Notes |
|---|---|---|
| id | UUID | Primary key; the `{audio_id}` in the audio API |
| user_id | UUID | FK to users; used for the ownership check |
| kind | VARCHAR | voice_sample, utterance or generated |
| object_key | VARCHAR | Storage key; never returned to clients |
| content_type | VARCHAR | For example `audio/wav` |
| duration_seconds | DOUBLE PRECISION, nullable | Audio length |
| created_at | TIMESTAMPTZ | Creation time |
| deleted_at | TIMESTAMPTZ, nullable | When the audio was deleted |

#### provider_requests

Stores the usage fields listed in section 15. Do not store API secrets in these tables.

### 6.2 Data ownership

Every voice profile, conversation, message, and audio object must be scoped to the authenticated user. Never trust a client-supplied user ID or profile ID without checking ownership.

---

## 7. Audio capture and processing

### 7.1 Browser recording

Use the browser MediaRecorder API. Request microphone permission only after the user clicks the record button.

The browser may produce WebM/Opus depending on browser support. Sarvam STT accepts WebM, but voice enrollment does not. Stop conversation recordings at `MAX_UTTERANCE_SECONDS`, because the STT endpoint is for audio under 30 seconds. The backend should:

1. Check file size.
2. Check the declared MIME type and inspect the actual file.
3. Validate duration and decodeability.
4. Normalize to a provider-supported format when needed.
5. Reject empty, corrupt, or excessively long recordings.
6. Avoid logging or retaining raw audio unnecessarily.

For reliable conversion, use FFmpeg to convert enrollment samples to WAV. For example, this produces mono 16 kHz WAV, the rate at which Sarvam says STT works best:

```bash
ffmpeg -i input.webm -ac 1 -ar 16000 output.wav
```

Sarvam does not document a preferred sample rate for enrollment, so compare clone quality at 16 kHz and at a higher rate during Milestone 0.

### 7.2 Voice sample quality

Provide recording guidance in the UI:

- Record in a quiet room.
- Use one speaker only.
- Keep the microphone at a consistent distance.
- Speak naturally and clearly.
- Avoid music, echo, clipping, and background conversations.
- Obtain explicit consent from the voice owner.

Sarvam's current voice enrollment guide recommends a short clean sample of approximately 10–15 seconds. Treat this as a provider recommendation and re-check the current limits.

### 7.3 Audio storage

For local development, store files outside the public frontend directory. In production, use private object storage with short-lived signed URLs.

Define retention rules. Users should be able to delete their source recording, generated audio, and cloned voice profile. Deleting a local database row alone does not delete a provider-hosted voice.

---

## 8. Frontend requirements

### 8.1 Pages

1. **Dashboard**
   - Voice profile status.
   - Create voice profile action.
   - Recent conversations.

2. **Voice enrollment**
   - Microphone permission.
   - Record, stop, preview, re-record.
   - Upload progress.
   - Enrollment status and errors.

3. **Conversation**
   - Message list.
   - Text input.
   - Record/stop controls.
   - Transcript preview.
   - Assistant response.
   - Audio player.
   - Loading and retry states.

4. **Settings**
   - Selected voice profile.
   - Language preference, limited to the languages supported by voice cloning.
   - Audio retention and deletion controls.

### 8.2 Conversation UI states

Model the interaction explicitly. The MVP sends one request and receives one response, so the browser cannot see which provider stage is running:

```text
idle
  -> recording
  -> uploading
  -> processing
  -> playing
  -> idle
```

Once server events are added in Milestone 5, replace `processing` with `transcribing`, `generating_text` and `generating_audio`.

Failure states should identify the failed stage, using the `stage` field from section 5.4:

- microphone permission denied
- upload failed
- unsupported audio
- transcription failed
- LLM request failed
- voice generation failed
- playback failed

If TTS fails after Grok has responded, still show the text response. Do not discard a valid LLM response because audio generation failed.

### 8.3 Frontend API service

Keep HTTP calls in a single API client module. Handle authentication, timeouts, cancellation, and error normalization centrally.

Do not put provider API keys in Vite variables prefixed with `VITE_`; those values are exposed to browser bundles.

---

## 9. Latency and real-time roadmap

The MVP is request/response. Measure each stage separately:

```text
Total response latency =
  upload
  + STT
  + LLM
  + TTS
  + audio delivery
```

Record timestamps for each stage. Use provider request IDs for troubleshooting, but do not log secret headers or sensitive audio.

### Later improvements

1. Stream Grok output (the Responses API supports `stream=True`).
2. Split assistant text into sentence-sized chunks.
3. Generate TTS chunks as text becomes available, if the Sarvam streaming API supports the chosen workflow.
4. Stream audio to the browser.
5. Add WebSocket session events.
6. Add barge-in/interruption handling.
7. Consider WebRTC or a voice-agent framework if full-duplex real-time conversation becomes a requirement.

Do not claim the first version is real-time speech-to-speech. It is a chained voice pipeline. Measure end-to-end latency before setting a target.

---

## 10. Error handling and reliability

Create provider-specific exceptions and map them to stable application errors.

| Failure | Backend behavior |
|---|---|
| Sarvam 401 / 403 | Report provider authentication/configuration error; do not retry |
| Sarvam 402 | Report that provider quota is exhausted; do not retry |
| Sarvam 403 `TIER_LIMIT_REACHED` | Report that the voice limit is reached; do not retry |
| Sarvam 422 on enrollment | Ask the user to re-record; the sample may have failed quality validation |
| Sarvam 429 | Retry with exponential backoff |
| Sarvam 5xx / timeout | Bounded retry where safe |
| Grok 401 | Report xAI configuration error |
| Grok 429 | Respect rate limits and retry guidance |
| Grok 5xx / timeout | Bounded retry; nothing is saved until the LLM replies, so the client can safely resend |
| Empty LLM response | Return a controlled generation error |
| TTS failure | Preserve and return the text response |
| Invalid audio | Return 400 with supported-format guidance |
| Unknown voice profile | Return 404 |
| Profile belongs to another user | Return 404 or 403 without leaking ownership |

Use timeouts for every external request. Retry only transient errors and use exponential backoff with jitter. Do not retry voice creation blindly: a timeout may occur after the provider created the voice. Use request tracking and reconciliation before retrying a potentially non-idempotent operation: send the local profile UUID as the Sarvam voice `name`, and after a timeout call `GET /voices?search=<uuid>` to check whether the voice was created. Show the display name only from the local database.

---

## 11. Security, consent and privacy

Voice is biometric-like personal data. Treat it as sensitive.

Required safeguards:

- Clone only the user's own voice or a voice for which explicit permission exists.
- Show a clear consent confirmation before enrollment, and store when it was given and which wording was shown. The Sarvam API has no consent field, so this record is the application's own evidence.
- Do not enable public voice sharing by default.
- Store provider keys only on the backend.
- Encrypt transport with HTTPS.
- Restrict audio objects to their owner.
- Apply upload size and duration limits.
- Rate-limit enrollment and generation endpoints.
- Avoid logging raw audio, full secrets, or unnecessary transcripts.
- Provide voice-profile deletion and source-audio deletion.
- Delete the provider-side clone with `DELETE /voices/delete/{voice_id}` when a user deletes their profile. Treat a provider 404 as already deleted. If the call fails for another reason, keep the local record and retry, so that no clone is orphaned at the provider.
- Set `store=False` on Grok requests so that transcripts are not retained by xAI for 30 days.
- Explain that generated speech is AI-generated where it is presented or shared.
- Define retention and backup deletion policies.

Do not use voice cloning to impersonate another person, bypass identity verification, or deceive listeners.

---

## 12. Testing strategy

### 12.1 Unit tests

Test without calling paid external APIs:

- Audio validation.
- Conversation history construction.
- Prompt construction.
- Provider response normalization.
- Ownership checks.
- Error mapping.
- Text chunking for TTS limits.

Mock the STT, LLM, and voice provider interfaces.

### 12.2 Integration tests

Use test credentials and short controlled recordings:

1. Verify Sarvam authentication.
2. Create a voice profile.
3. Generate a short phrase with the saved voice.
4. Transcribe a sample recording.
5. Send a prompt to Grok.
6. Run the complete STT → Grok → TTS flow.
7. Verify generated audio is playable.
8. Verify provider errors do not expose credentials.

### 12.3 Acceptance criteria for MVP

- A user can record and preview a voice sample.
- A valid sample can create a saved Sarvam voice profile.
- The application stores the returned provider voice ID securely.
- A user can send text and receive a Grok response.
- The response can be synthesized using the selected saved voice.
- A user can submit recorded speech and receive a transcript, response text, and generated audio.
- Conversation messages persist in PostgreSQL.
- TTS failure does not lose the text response.
- Another user cannot access the voice profile or audio (tested with a second seeded user).
- API keys are never present in browser bundles or Git history.

---

## 13. Development setup

Assume Python 3.12, Node.js LTS, Docker (or a local PostgreSQL server) and FFmpeg.

Install FFmpeg on Windows, then open a new terminal so that it is on `PATH`:

```powershell
winget install Gyan.FFmpeg
```

### 13.1 Backend environment

From the repository root, copy `.env.example` to `.env`, fill in the keys, and start PostgreSQL:

```bash
docker compose up -d
```

`docker-compose.yml` should define a PostgreSQL service that matches `DATABASE_URL`. If a local PostgreSQL server already uses port 5432, stop it or change the mapped port.

Then create the Python environment:

```bash
cd backend

python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activate on WSL/Ubuntu:

```bash
source .venv/bin/activate
```

Install initial dependencies:

```bash
pip install fastapi "uvicorn[standard]" pydantic-settings
pip install sqlalchemy asyncpg alembic
pip install python-multipart httpx openai "pwdlib[argon2]"
pip install "sarvamai>=0.1.37"
pip install pytest pytest-asyncio
```

Pin exact tested versions in `requirements.txt` after the first successful integration. Confirm that the installed Sarvam SDK exposes the required voice-cloning methods.

Once migrations exist (Milestone 1), apply them and run the API:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

Open:

```text
http://localhost:8000/docs
```

### 13.2 Frontend environment

From the repository root:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm run dev
```

Use:

```text
http://localhost:5173
```

### 13.3 Environment checklist

Before testing provider calls:

- [ ] Sarvam API key is available in the root `.env`.
- [ ] xAI API key is available in the root `.env`.
- [ ] A valid xAI model ID is configured.
- [ ] `ffmpeg -version` works in a new terminal.
- [ ] Sarvam voice cloning is enabled for the account.
- [ ] The account has sufficient credits/quota.
- [ ] Microphone access works on localhost.
- [ ] `.env` and audio storage are excluded from Git.

---

## 14. Implementation milestones

Build in this order. Do not implement all layers simultaneously.

### Milestone 0 — Verify provider access

**Goal:** Confirm both existing API keys work and Sarvam voice cloning is enabled.

Tasks:

- Create a minimal Python script for Grok text generation.
- Create a minimal Python script for Sarvam STT.
- Create a short test recording of your own voice.
- Create a Sarvam voice profile.
- Generate a short phrase using that profile.
- Delete a test voice, confirming that it is removed at the provider.
- Confirm that `AsyncSarvamAI` voice-cloning calls and Grok's `store=False` work as expected.
- Save the provider request IDs and record latency/errors.
- Chain the three operations in one script (see section 18).

**Exit criteria:** All three provider operations work independently (STT, Grok, and cloned TTS) and together in the chained script.

### Milestone 1 — Backend foundation

Tasks:

- Create FastAPI project structure.
- Add Pydantic settings.
- Add PostgreSQL connection.
- Add SQLAlchemy models and Alembic, starting with `users` and `voice_profiles`.
- Add health endpoint.
- Add login with a single seeded user and cookie sessions, and scope all data queries to that user.
- Add provider interfaces and mocked tests.
- Scaffold the Vite frontend with the login page and API client.

**Exit criteria:** Backend starts, database connects, migrations run, tests pass, and the seeded user can log in from the frontend.

### Milestone 2 — Voice enrollment

Tasks:

- Build browser recording component.
- Add the consent confirmation and store the consent record.
- Add audio upload endpoint.
- Validate and normalize audio.
- Integrate Sarvam voice creation.
- Persist local profile and provider voice ID.
- Add profile listing and deletion.

**Exit criteria:** A user can create, retrieve, and delete their own voice profile.

### Milestone 3 — Text chat with voice output

Tasks:

- Add the conversation, message, audio asset and provider request tables.
- Integrate Grok.
- Persist user and assistant messages.
- Integrate Sarvam cloned TTS.
- Return generated audio.
- Add frontend audio playback.

**Exit criteria:** User sends text and hears the answer in their enrolled voice.

### Milestone 4 — Speech conversation

Tasks:

- Capture microphone audio.
- Upload audio to FastAPI.
- Integrate Sarvam STT.
- Show transcript for confirmation/debugging.
- Pass transcript to conversation service.
- Generate cloned audio.
- Handle partial failures gracefully.

**Exit criteria:** User speaks, the application understands, responds, and plays audio in the enrolled voice.

### Milestone 5 — Real-time improvements

Tasks:

- Measure per-stage latency.
- Add streaming where provider APIs permit.
- Add sentence/chunk handling.
- Add WebSocket events if useful.
- Add cancellation and interruption behavior.
- Load-test concurrent sessions.

**Exit criteria:** Measured latency and reliability meet the product's chosen target.

### Milestone 6 — Production hardening

Tasks:

- Multi-user registration, account management and authorization review.
- Private object storage.
- Secrets management.
- Rate limits and quotas.
- Structured logs and metrics.
- Data deletion workflows.
- Docker deployment and CI/CD.
- Security and privacy review.

**Exit criteria:** Deployable application with documented operational and privacy controls.

---

## 15. Cost and quota considerations

The application makes separate provider calls:

- STT usage for each user utterance.
- Grok usage for each assistant response.
- Cloned TTS usage for each generated response.
- Optional storage and infrastructure costs.

Check current provider pricing, model availability, request limits, and account quotas before estimating per-conversation cost. Do not hardcode assumed prices.

Add a usage table with:

- user ID
- provider
- operation
- provider request ID
- model
- input/output usage where returned
- latency
- status
- timestamp

This makes it possible to estimate the cost of a conversation and identify slow or failing stages.

---

## 16. Risks and technical decisions

| Risk | Mitigation |
|---|---|
| Sarvam voice cloning is beta | Verify access early; keep a provider abstraction |
| Short voice sample quality varies | Provide recording guidance and test multiple samples |
| Browser audio format mismatch | Validate and normalize server-side |
| TTS text length limit | Split long output into chunks |
| Provider latency | Measure stages; add streaming later |
| Provider outage or quota exhaustion | Return text if TTS fails; handle 429/5xx safely |
| Duplicate voice creation after timeout | Track enrollment attempts and reconcile before retry |
| Sensitive voice data | Consent, access control, encryption and deletion |
| Model ID changes | Configure model ID through environment variables |

### Important design decision

Although Sarvam currently provides STT, TTS, and instant voice cloning, keep these as separate adapters. This lets the project replace one capability without replacing the whole stack.

If Sarvam voice cloning is unavailable on your account or does not meet quality requirements, the fallback can be a self-hosted open-source voice-cloning model. Evaluate model license, commercial-use restrictions, hardware requirements, and voice quality before selecting one. Do not add that complexity until the Sarvam proof of concept is complete.

---

## 17. Official references

### Sarvam

- [Sarvam API introduction](https://docs.sarvam.ai/api-reference/introduction)
- [Sarvam model APIs overview](https://docs.sarvam.ai/api/getting-started/welcome)
- [Sarvam model selection](https://docs.sarvam.ai/api/getting-started/models)
- [Instant Voice Cloning overview](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/overview)
- [Create Voice API](https://docs.sarvam.ai/api-reference/voice-cloning/create-voice)
- [Generate cloned speech API](https://docs.sarvam.ai/api-reference/voice-cloning/clone)
- [Delete Voice API](https://docs.sarvam.ai/api-reference/voice-cloning/delete-voice)
- [List Voices API](https://docs.sarvam.ai/api-reference/voice-cloning/list-voices)
- [Commercial licensing](https://docs.sarvam.ai/api/getting-started/commercial-licensing)
- [Libraries and SDKs](https://docs.sarvam.ai/api/getting-started/sdks)
- [Voice cloning FAQ](https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/faq)

### xAI

- [xAI developer documentation](https://docs.x.ai/)
- [xAI REST API reference](https://docs.x.ai/developers/rest-api-reference)
- [Responses API](https://docs.x.ai/developers/rest-api-reference/inference/responses)
- [Comparison with Chat Completions](https://docs.x.ai/developers/model-capabilities/text/comparison)
- [Models](https://docs.x.ai/developers/models)

### Frameworks

- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [Vite](https://vite.dev/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Sarvam Python SDK](https://pypi.org/project/sarvamai/)

---

## 18. First task: provider proof of concept

Before building the UI, create these scripts. They use a `check_` prefix so that `pytest` does not collect them and spend provider credits:

```text
backend/
└── poc/
    ├── check_llm.py
    ├── check_stt.py
    ├── check_sarvam_voice_clone.py
    └── check_pipeline.py
```

Run them in this order:

1. `check_llm.py`: send a simple text prompt and print the response.
2. `check_stt.py`: submit a short recording and print its transcript.
3. `check_sarvam_voice_clone.py`: create a voice from your own sample, save the returned `voice_id`, synthesize a short phrase, and play the result. Reuse the saved `voice_id` on later runs rather than creating another voice, because saved voices are capped.
4. `check_pipeline.py`: chain the previous steps using a recorded sentence and the saved `voice_id`.

Only after all four pass should you build the integrated conversation endpoint.

**Definition of done for the first proof of concept:** `check_pipeline.py` transcribes a sentence you recorded, Grok generates a reply, and Sarvam speaks that reply using your authorized cloned voice.

---

*This document is an implementation plan, not a guarantee that provider access, quotas, beta features, SDK signatures, or model IDs will remain unchanged. Verify the linked official API references and your account's enabled capabilities during implementation.*
