# 🐢 Turtle Care Assistant — NVIDIA NIM RAG Demo

[繁體中文](README.md) | **English**

[![CI](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/richie7p/turtle-care-assistant-demo/actions/workflows/ci.yml)

A complete domain demonstration of the [NVIDIA NIM RAG Platform](https://github.com/richie7p/nvidia-nim-rag-platform). Turtle care is used to show how the shared platform combines structured profiles, private image uploads, vision analysis, retrieval-augmented generation, medical-safety guidance, and an operational admin console.

Every installation must use its own NVIDIA NIM API key. This repository contains no author key, account, database, or default password.

## What the demo includes

- Multiple turtle profiles with species, aquatic or terrestrial type, size, habitat, UVB, heating, and diet fields
- A turtle can be attached to a conversation and its profile is injected into the AI context
- JPEG, PNG, and WebP analysis with content validation, EXIF removal, dimension limits, and upload-count limits
- Twelve Traditional Chinese reference documents covering aquatic turtles, tortoises, UVB, water quality, temperature, humidity, filtration, basking, feeding, calcium, enclosure safety, and warning signs
- Source-linked RAG answers; the assistant must not fabricate citations when retrieval finds no qualified result
- Image responses are limited to observable findings and must not diagnose a condition from a photo alone
- Natural escalation to a reptile veterinarian for bleeding, serious injury, breathing abnormalities, prolonged refusal to eat, or other high-risk signs
- Per-user isolation for profiles, conversations, messages, and attachments
- Admin views for platform usage, AI requests, knowledge synchronization, NVIDIA NIM health, and audited management actions

## Requirements

- Python 3.11
- Node.js 22 or newer
- Your own NVIDIA NIM API key

## Quick start on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Set-Location frontend
npm.cmd install
Set-Location ..
Copy-Item .env.example .env
```

Edit `.env`:

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

Open <http://127.0.0.1:8000>. No default login is provided.

## Quick start on macOS or Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
cd frontend
npm install
cd ..
cp .env.example .env
```

After editing `.env`:

```bash
cd backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m app.cli init-db
../.venv/bin/python -m app.cli create-admin
../.venv/bin/python -m app.cli validate-knowledge
../.venv/bin/python -m app.cli sync-knowledge
cd ..
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

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

## Default NVIDIA models

- Chat: `nvidia/nemotron-3-nano-30b-a3b`
- Fallback: `mistralai/mistral-nemotron`
- Vision: `nvidia/nemotron-nano-12b-v2-vl`
- Embeddings: `nvidia/llama-nemotron-embed-1b-v2`

Hosted model availability can change. All identifiers are configurable in `.env`.

NVIDIA's current [vision model card](https://build.nvidia.com/nvidia/nemotron-nano-12b-v2-vl/modelcard) lists the default vision model's supported language as English only. Before presenting Traditional Chinese image analysis as a production capability, run a live Chinese smoke test with a private key and switch to a model that explicitly supports the target language if required.

## Tests

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

Automated tests use an internal fake provider. They validate application behavior without exposing a real API key; live NVIDIA NIM connectivity must be smoke-tested separately with a private key.

## Safety and privacy

- `.env`, databases, uploads, and API keys are excluded from Git.
- The API key is used only by FastAPI and is never sent to the React browser.
- Revoke and replace any key that has been shared publicly.
- Uploaded images are private and served through authenticated endpoints.
- The application provides general husbandry information and cannot replace diagnosis by a qualified reptile veterinarian.
- Review retention, backup, consent, and access-control requirements before storing real user or institutional data.

## License

MIT
