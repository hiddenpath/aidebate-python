"""Debate engine - executes debate rounds with streaming and optional tool calling."""

import logging
from typing import AsyncGenerator

from .prompts import build_judge_prompt, build_side_prompt, build_side_prompt_with_tools
from .tools import SearchResult, execute_web_search, is_search_enabled, search_tool_definition
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
    Execute one debate round with streaming (no tool calling).

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


async def execute_round_with_tools(
    client_info: ClientInfo,
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
) -> AsyncGenerator[dict, None]:
    """
    Execute one debate round WITH tool calling support.

    Flow:
    1. Non-streaming execute() with web_search tool - model decides whether to search
    2. If tool calls: execute searches, yield search events, then stream with context
    3. If no tool calls: yield the response content directly

    Yields same format as execute_debate_round plus:
      - {"type": "search", "query": str, "results": str}
    """
    messages = build_side_prompt_with_tools(side, phase, topic, transcript)
    tool_defs = [search_tool_definition()]

    try:
        # Phase 1: Non-streaming call with tools
        response = await (
            client_info.client.chat()
            .messages(messages)
            .tools(tool_defs)
            .temperature(0.7)
            .max_tokens(2048)
            .execute()
        )

        if not response.tool_calls:
            # No tool calls - model responded directly
            if response.content:
                yield {"type": "delta", "content": response.content}
            if hasattr(response, "usage") and response.usage:
                yield {"type": "usage", "usage": response.usage}
            return

        # Phase 2: Model wants to search - execute tool calls
        logger.info(
            "Model %s requested %d tool call(s)",
            client_info.model_id, len(response.tool_calls),
        )

        search_results: list[SearchResult] = []
        for tool_call in response.tool_calls:
            fn_name = getattr(tool_call, "function_name", getattr(tool_call, "name", ""))
            if fn_name == "web_search":
                args = tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
                query = args.get("query", "")
                if query:
                    try:
                        result = await execute_web_search(query)
                        search_results.append(result)
                    except Exception as e:
                        logger.warning("Search failed for '%s': %s", query, e)
                        search_results.append(SearchResult(
                            query=query,
                            results=f"Search failed: {e}",
                        ))

        # Yield search events for the UI
        for result in search_results:
            yield {"type": "search", "query": result.query, "results": result.results}

        # Phase 3: Build context with search results and stream the final response
        search_context = "\n\n".join(
            f"### Search: {r.query}\n{r.results}" for r in search_results
        )
        messages_with_context = build_side_prompt_with_tools(
            side, phase, topic, transcript, search_context=search_context,
        )

        async for event in (
            client_info.client.chat()
            .messages(messages_with_context)
            .temperature(0.7)
            .max_tokens(2048)
            .stream()
        ):
            chunk = _map_event(event)
            if chunk:
                yield chunk

    except Exception as e:
        logger.error("Tool-enabled round error for %s: %s", client_info.model_id, e)
        yield {"type": "error", "message": str(e)}


async def execute_judge_round(
    client_info: ClientInfo,
    topic: str,
    transcript: list[TranscriptEntry],
) -> AsyncGenerator[dict, None]:
    """
    Execute judge round with streaming (no tools - judge evaluates objectively).

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
