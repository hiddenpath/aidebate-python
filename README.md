# AI Debate (Python) v0.1.0

**Multi-model AI debate arena built on [ai-lib-python](https://github.com/hiddenpath/ai-lib-python) and [ai-protocol](https://github.com/hiddenpath/ai-protocol).**

Python port of [aidebate](https://github.com/hiddenpath/aidebate) (Rust). Three AI models engage in a structured debate: Pro and Con present arguments across four rounds, then a Judge delivers the verdict.

## Features

- **4-Round Debate Flow**: Opening → Rebuttal → Defense → Closing → Judgement
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

- **Backend**: FastAPI (async web framework) + Uvicorn (ASGI server)
- **AI Integration**: [ai-lib-python](https://github.com/hiddenpath/ai-lib-python) v0.5.0
- **Protocol**: [ai-protocol](https://github.com/hiddenpath/ai-protocol)
- **Database**: aiosqlite (async SQLite)
- **Streaming**: Server-Sent Events (SSE) via StreamingResponse
- **Frontend**: Same as Rust version — Marked.js (CDN), dark theme

## Default Model Configuration

| Role | Default Model | Fallback |
|------|---------------|----------|
| Pro | `deepseek/deepseek-chat` | `mistral/mistral-small-latest` |
| Con | `zhipu/glm-4-plus` | `mistral/mistral-small-latest` |
| Judge | `groq/llama-3.3-70b-versatile` | `mistral/mistral-small-latest` |

Users can override these selections in the UI before starting a debate.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env and add your API keys (at least one provider required)
```

### 3. Run

```bash
python -m aidebate
# or
python run.py
```

### 4. Open in Browser

Navigate to `http://127.0.0.1:3000`

## Environment Configuration

See [.env.example](.env.example) for all available options. Key variables:

```bash
# Required: At least one AI provider API key
DEEPSEEK_API_KEY=sk-your-key
GROQ_API_KEY=gsk_your-key      # generous free tier
MISTRAL_API_KEY=your-key        # recommended as fallback

# Optional: Override default models
PRO_MODEL_ID=deepseek/deepseek-chat
CON_MODEL_ID=zhipu/glm-4-plus
JUDGE_MODEL_ID=groq/llama-3.3-70b-versatile
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main page |
| GET | `/health` | Health check with model configuration |
| GET | `/api/models` | Available providers and models (for UI) |
| POST | `/debate/stream` | Start a debate, returns SSE stream |
| GET | `/history` | Fetch debate history |

## Project Structure

```
aidebate-python/
├── aidebate/
│   ├── __init__.py        # Package metadata
│   ├── __main__.py        # Entry point (python -m aidebate)
│   ├── app.py             # FastAPI application and routes
│   ├── config.py          # Provider detection and client management
│   ├── engine.py          # Debate engine with streaming
│   ├── prompts.py         # Prompt templates for debate roles
│   ├── storage.py         # SQLite persistence
│   └── types.py           # Data types and enums
├── static/
│   └── index.html         # Frontend (shared with Rust version)
├── .env.example
├── pyproject.toml
├── requirements.txt
├── run.py                 # Convenience run script
└── README.md
```

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
