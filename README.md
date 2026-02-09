# AI Debate (Python) v0.2.0

**Multi-model AI debate arena built on [ai-lib-python](https://github.com/hiddenpath/ai-lib-python) and [ai-protocol](https://github.com/hiddenpath/ai-protocol).**

[中文文档](README_CN.md)

Python port of [aidebate](https://github.com/hiddenpath/aidebate) (Rust). Three AI models engage in a structured debate: Pro and Con present arguments across four rounds, then a Judge delivers the verdict. Debaters can optionally search the web for evidence to support their arguments.

## Features

- **4-Round Debate Flow**: Opening → Rebuttal → Defense → Closing → Judgement
- **Web Search Tool Calling**: Debaters can search the web for evidence via Tavily API (optional)
- **Dynamic Model Selection**: Choose any available model for each role via the UI
- **Auto Provider Detection**: Automatically detects configured API keys and shows available models
- **Multi-Provider Support**: DeepSeek, Zhipu GLM, Groq, Mistral, OpenAI, Anthropic, MiniMax
- **Automatic Fallback**: Primary model failures trigger automatic switch to backup model
- **Real-time Streaming**: All rounds use true SSE streaming via FastAPI
- **Token Usage Tracking**: Per-round token consumption display
- **Reasoning Display**: Collapsible thinking/reasoning blocks when supported by model
- **Debate History**: SQLite database for persistent debate records
- **Modern UI**: Dark theme, responsive layout, real Markdown rendering

## Architecture

### Backend
- **Framework**: FastAPI (async web framework) + Uvicorn (ASGI server)
- **AI Integration**: [ai-lib-python](https://github.com/hiddenpath/ai-lib-python) v0.5.0
- **Protocol**: [ai-protocol](https://github.com/hiddenpath/ai-protocol)
- **Database**: aiosqlite (async SQLite)
- **Streaming**: Server-Sent Events (SSE) via StreamingResponse
- **Tool Calling**: Function calling with web search via Tavily API

### Frontend
- **Markdown**: [Marked.js](https://marked.js.org/) (CDN)
- **Style**: Modern dark theme with responsive layout (shared with Rust version)
- **Real-time**: SSE client with streaming updates
- **Search Display**: Visual search cards showing queries and sources

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys (at least one provider required)
# Optionally add TAVILY_API_KEY for web search tool calling
```

### 3. Run

```bash
python -m aidebate
# or
python run.py
```

### 4. Open in Browser

Navigate to `http://127.0.0.1:3000`

## API Key Configuration

API keys are loaded from a `.env` file (via `python-dotenv`). At startup, the system scans for all known provider keys and automatically makes the corresponding models available in the UI.

| Environment Variable | Provider | Role | Notes |
|---------------------|----------|------|-------|
| `DEEPSEEK_API_KEY` | DeepSeek | Default Pro model | `sk-your-key` |
| `ZHIPU_API_KEY` | Zhipu / GLM | Default Con model | `your-key` |
| `GROQ_API_KEY` | Groq | Default Judge model | `gsk_your-key`, generous free tier |
| `MISTRAL_API_KEY` | Mistral | Universal fallback | `your-key`, recommended |
| `OPENAI_API_KEY` | OpenAI | Optional | `sk-your-key` |
| `ANTHROPIC_API_KEY` | Anthropic | Optional | `sk-ant-your-key` |
| `MINIMAX_API_KEY` | MiniMax | Optional | `your-key` |
| `TAVILY_API_KEY` | Tavily | Web search (optional) | `tvly-your-key`, get at [tavily.com](https://tavily.com) |

**How it works:**
1. Copy `.env.example` to `.env` and fill in your keys
2. At least **one** AI provider key is required; `MISTRAL_API_KEY` is recommended as a reliable fallback
3. The system auto-detects which keys are present and exposes only those providers in the `/api/models` endpoint and UI dropdown
4. If a primary model fails (e.g., auth error), the system automatically falls back to `mistral/mistral-small-latest`
5. Users can override models for each role via the UI or via environment variables:
   - `PRO_MODEL_ID` — e.g. `deepseek/deepseek-chat`
   - `CON_MODEL_ID` — e.g. `zhipu/glm-4-plus`
   - `JUDGE_MODEL_ID` — e.g. `groq/llama-3.3-70b-versatile`

## Database

The project uses **SQLite** for persisting debate history. No external database server is needed.

- **Default path**: `debate.db` (created in the working directory)
- **Override**: Set `DATABASE_URL` in `.env` (e.g., `DATABASE_URL=sqlite:///path/to/debate.db`)
- **Auto-creation**: The database file and table are created automatically on first run
- **No migrations needed**: Uses `CREATE TABLE IF NOT EXISTS` on startup

**Schema** (`debate_messages` table):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `user_id` | TEXT | User identifier |
| `session_id` | TEXT | Debate session identifier |
| `role` | TEXT | `pro`, `con`, or `judge` |
| `phase` | TEXT | `opening`, `rebuttal`, `defense`, `closing`, or `judgement` |
| `provider` | TEXT | Model ID used (e.g., `deepseek/deepseek-chat`) |
| `content` | TEXT | Debate message content |
| `created_at` | TIMESTAMP | Auto-generated timestamp |

## Environment Configuration

See [.env.example](.env.example) for all available options:

```bash
# Required: At least one AI provider API key
DEEPSEEK_API_KEY=sk-your-key
ZHIPU_API_KEY=your-key
GROQ_API_KEY=gsk_your-key
MISTRAL_API_KEY=your-key        # recommended as fallback

# Optional: Additional providers
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
MINIMAX_API_KEY=your-key

# Optional: Web search for evidence-backed debates
TAVILY_API_KEY=tvly-your-key

# Optional: Override default models
PRO_MODEL_ID=deepseek/deepseek-chat
CON_MODEL_ID=zhipu/glm-4-plus
JUDGE_MODEL_ID=groq/llama-3.3-70b-versatile

# Optional: Database path (default: sqlite:///debate.db)
DATABASE_URL=sqlite:///debate.db

# Optional: Server host and port
HOST=0.0.0.0
PORT=3000
```

## Tool Calling (Web Search)

When `TAVILY_API_KEY` is set, debaters (Pro and Con) can call a `web_search` tool to find evidence:

1. The model receives the debate context and a `web_search` tool definition
2. If the model decides evidence would help, it calls `web_search` with a query
3. The system executes the search via Tavily API and feeds results back
4. The model generates its argument incorporating the search results
5. Search activity is displayed in the UI with query and sources

**Note**: The Judge does NOT use tools - it evaluates objectively based on the debate transcript only.

If `TAVILY_API_KEY` is not set, the system works exactly as before (no tool calling, no behavior change).

## Default Model Configuration

| Role | Default Model | Fallback |
|------|---------------|----------|
| Pro | `deepseek/deepseek-chat` | `mistral/mistral-small-latest` |
| Con | `zhipu/glm-4-plus` | `mistral/mistral-small-latest` |
| Judge | `groq/llama-3.3-70b-versatile` | `mistral/mistral-small-latest` |

Users can override these selections in the UI before starting a debate.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main page |
| GET | `/health` | Health check with model configuration |
| GET | `/api/models` | Available providers, models, and feature flags |
| POST | `/debate/stream` | Start a debate, returns SSE stream |
| GET | `/history` | Fetch debate history |

## SSE Event Types

| Type | Description |
|------|-------------|
| `phase` | Debate initialization with model info |
| `phase_start` | A debate round begins |
| `delta` | Streaming content chunk |
| `thinking` | Model reasoning/thinking content |
| `usage` | Token usage metadata |
| `search` | Web search performed (query + results) |
| `phase_done` | A debate round completed |
| `error` | Error occurred |
| `done` | Debate complete |

## Debate Flow

1. **User enters topic** and optionally selects models for each role
2. **System initializes AI clients** (Pro, Con, Judge) with fallback support
3. **4 debate rounds** (each round: Pro speaks → Con speaks):
   - Opening Statement
   - Rebuttal
   - Defense
   - Closing Statement
   - *(If web search is enabled, models may search for evidence during any round)*
4. **Judge delivers verdict** based on the complete debate transcript

## Project Structure

```
aidebate-python/
├── aidebate/
│   ├── __init__.py        # Package metadata
│   ├── __main__.py        # Entry point (python -m aidebate)
│   ├── app.py             # FastAPI application and routes
│   ├── config.py          # Provider detection and client management
│   ├── engine.py          # Debate engine with streaming + tool calling
│   ├── prompts.py         # Prompt templates for debate roles
│   ├── storage.py         # SQLite persistence
│   ├── tools.py           # Web search tool (Tavily API)
│   └── types.py           # Data types and enums
├── static/
│   └── index.html         # Single-page web UI (shared with Rust version)
├── .env.example           # Environment variable template
├── pyproject.toml         # Project metadata and build config
├── requirements.txt       # Python dependencies
├── run.py                 # Convenience run script
└── README.md
```

## ai-lib-python Features Used

- **Unified Client Interface**: `AiClient("provider/model")`
- **Automatic Fallback**: `AiClientBuilder().with_fallbacks()`
- **Streaming**: `execute_stream()` returns async generator of `StreamingEvent`
- **Tool Calling**: `tools([ToolDefinition])` + `execute()` for function calling
- **Token Usage**: `StreamingEvent` metadata for token tracking
- **Error Classification**: Auth errors trigger automatic fallback
- **Protocol-Driven**: All behavior defined by ai-protocol manifests

## Related Projects

- [aidebate](https://github.com/hiddenpath/aidebate) - Rust version of this project
- [ai-lib-python](https://github.com/hiddenpath/ai-lib-python) - Python Runtime for AI-Protocol
- [ai-lib-rust](https://github.com/hiddenpath/ai-lib-rust) - Rust Runtime for AI-Protocol
- [ai-protocol](https://github.com/hiddenpath/ai-protocol) - Provider-agnostic AI specification

## License

This project is licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE))
- MIT License ([LICENSE-MIT](LICENSE-MIT))

at your option.
