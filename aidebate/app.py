"""FastAPI application for AI Debate."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import __version__
from .config import (
    build_client,
    default_models,
    detect_available_providers,
    init_default_clients,
)
from .engine import execute_debate_round, execute_judge_round, execute_round_with_tools
from .storage import fetch_history, init_db, save_message
from .tools import is_search_enabled
from .types import ClientInfo, DebatePhase, Position, TranscriptEntry

logger = logging.getLogger("aidebate")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Debate", version=__version__)

# App state (set during startup)
_state: dict = {}

STATIC_DIR = Path(__file__).parent.parent / "static"


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Initialize database and AI clients on startup."""
    db_path = await init_db()
    pro, con, judge = await init_default_clients()

    _state["db_path"] = db_path
    _state["pro"] = pro
    _state["con"] = con
    _state["judge"] = judge
    _state["start_time"] = time.time()

    logger.info(
        "AI Debate v%s ready: pro=%s, con=%s, judge=%s",
        __version__, pro.model_id, con.model_id, judge.model_id,
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class DebateRequest(BaseModel):
    user_id: str
    session_id: str
    topic: str
    pro_model: Optional[str] = None
    con_model: Optional[str] = None
    judge_model: Optional[str] = None


class HistoryQuery(BaseModel):
    user_id: str
    session_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main page."""
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/api/models")
async def get_models():
    """Return available providers, models, and default selections."""
    providers = detect_available_providers()
    pro_default, con_default, judge_default = default_models()

    pro_info: ClientInfo = _state["pro"]
    con_info: ClientInfo = _state["con"]
    judge_info: ClientInfo = _state["judge"]

    return {
        "providers": [p.to_dict() for p in providers],
        "defaults": {
            "pro": pro_info.model_id,
            "con": con_info.model_id,
            "judge": judge_info.model_id,
        },
        "registered_defaults": {
            "pro": pro_default,
            "con": con_default,
            "judge": judge_default,
        },
        "features": {
            "web_search": is_search_enabled(),
        },
    }


@app.get("/health")
async def health():
    """Health check with model configuration."""
    pro: ClientInfo = _state["pro"]
    con: ClientInfo = _state["con"]
    judge: ClientInfo = _state["judge"]
    uptime = int(time.time() - _state.get("start_time", time.time()))

    return {
        "status": "ok",
        "version": __version__,
        "uptime_secs": uptime,
        "pro": pro.name,
        "pro_model": pro.model_id,
        "con": con.name,
        "con_model": con.model_id,
        "judge": judge.name,
        "judge_model": judge.model_id,
    }


@app.get("/history")
async def get_history(user_id: str, session_id: str):
    """Fetch debate history."""
    rows = await fetch_history(_state["db_path"], user_id, session_id)
    return {"history": rows}


@app.post("/history")
async def post_history(req: HistoryQuery):
    """Fetch debate history (POST)."""
    rows = await fetch_history(_state["db_path"], req.user_id, req.session_id)
    return {"history": rows}


@app.post("/debate/stream")
async def debate_stream(req: DebateRequest):
    """Start a debate and return an SSE stream."""
    if not req.topic.strip() or len(req.topic) > 2000:
        return _sse_error("invalid_topic")

    # Resolve clients (custom or default)
    try:
        pro_client = await _resolve_client(req.pro_model, "pro")
        con_client = await _resolve_client(req.con_model, "con")
        judge_client = await _resolve_client(req.judge_model, "judge")
    except Exception as e:
        return _sse_error(f"Model init failed: {e}")

    async def event_generator():
        yield _sse_json({
            "type": "phase",
            "phase": "init",
            "message": "Debate started",
            "models": {
                "pro": pro_client.model_id,
                "con": con_client.model_id,
                "judge": judge_client.model_id,
            },
        })

        transcript: list[TranscriptEntry] = []
        debate_phases = [
            DebatePhase.OPENING,
            DebatePhase.REBUTTAL,
            DebatePhase.DEFENSE,
            DebatePhase.CLOSING,
        ]

        # Four debate rounds
        for phase in debate_phases:
            for side, client in [
                (Position.PRO, pro_client),
                (Position.CON, con_client),
            ]:
                yield _sse_json({
                    "type": "phase_start",
                    "phase": phase.value,
                    "side": side.value,
                    "title": phase.title,
                    "provider": client.name,
                    "model": client.model_id,
                })

                full_content = ""
                error_occurred = False

                # Choose between tool-enabled and regular execution
                search_enabled = is_search_enabled()
                round_gen = (
                    execute_round_with_tools(client, side, phase, req.topic, transcript)
                    if search_enabled
                    else execute_debate_round(client, side, phase, req.topic, transcript)
                )

                async for chunk in round_gen:
                    if chunk["type"] == "delta":
                        yield _sse_json({
                            "type": "delta",
                            "side": side.value,
                            "phase": phase.value,
                            "model": client.model_id,
                            "content": chunk["content"],
                        })
                        full_content += chunk["content"]
                    elif chunk["type"] == "thinking":
                        yield _sse_json({
                            "type": "thinking",
                            "side": side.value,
                            "phase": phase.value,
                            "model": client.model_id,
                            "content": chunk["content"],
                        })
                    elif chunk["type"] == "usage":
                        yield _sse_json({
                            "type": "usage",
                            "side": side.value,
                            "phase": phase.value,
                            "model": client.model_id,
                            "usage": chunk["usage"],
                        })
                    elif chunk["type"] == "search":
                        yield _sse_json({
                            "type": "search",
                            "side": side.value,
                            "phase": phase.value,
                            "model": client.model_id,
                            "query": chunk["query"],
                            "results": chunk["results"],
                        })
                    elif chunk["type"] == "error":
                        yield _sse_json({"type": "error", "message": chunk["message"]})
                        error_occurred = True
                        break

                if error_occurred:
                    return

                transcript.append(TranscriptEntry(
                    position=side, phase=phase,
                    content=full_content, model_id=client.model_id,
                ))
                await save_message(
                    _state["db_path"], req.user_id, req.session_id,
                    side, phase, client.model_id, full_content,
                )
                yield _sse_json({
                    "type": "phase_done",
                    "phase": phase.value,
                    "side": side.value,
                    "model": client.model_id,
                })

        # Judge round
        yield _sse_json({
            "type": "phase_start",
            "phase": "judgement",
            "side": "judge",
            "title": DebatePhase.JUDGEMENT.title,
            "provider": judge_client.name,
            "model": judge_client.model_id,
        })

        full_content = ""
        async for chunk in execute_judge_round(judge_client, req.topic, transcript):
            if chunk["type"] == "delta":
                yield _sse_json({
                    "type": "delta",
                    "side": "judge",
                    "phase": "judgement",
                    "model": judge_client.model_id,
                    "content": chunk["content"],
                })
                full_content += chunk["content"]
            elif chunk["type"] == "thinking":
                yield _sse_json({
                    "type": "thinking",
                    "side": "judge",
                    "phase": "judgement",
                    "model": judge_client.model_id,
                    "content": chunk["content"],
                })
            elif chunk["type"] == "usage":
                yield _sse_json({
                    "type": "usage",
                    "side": "judge",
                    "phase": "judgement",
                    "model": judge_client.model_id,
                    "usage": chunk["usage"],
                })
            elif chunk["type"] == "error":
                yield _sse_json({"type": "error", "message": chunk["message"]})
                return

        transcript.append(TranscriptEntry(
            position=Position.JUDGE, phase=DebatePhase.JUDGEMENT,
            content=full_content, model_id=judge_client.model_id,
        ))
        await save_message(
            _state["db_path"], req.user_id, req.session_id,
            Position.JUDGE, DebatePhase.JUDGEMENT, judge_client.model_id, full_content,
        )
        yield _sse_json({
            "type": "phase_done",
            "phase": "judgement",
            "side": "judge",
            "model": judge_client.model_id,
        })

        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_client(custom_model: str | None, role: str) -> ClientInfo:
    """Resolve a client for a role. Use custom model if specified, else default."""
    if custom_model and custom_model.strip():
        return await build_client(custom_model.strip())
    defaults = {"pro": _state["pro"], "con": _state["con"], "judge": _state["judge"]}
    return defaults.get(role, _state["pro"])


def _sse_json(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_error(message: str):
    """Return an SSE error response."""
    body = f'data: {{"type":"error","message":"{message}"}}\n\n'
    return StreamingResponse(
        iter([body]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
