"""Debate engine - executes debate rounds with streaming."""

import logging
from typing import AsyncGenerator

from .prompts import build_judge_prompt, build_side_prompt
from .types import ClientInfo, DebatePhase, Position, TranscriptEntry

logger = logging.getLogger("aidebate")


async def execute_debate_round(
    client_info: ClientInfo,
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
) -> AsyncGenerator[dict, None]:
    """
    Execute one debate round with streaming.

    Yields dicts with keys:
      - {"type": "delta", "content": str}
      - {"type": "thinking", "content": str}
      - {"type": "usage", "usage": dict}
      - {"type": "error", "message": str}
    """
    messages = build_side_prompt(side, phase, topic, transcript)

    try:
        async for event in (
            client_info.client.chat()
            .messages(messages)
            .temperature(0.7)
            .max_tokens(2048)
            .stream()
        ):
            chunk = _map_event(event)
            if chunk:
                yield chunk

    except Exception as e:
        logger.error("Stream error for %s: %s", client_info.model_id, e)
        yield {"type": "error", "message": str(e)}


async def execute_judge_round(
    client_info: ClientInfo,
    topic: str,
    transcript: list[TranscriptEntry],
) -> AsyncGenerator[dict, None]:
    """
    Execute judge round with streaming.

    Yields same dict format as execute_debate_round.
    """
    messages = build_judge_prompt(topic, transcript)

    try:
        async for event in (
            client_info.client.chat()
            .messages(messages)
            .temperature(0.3)
            .max_tokens(1024)
            .stream()
        ):
            chunk = _map_event(event)
            if chunk:
                yield chunk

    except Exception as e:
        logger.error("Judge stream error for %s: %s", client_info.model_id, e)
        yield {"type": "error", "message": str(e)}


def _map_event(event) -> dict | None:
    """Map an ai-lib-python streaming event to a dict chunk."""
    try:
        # Content delta
        if hasattr(event, "is_content_delta") and event.is_content_delta:
            content = event.as_content_delta.content
            if content:
                return {"type": "delta", "content": content}
            return None

        # Thinking delta (reasoning)
        if hasattr(event, "is_thinking_delta") and event.is_thinking_delta:
            thinking = event.as_thinking_delta.thinking
            if thinking:
                return {"type": "thinking", "content": thinking}
            return None

        # Metadata (token usage)
        if hasattr(event, "is_metadata") and event.is_metadata:
            meta = event.as_metadata
            if hasattr(meta, "usage") and meta.usage:
                return {"type": "usage", "usage": meta.usage}
            return None

        # Stream error
        if hasattr(event, "is_stream_error") and event.is_stream_error:
            error = event.as_stream_error
            msg = getattr(error, "message", str(error))
            return {"type": "error", "message": msg}

    except Exception as e:
        logger.warning("Event mapping error: %s", e)

    return None
