# Gustave Code

**Personal local AI assistant** powered by open-source uncensored LLMs, running entirely on your hardware. Your data never leaves your machine.

Built with **React** + **FastAPI** + **LangChain** + **Ollama**.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Multi-model profiles** — Switch between quality tiers on the fly:
  - **Fast** (JOSIEFIED Qwen3 8B) — Ultra-fast, 100% VRAM, ~80-100 tok/s
  - **LLaMA** (LLaMA 3.3 70B) — High quality, 128K context
  - **Mixtral** (Dolphin 8x22B) — Maximum quality MoE
- **Streaming SSE** — Real-time token-by-token responses with thinking indicators
- **Background streaming** — Navigate between conversations while a response generates
- **Tool use** — Calculator, date/time, Wikipedia, web search (DuckDuckGo + Tavily)
- **Long-term memory** — ChromaDB vector store for persistent context across sessions
- **Conversation management** — Full CRUD with sidebar, search, and date grouping
- **Control panel** — Desktop launcher with service management, logs, and health monitoring
- **Uncensored models** — Abliterated models with no refusal filters
- **100% local** — No cloud dependency, no data exfiltration

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | RTX 3060 12GB | RTX 3080 12GB+ |
| RAM | 32 GB | 64 GB |
| CPU | 8 cores | 16 cores (Ryzen 9) |
| Storage | 50 GB free | 150 GB free (all models) |

## Architecture

```
gustave-code/
├── launcher.py          # Desktop control panel (port 9000)
├── dashboard.html       # Launcher UI
├── backend/             # FastAPI + LangChain
│   ├── app/
│   │   ├── config.py          # Model profiles & settings
│   │   ├── main.py            # FastAPI entry point
│   │   ├── routers/           # API endpoints
│   │   │   ├── chat.py        # POST /chat (SSE streaming)
│   │   │   ├── conversations.py
│   │   │   ├── health.py
│   │   │   └── models.py
│   │   ├── services/
│   │   │   ├── agent.py       # LangChain agent orchestration
│   │   │   ├── llm_service.py # LLM provider abstraction
│   │   │   ├── memory_service.py
│   │   │   └── tools/         # Calculator, web search, etc.
│   │   ├── database/          # SQLAlchemy ORM
│   │   └── models/            # Pydantic schemas
│   └── requirements.txt
├── frontend/            # React 18 SPA
│   └── src/
│       ├── App.jsx
│       ├── hooks/useChat.js   # SSE streaming + background support
│       ├── components/        # ChatWindow, Sidebar, InputBar, etc.
│       └── api/client.js      # Axios + Fetch SSE
├── modelfiles/          # Custom Ollama model profiles
├── data/                # ChromaDB vector store (gitignored)
└── docker-compose.yml   # Full stack containerization
```

## Installation

### Step 1 — Install prerequisites

| Tool | Version | Download |
|------|---------|----------|
| **Ollama** | Latest | [ollama.com/download](https://ollama.com/download) |
| **Python** | 3.11+ | [python.org/downloads](https://python.org/downloads) |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org) |
| **Git** | Any | [git-scm.com](https://git-scm.com) |

> **Tip:** On Windows, check "Add to PATH" during Python and Node.js installation.

### Step 2 — Clone the repository

```bash
git clone https://github.com/Inerio/my-personal-LLM.git
cd my-personal-LLM
```

### Step 3 — Configure environment

```bash
# Copy the template
cp .env.example .env
```

Open `.env` in a text editor and configure:
- **Required:** Nothing to change for basic usage (defaults work out of the box)
- **Optional:** Add a [Tavily API key](https://tavily.com) for premium web search
- **Optional:** Add an [OpenWeatherMap API key](https://openweathermap.org/api) for weather tool

> For Docker deployment, use `cp .env.docker .env` instead.

### Step 4 — Install dependencies

**Backend (Python):**
```bash
cd backend
pip install -r requirements.txt
cd ..
```

**Frontend (Node.js):**
```bash
cd frontend
npm install
cd ..
```

### Step 5 — Download and create Ollama models

Make sure Ollama is running (`ollama serve` or the Ollama desktop app).

**Windows — automatic setup (downloads all 3 models):**
```bash
setup-models.bat
```

**Manual / Linux / macOS:**

Only the Fast profile is required to get started (~9 GB download):
```bash
# Download the base model
ollama pull goekdenizguelmez/JOSIEFIED-Qwen3:8b-q8_0

# Create the custom profile with optimized parameters
ollama create gustave-fast -f modelfiles/Modelfile-fast
```

Optional larger models (need more RAM):
```bash
# LLaMA 3.3 70B — ~43 GB download, needs ~43 GB RAM
ollama pull huihui_ai/llama3.3-abliterated:70b-instruct-q4_K_M
ollama create gustave-llama -f modelfiles/Modelfile-llama

# Dolphin Mixtral 8x22B — ~80 GB download, needs ~80 GB RAM
ollama pull dolphin-mixtral:8x22b
ollama create gustave-mixtral -f modelfiles/Modelfile-mixtral
```

Verify your models are installed:
```bash
ollama list
# Should show: gustave-fast (and gustave-llama, gustave-mixtral if installed)
```

### Step 6 — Run

#### Option A: Desktop Launcher (Recommended — Windows)

```bash
pythonw launcher.py
```

This opens a control panel at **http://localhost:9000** that manages all services automatically (Ollama, ChromaDB, backend, frontend). Click "Start All" and you're ready.

#### Option B: Docker Compose

```bash
cp .env.docker .env
docker compose up --build -d
```

Services:
- Frontend: **http://localhost:3000**
- Backend API: **http://localhost:8000**
- API docs: **http://localhost:8000/docs**

Stop with: `docker compose down`

#### Option C: Manual (4 terminals)

```bash
# Terminal 1 — Ollama (skip if already running as a service)
ollama serve

# Terminal 2 — ChromaDB (long-term memory)
chroma run --host localhost --port 8001

# Terminal 3 — Backend API
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 4 — Frontend dev server
cd frontend
npm start
```

Open **http://localhost:3000** in your browser.

### Verify installation

1. Open **http://localhost:3000** (or **http://localhost:9000** for the launcher)
2. The health indicator in the bottom-left should show "Ollama connecté"
3. Type a message and press Enter — you should see a streaming response

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send message (SSE streaming response) |
| `GET` | `/health` | Service health check |
| `GET` | `/conversations` | List all conversations |
| `GET` | `/conversations/{id}` | Get conversation with messages |
| `DELETE` | `/conversations/{id}` | Delete conversation |
| `PATCH` | `/conversations/{id}/title` | Rename conversation |
| `POST` | `/conversations/{id}/save-partial` | Save partial response on cancel |
| `GET` | `/models` | Available Ollama models |
| `GET` | `/models/profiles` | Configured quality profiles |

## Configuration

All settings are in `.env` (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `DEFAULT_MODEL_PROFILE` | `fast` | Default quality profile |
| `TAVILY_API_KEY` | — | Optional: premium web search |
| `OPENWEATHERMAP_API_KEY` | — | Optional: weather tool |
| `DATABASE_URL` | `sqlite:///./data/conversations.db` | Conversation storage |
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8001` | ChromaDB port |

## Tech Stack

- **Frontend**: React 18, Tailwind CSS, Axios, react-markdown, react-syntax-highlighter
- **Backend**: FastAPI, LangChain, LangGraph, SQLAlchemy
- **LLM Runtime**: Ollama (local inference)
- **Vector Store**: ChromaDB (long-term memory)
- **Database**: SQLite (conversations)
- **Tools**: DuckDuckGo search, Tavily, Wikipedia, OpenWeatherMap, calculator, datetime

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
