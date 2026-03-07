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
  - **Fast** (Qwen 2.5 14B) — Quick responses, ~30-50 tok/s
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
│       └── api/client.js      # Axios + EventSource
├── modelfiles/          # Custom Ollama model profiles
├── data/                # ChromaDB vector store (gitignored)
└── docker-compose.yml   # Full stack containerization
```

## Quick Start

### Prerequisites

1. **Ollama** — [Download](https://ollama.com/download)
2. **Python 3.11+** — [Download](https://python.org/downloads)
3. **Node.js 18+** — [Download](https://nodejs.org)
4. **ChromaDB** — `pip install chromadb` or use Docker

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/gustave-code.git
cd gustave-code

# Copy environment configuration
cp .env.example .env
# Edit .env with your settings (optional: add Tavily API key for premium search)

# Download and create Ollama model profiles
# Windows:
setup-models.bat
# Linux/macOS:
# ollama pull huihui_ai/qwen2.5-abliterate:14b-instruct-q8_0
# ollama create gustave-fast -f modelfiles/Modelfile-fast
# (repeat for llama and mixtral profiles)

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### Running

#### Option 1: Launcher (Recommended)

```bash
# Start the control panel — manages all services automatically
pythonw launcher.py
# Opens http://localhost:9000 in your browser
```

The launcher will start Ollama, ChromaDB, the backend, and the frontend for you.

#### Option 2: Docker Compose

```bash
docker compose up --build -d
# Frontend: http://localhost:3000
```

#### Option 3: Manual

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — ChromaDB
chroma run --host localhost --port 8001

# Terminal 3 — Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 4 — Frontend
cd frontend
npm start
```

Open **http://localhost:3000** in your browser.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send message (SSE streaming response) |
| `GET` | `/health` | Service health check |
| `GET` | `/conversations` | List all conversations |
| `GET` | `/conversations/{id}` | Get conversation with messages |
| `POST` | `/conversations/create` | Create new conversation |
| `DELETE` | `/conversations/{id}` | Delete conversation |
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

- **Frontend**: React 18, Axios, react-markdown, react-syntax-highlighter
- **Backend**: FastAPI, LangChain, LangGraph, SQLAlchemy, SSE-Starlette
- **LLM Runtime**: Ollama (local inference)
- **Vector Store**: ChromaDB (long-term memory)
- **Database**: SQLite (conversations)
- **Tools**: DuckDuckGo search, Wikipedia, calculator, datetime

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.
