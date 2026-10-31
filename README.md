# Personal Voice AI

Speak to an AI assistant and hear replies in your own cloned voice. The pipeline is speech-to-text (Sarvam), then the LLM (Groq or xAI), then cloned speech (Sarvam). See [Documentation.md](Documentation.md) for the full design.

## Setup

Requires conda, Node.js and PostgreSQL. Copy `.env.example` to `.env` and fill it in.

```powershell
conda activate environ
cd backend
pip install -r requirements-dev.txt
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

To also run them on PostgreSQL, which enforces foreign keys, set `TEST_DATABASE_URL` to an empty, throwaway database first. The tests drop every table in it, so never point it at `voice_db`.

## CI/CD

| When | What runs |
|---|---|
| Pull request | [CI](.github/workflows/ci.yml): backend tests on SQLite and PostgreSQL, migrations both ways, frontend lint and build, dependency audits, secret scan, and a smoke test of the production stack |
| Push to `main` or a `v*` tag | [Release](.github/workflows/release.yml): CI, then publishes images to GitHub Container Registry, then deploys if enabled |
| Started by hand | [Roll back](.github/workflows/rollback.yml): deploys an earlier published image |

Dependabot opens weekly update pull requests. To stop a broken change reaching `main`, protect the branch in GitHub and require the CI checks.

### Turn on automatic deployment

Publishing images works without any setup. Deployment stays off until you do the following.

1. On a Linux server with Docker, point your domain's DNS at it and open ports 80 and 443.
2. Create a folder such as `/opt/voice-ai` and copy `.env.production.example` into it as `.env.production`, then fill it in.
3. Create an SSH key only for deployments, and add its public key to the server's `authorized_keys`. That server user must be able to run Docker, which gives it full control of the server, so use a dedicated machine or user.
4. In the GitHub repository settings, create an environment named `production` with these values. Add required reviewers to it if you want to approve each deployment.

| Kind | Name | Value |
|---|---|---|
| Secret | `DEPLOY_HOST` | The server's address |
| Secret | `DEPLOY_USER` | The SSH user |
| Secret | `DEPLOY_SSH_KEY` | The private deploy key |
| Secret | `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan your-server`, after confirming it is the right server |
| Variable | `DEPLOY_PATH` | For example `/opt/voice-ai` |
| Variable | `DEPLOY_URL` | For example `https://voice.example.com` |

5. Add a repository variable `DEPLOY_ENABLED` set to `true`.
6. After the first deployment, create your login on the server:

```bash
cd /opt/voice-ai
export IMAGE_PREFIX=ghcr.io/<owner>/<repository> IMAGE_TAG=latest
docker compose -f docker-compose.prod.yml --env-file .env.production exec backend python -m app.seed --email you@example.com
```

### Roll back

Run **Roll back** from the Actions tab with an earlier tag such as `sha-<commit hash>`.

The backend applies migrations when it starts, and an older image cannot start on a database migrated past what it knows. If the versions between differ in `backend/alembic/versions`, first run `alembic downgrade <revision>` in the newer backend container. Downgrades can remove data, so back up the database first.

### Back up production data

The `db_data` and `audio_data` Docker volumes hold everything. Nothing backs them up automatically, so set up regular backups on the server.

### Try the production stack locally

```powershell
$env:DOMAIN='localhost:8443'; $env:HTTP_PORT='8080'; $env:HTTPS_PORT='8443'
$env:SESSION_SECRET='local-only-session-secret-0123456789abcdef'; $env:DB_PASSWORD='local-only'
docker compose -f docker-compose.prod.yml up -d --build --wait
```

Open https://localhost:8443 and accept the certificate warning. Compose also reads your local `.env` here. Stop it with `docker compose -f docker-compose.prod.yml down -v`, which deletes this stack's data.

## Usage records

Every provider call adds a row to `provider_requests`: the provider's request ID, operation, model, characters, tokens, audio length, latency and outcome. Conversation text is never stored there. A long reply gets one row per speech chunk, because each is a separate billed call. Sarvam's voice creation and deletion responses have no request ID on success, so those rows have one only on failure.

Quote `provider_request_id` when contacting a provider's support. To find slow or failing stages:

```sql
SELECT provider, operation, status, count(*), round(avg(latency_ms)) AS avg_ms,
       sum(input_characters) AS characters, sum(input_tokens) AS tokens_in,
       sum(output_tokens) AS tokens_out, round(sum(audio_seconds)) AS audio_seconds
FROM provider_requests
WHERE created_at > now() - interval '7 days'
GROUP BY provider, operation, status
ORDER BY provider, operation, status;
```

## Switch to xAI Grok

In `.env`, set `LLM_PROVIDER=xai` and `XAI_API_KEY` to your xAI key. Each provider only ever receives its own key.

## Rate limits

Defaults are 10 login attempts per minute per IP address, 5 voice enrollments per hour per user, and 30 conversation turns per minute per user. Override them with `LOGIN_ATTEMPTS_PER_MINUTE`, `ENROLLMENTS_PER_HOUR` and `TURNS_PER_MINUTE`.

The counters live in one server process, so running several workers needs a shared store such as Redis. Behind a proxy, every client shares one IP address until the proxy's forwarded address is trusted.
