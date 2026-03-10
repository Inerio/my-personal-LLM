# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Gustave Code** — Personal local AI assistant. React 18 frontend + FastAPI backend + LangChain/LangGraph agent + Ollama (local LLMs) + ChromaDB (long-term memory). Fully offline, uncensored. French-language UI and system prompts.

**Owner hardware:** RTX 3080 12GB, Ryzen 9 5950X (16c/32t), 64GB RAM, Windows 11.

## Commands

```bash
# Start everything (recommended on Windows)
pythonw app.py                         # Native PyQt6 launcher window

# Backend (port 8000)
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend dev server (port 3000)
cd frontend && npm start

# Frontend production build
cd frontend && npm run build

# ChromaDB (port 8001)
chroma run --host localhost --port 8001

# Ollama (port 11434)
ollama serve

# E2E tests (from project root)
python test_chat_e2e.py
python test_tools_e2e.py
python test_chroma.py
python test_memory.py
```

## Architecture

```
User (browser:3000) → React SPA → SSE POST /chat → FastAPI (8000)
                                                      ↓
                                              Agent (LangGraph)
                                              ├── ChatOllama (11434)
                                              ├── Tools (web, calc, wiki...)
                                              └── MemoryService → ChromaDB (8001)
                                                                → SQLite (data/conversations.db)

app.py — Native PyQt6 launcher, manages all 4 services via subprocess
```

### SSE Streaming Pipeline

**Backend:** `chat.py` → `agent.chat_stream()` → yields events into `asyncio.Queue` → `StreamingResponse` with 15s keepalive. Events: `conversation_id`, `token`, `thinking`, `tool_start`, `tool_end`, `done`, `error`.

**Frontend:** `client.js:sendMessage()` → `fetch()` with manual SSE parsing (not EventSource) → callbacks dispatched to `useChat.js` hook → React state.

**Background streaming:** User can navigate conversations while a stream is active. `useChat.js` uses refs (`streamMsgsRef`, `streamConvIdRef`) to accumulate tokens independently of React state. State only updates if the user is viewing the streaming conversation.

### Three Model Profiles

| Profile | Model | VRAM+RAM | Tools | Long-term Memory |
|---------|-------|----------|-------|-----------------|
| `fast` | JOSIEFIED Qwen3 8B (q8_0) | ~9 GB (100% VRAM) | Yes | Yes |
| `llama` | LLaMA 3.3 70B (q4_K_M) | ~43 GB | No (phantom calls) | Limited |
| `mixtral` | Dolphin Mixtral 8x22B | ~80 GB | No (400 error) | No |

Per-profile inference params, context limits, timeouts, and keep_alive are all in `backend/app/config.py` (`PROFILE_INFERENCE_PARAMS`, `PROFILE_CONTEXT_LIMITS`, `PROFILE_TIMEOUTS`, `PROFILE_KEEP_ALIVE`).

### Key Backend Services

- **`agent.py`** — LangGraph agent. Builds profile-aware context (history truncation, memory injection), parses `<think>` blocks, streams SSE events, auto-generates conversation titles.
- **`llm_service.py`** — Abstracts Ollama/OpenAI/Anthropic. Returns configured `ChatOllama` with per-profile params (num_ctx, num_predict, num_thread, timeout, keep_alive).
- **`memory_service.py`** — Two-level memory: SQLite (conversation history) + ChromaDB (semantic search across past conversations). `format_context_for_prompt()` injects relevant memories into system prompt.
- **`db.py`** — SQLAlchemy with SQLite WAL mode. Auto-migration on startup (`_auto_migrate()`). Models: `Conversation` and `Message` (with thinking_content, tool_calls JSON, extra_metadata).

### Key Frontend Patterns

- **`useChat.js`** — Core hook managing streaming state. `send()` initiates SSE, `cancelStream()` aborts + saves partial via `POST /conversations/{id}/save-partial`. Background streaming via refs decoupled from React render cycle.
- **`client.js`** — REST via Axios (through React proxy), SSE via direct `fetch()` to backend (avoids proxy buffering). Profile-specific connection timeouts (1min/5min/10min). `diagnoseError()` calls `/health` after failures to determine cause (backend down / Ollama crashed / model timeout).
- **`MessageBubble.jsx`** — ReactMarkdown + remarkGfm + Prism syntax highlighting. `normalizeNewlines()` pre-processes content (some models emit literal `\n` instead of real newlines). Thinking blocks rendered in collapsible panel.

### Launcher

`app.py` is a native PyQt6 desktop application that manages all 4 services as subprocesses. No HTTP server, no browser needed for the launcher. Features: real-time log panel with filters, service status dots, animated window resize, log deduplication, ANSI stripping, noise filtering. "Ouvrir Gustave Code" opens Chrome to localhost:3000.

## Important Conventions

- **Language:** All UI text, error messages, system prompts, and comments are in **French**.
- **Styling:** Tailwind CSS via CDN (no custom config). Theme: "Clair Obscure" — dark background (#0c0b09), gold/amber accents (#c9a84c), warm browns. CSS variables defined in `frontend/public/index.html`.
- **Tools only on Fast profile:** LLaMA produces phantom tool calls, Mixtral returns 400. Tools are disabled for non-fast profiles in `agent.py`.
- **Abliterated models:** All Ollama models are uncensored/abliterated variants. System prompt reinforces this.
- **Ollama env vars** set by launcher: `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_FLASH_ATTENTION=1`.
- **Conda environment:** Python runs from `C:\Users\Julien\.conda\envs\llm\python.exe`.
- **No test framework:** Tests are standalone Python scripts at project root, run directly.
- **Database location:** `data/conversations.db` (gitignored). ChromaDB persistence in `data/chromadb/`.
