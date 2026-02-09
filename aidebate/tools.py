"""Web search tool for evidence-backed debates.

Uses Tavily API for web search. Enabled when TAVILY_API_KEY is set.
When disabled, debates proceed without tool calling (no behavior change).
"""

import logging
import os
from dataclasses import dataclass

import httpx
from ai_lib_python import ToolDefinition

logger = logging.getLogger("aidebate")


def is_search_enabled() -> bool:
    """Check if the web search tool is available (TAVILY_API_KEY is set)."""
    return bool(os.environ.get("TAVILY_API_KEY"))


def search_tool_definition() -> ToolDefinition:
    """Build the tool definition for web search."""
    return ToolDefinition.from_function(
        name="web_search",
        description=(
            "Search the web for factual evidence, statistics, news, or data "
            "to support your argument. Use specific, factual queries."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query - be specific and factual, "
                        "e.g. 'AI job displacement statistics 2025'"
                    ),
                }
            },
            "required": ["query"],
        },
    )


@dataclass
class SearchResult:
    """Result from a web search tool call."""

    query: str
    results: str


async def execute_web_search(query: str) -> SearchResult:
    """Execute a web search via the Tavily API."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set")

    logger.info("Web search: %s", query)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 3,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    formatted = []

    # Include Tavily's direct answer if available
    answer = data.get("answer", "")
    if answer:
        formatted.append(f"Direct Answer: {answer}\n")

    # Format individual results
    for r in data.get("results", []):
        title = r.get("title", "")
        content = r.get("content", "")[:300]
        url = r.get("url", "")
        formatted.append(f"Source: {title}\n{content}\nURL: {url}\n")

    results_text = "\n".join(formatted) if formatted else "No relevant results found."

    return SearchResult(query=query, results=results_text)
