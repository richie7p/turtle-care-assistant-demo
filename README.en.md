# 🐢 Turtle Care Assistant — NVIDIA NIM RAG Demo

[繁體中文](README.md) | **English**

[![CI](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml)

A complete domain demonstration of the [NVIDIA NIM RAG Platform](https://github.com/richie7p/nvidia-nim-rag-platform). Turtle care is used to show how the shared platform combines structured profiles, private image uploads, vision analysis, retrieval-augmented generation, medical-safety guidance, and an operational admin console.

Every installation must use its own NVIDIA NIM API key. This repository contains no author key, account, database, or default password.

## What the demo includes

- Multiple turtle profiles with species, aquatic or terrestrial type, size, habitat, UVB, heating, and diet fields
- A turtle can be attached to a conversation and its profile is injected into the AI context
- JPEG, PNG, and WebP analysis with content validation, EXIF removal, dimension limits, and upload-count limits
- Twelve Traditional Chinese demonstration documents covering aquatic turtles, tortoises, UVB, water quality, temperature, humidity, filtration, basking, feeding, calcium, enclosure safety, and warning signs
- Document-level RAG citations; the assistant must not fabricate a source when retrieval finds no qualified result
- Image responses are limited to observable findings and must not diagnose a condition from a photo alone
- Natural escalation to a reptile veterinarian for bleeding, serious injury, breathing abnormalities, prolonged refusal to eat, or other high-risk signs
- Per-user isolation for profiles, conversations, messages, and attachments
- Admin views for platform usage, AI requests, knowledge synchronization, NVIDIA NIM health, and audited management actions

## Requirements

- Git
- Python 3.11
- Node.js 22 or newer; the current LTS release is recommended
- Your own NVIDIA NIM API key
- Network access to `https://integrate.api.nvidia.com`

Sign in on [NVIDIA Build](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512) and select **Generate API Key**. Hosted NIM runs in NVIDIA's cloud, so the demo does not require an NVIDIA GPU or a local model download. NVIDIA's hosted trial endpoints may have quota and traffic limits; check the current NVIDIA terms for your use case.

## Quick start on Windows

```powershell
git clone https://github.com/richie7p/turtle-care-assistant-demo.git
Set-Location turtle-care-assistant-demo
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location frontend
npm.cmd ci
Set-Location ..
Copy-Item .env.example .env
```

Generate a session secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output and your NVIDIA key into `.env`:

```env
SESSION_SECRET=replace_with_a_random_value_of_at_least_32_characters
AI_API_KEY=your_NVIDIA_NIM_API_key
```

Initialize the database, create an administrator interactively, validate the bundled documents, build their embeddings, and start the application:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.cli init-db
..\.venv\Scripts\python.exe -m app.cli create-admin
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
..\.venv\Scripts\python.exe -m app.cli sync-knowledge
Set-Location ..
.\start.cmd
```

`start.cmd` builds the frontend, applies migrations, and starts FastAPI. It also avoids the persistent PowerShell Execution Policy change that running a `.ps1` directly may require. Open <http://127.0.0.1:8000>. No default login is provided.

## Quick start on macOS or Linux

```bash
git clone https://github.com/richie7p/turtle-care-assistant-demo.git
cd turtle-care-assistant-demo
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cd frontend
npm ci
cd ..
cp .env.example .env
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the generated secret and your NVIDIA key into `.env`, then run:

```bash
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.cli init-db
../.venv/bin/python -m app.cli create-admin
../.venv/bin/python -m app.cli validate-knowledge
../.venv/bin/python -m app.cli sync-knowledge
cd ..
bash scripts/start.sh
```

Open <http://127.0.0.1:8000>. Run `chmod +x scripts/start.sh` if you want to invoke the script directly.

## First-run verification

1. Open <http://127.0.0.1:8000/api/health> and confirm that `status` is `ok` and `configured` is `true`.
2. Sign in as the administrator and run the NVIDIA provider check. Confirm that Chat, Vision, and Embedding models are available.
3. Register a regular test user, create a turtle profile, start a conversation, and select that turtle.
4. Ask a bundled-document question such as “What does UVB lighting do?” and verify a streamed response plus citation cards.
5. Upload a test image without private information and verify image analysis. Health-related output must not diagnose solely from the photo.

`/api/health` reports whether a key is present; it does not prove that the key is valid. Use the provider check and the smoke tests above to verify live connectivity and quality.

## How this demonstrates a reusable platform

The turtle module is enabled with:

```env
ENABLE_TURTLE_MODULE=true
SYSTEM_PROMPT_FILE=./prompts/assistant.md
KNOWLEDGE_DIR=./knowledge
```

The generic platform edition sets `ENABLE_TURTLE_MODULE=false` and ships with generic branding, a generic prompt, and an empty knowledge directory. Authentication, conversations, RAG, citations, usage logging, administration, access control, and the NVIDIA provider are shared application code.

Replacing Markdown knowledge, branding, and prompts does not require code changes. Replacing a Turtle Profile with a Student Profile or another structured domain object does require database, API, and frontend changes. The `ModelProvider` interface establishes an extension boundary, but NVIDIA Hosted NIM is the only provider implemented today; vLLM is not bundled.

## Replace the turtle-care knowledge

Add, edit, or remove files under `knowledge/**/*.md`, then run:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.cli validate-knowledge
..\.venv\Scripts\python.exe -m app.cli sync-knowledge
```

Plain Markdown is supported. Optional YAML frontmatter supplies source metadata, tags, and a review date. The generic platform repository contains a more detailed frontmatter example.

The 12 bundled documents demonstrate chunking, embeddings, retrieval, and citations. They are project demonstration content and have not been reviewed by a veterinarian. Before a real deployment, have a qualified content owner review them or replace them with your organization's properly licensed material.

## Default NVIDIA models

- Chat: [`mistralai/ministral-14b-instruct-2512`](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512)
- Fallback: [`mistralai/mistral-nemotron`](https://build.nvidia.com/mistralai/mistral-nemotron)
- Vision: [`mistralai/ministral-14b-instruct-2512`](https://build.nvidia.com/mistralai/ministral-14b-instruct-2512)
- Embeddings: [`nvidia/llama-nemotron-embed-1b-v2`](https://build.nvidia.com/nvidia/llama-nemotron-embed-1b-v2/modelcard)

The default Ministral model accepts text and images, and its NVIDIA model information lists Chinese among the supported languages. The embedding model is documented for multilingual and cross-lingual retrieval, including Chinese. Hosted model availability can change, and every identifier is configurable in `.env`. Before presenting the demo, run text, image, and embedding smoke tests with your own private key and representative turtle images.

## Server deployment

The local quick start listens only on `127.0.0.1`. At minimum, set these values for an internet-facing installation:

```env
APP_ENV=production
APP_ORIGIN=https://assistant.example.org
SESSION_SECRET=a_unique_long_random_value
```

Start one application process behind Caddy, Nginx, or a cloud load balancer:

```bash
APP_HOST=0.0.0.0 APP_PORT=8000 bash scripts/start.sh
```

On Windows Server, use: `$env:APP_HOST='0.0.0.0'; $env:APP_PORT='8000'; .\start.cmd`.

The reverse proxy must provide HTTPS, and `APP_ORIGIN` must exactly match the origin used by the browser. Persist and back up `backend/data/` and `backend/uploads/`. SQLite is suitable for a single-machine demo; a multi-instance deployment first needs a PostgreSQL driver, validated migrations, shared rate limiting, and staging integration tests. See the [platform README](https://github.com/richie7p/nvidia-nim-rag-platform/blob/main/README.en.md#server-deployment) for the full boundary.

## Tests

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Automated tests use an internal fake provider. They validate application behavior without exposing a real API key. GitHub Actions runs the suite on `windows-latest`, `ubuntu-latest`, and `macos-latest`. On macOS or Linux, replace the Windows Python path with `../.venv/bin/python` and `npm.cmd` with `npm`. Live NVIDIA NIM connectivity must be smoke-tested separately with a private key.

## Troubleshooting

- `start.ps1 cannot be loaded`: run `.\start.cmd` from the repository root. It applies Execution Policy Bypass only to that launch.
- `.venv was not found`: confirm that the shell is in the cloned repository root, then repeat the virtual-environment and pip-install steps.
- The API says the frontend was not built: run `npm ci` and `npm run build` in `frontend/`, or run the start script again.
- AI reports that it is not configured: make sure the root `.env` contains `AI_API_KEY`, then restart the service.
- No knowledge citations appear: as an administrator, run `validate-knowledge` and `sync-knowledge`; synchronization consumes NVIDIA embedding quota.
- A model returns 404 or becomes unavailable: select a currently hosted model on NVIDIA Build, update its ID in `.env`, and synchronize again if the embedding model changed.
- Port 8000 is occupied: stop the old service or set another port. On PowerShell, for example: `$env:APP_PORT='8010'; .\start.cmd`.

## Safety and privacy

- `.env`, databases, uploads, and API keys are excluded from Git.
- The API key is used only by FastAPI and is never sent to the React browser.
- Revoke and replace any key that has been shared publicly.
- Uploaded images are private and served through authenticated endpoints.
- The application provides general husbandry information and cannot replace diagnosis by a qualified reptile veterinarian.
- Review retention, backup, consent, and access-control requirements before storing real user or institutional data.

## License

MIT

## Upgrading an existing installation

Stop the service and back up the database and uploads before updating. After updating the code, run `python -m alembic upgrade head` from `backend/` using the project virtual environment, then restart the service. Run the migration before synchronizing knowledge.

This migration snapshots existing answer citations so their original title, source and section survive knowledge updates. Citations deleted before this upgrade cannot be recovered by the migration.
