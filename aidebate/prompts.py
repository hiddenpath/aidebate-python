"""Prompt templates for the AI Debate system."""

from ai_lib_python import Message

from .types import DebatePhase, Position, TranscriptEntry
from .config import TRANSCRIPT_MAX_ENTRIES, get_max_tokens_for_role, get_reserved_tokens_for_role


def _estimate_tokens_from_text(text: str) -> int:
    """Rough token estimate: assume ~1 token per 4 characters (heuristic)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _compress_transcript_for_role(transcript: list[TranscriptEntry], role: str, reserved_tokens: int | None = None) -> list[TranscriptEntry]:
    """Trim the transcript so estimated tokens fit within the role's per-turn budget.

    reserved_tokens: tokens reserved for system + reply content. The rest is available for history.
    This function removes oldest entries first and, if needed, trims entry content.
    """
    if not transcript:
        return transcript

    if reserved_tokens is None:
        reserved_tokens = get_reserved_tokens_for_role(role)

    max_tokens = get_max_tokens_for_role(role)
    allowed_history_tokens = max(0, max_tokens - reserved_tokens)

    # Build recent-first and include entries until token budget exceeded
    out: list[TranscriptEntry] = []
    total = 0
    for entry in reversed(transcript):
        est = _estimate_tokens_from_text(entry.content)
        if total + est > allowed_history_tokens and out:
            break
        out.append(entry)
        total += est

    out = list(reversed(out))

    # If still empty (single entry too large), truncate the oldest entry content
    if not out and transcript:
        first = transcript[-1]
        # estimate allowed chars from tokens
        allowed_chars = max(80, allowed_history_tokens * 4)
        truncated = first.content[:allowed_chars] + "\n\n[...已截断]"
        new_entry = TranscriptEntry(position=first.position, phase=first.phase, model_id=first.model_id, content=truncated)
        return [new_entry]

    return out


def build_side_prompt(
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
) -> list[Message]:
    """Build the prompt messages for a debate side (Pro or Con)."""
    return _build_side_prompt_inner(side, phase, topic, transcript, tools_enabled=False)


def build_side_prompt_with_tools(
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
    search_context: str | None = None,
) -> list[Message]:
    """Build the prompt messages with tool calling enabled and optional search context."""
    return _build_side_prompt_inner(
        side, phase, topic, transcript,
        tools_enabled=True, search_context=search_context,
    )


def _build_side_prompt_inner(
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
    tools_enabled: bool = False,
    search_context: str | None = None,
) -> list[Message]:
    stance = {
        Position.PRO: "你是正方，支持该议题。",
        Position.CON: "你是反方，反对该议题。",
    }.get(side, "")

    phase_goal = {
        DebatePhase.OPENING: "开篇陈词：阐述立场与核心论点。",
        DebatePhase.REBUTTAL: "反驳：针对对方论点逐条反驳，并补充论据。",
        DebatePhase.DEFENSE: "防守：回应对方反驳，巩固自身论据。",
        DebatePhase.CLOSING: "总结陈词：总结关键论点，强调结论。",
    }.get(phase, "")

    # Format transcript history (compress by token budget per-role)
    history = ""
    # compress transcript to fit token budget for this side
    recent = _compress_transcript_for_role(transcript, role=side.name.lower()) if transcript else transcript
    max_entries = TRANSCRIPT_MAX_ENTRIES if TRANSCRIPT_MAX_ENTRIES and TRANSCRIPT_MAX_ENTRIES > 0 else len(recent)
    recent = recent[-max_entries:]
    if len(transcript) > len(recent):
        history += f"[...已截断，显示最近 {len(recent)} 条记录]\n\n"
    for entry in recent:
        history += f"[{entry.position.label} - {entry.phase.title} - {entry.model_id}]\n{entry.content}\n\n"

    tool_instruction = ""
    if tools_enabled:
        tool_instruction = (
            "\n- 当需要事实、数据、统计或最新信息来支持论点时，请调用 web_search 工具搜索证据。\n"
            "- 搜索结果要自然融入你的论点，不要提及工具调用过程。\n"
        )

    system_content = (
        f"{stance}\n"
        f"议题：{topic}\n"
        f"当前阶段：{phase_goal}\n"
        f"要求：\n"
        f"- 用 Markdown 输出。\n"
        f"- 必须包含 `## Reasoning`（推理过程，精简列点）和 `## Final Position`（本轮结论）。\n"
        f"- 语言简洁有力，避免重复。\n"
        f"- 字数建议 120-220 中文字。{tool_instruction}\n"
    )

    messages = [Message.system(system_content)]
    if history:
        messages.append(Message.user(f"已进行的辩论记录：\n{history}"))

    # Inject search results as reference context if available
    if search_context:
        messages.append(Message.user(
            f"以下是搜索到的参考资料，请将相关内容自然地融入你的论点：\n\n{search_context}"
        ))

    messages.append(Message.user(f"请完成本轮 `{phase.title}` 发言。"))
    return messages


def build_judge_prompt(
    topic: str,
    transcript: list[TranscriptEntry],
) -> list[Message]:
    """Build the prompt messages for the judge."""
    history = ""
    max_entries = TRANSCRIPT_MAX_ENTRIES if TRANSCRIPT_MAX_ENTRIES and TRANSCRIPT_MAX_ENTRIES > 0 else len(transcript)
    recent = transcript[-max_entries:]
    if len(transcript) > max_entries:
        history += f"[...已截断，显示最近 {max_entries} 条记录]\n\n"
    for entry in recent:
        history += f"[{entry.position.label} - {entry.phase.title} - {entry.model_id}]\n{entry.content}\n\n"

    system_content = (
        f"你是中立裁判，请根据完整辩论记录做出裁决。\n"
        f"议题：{topic}\n"
        f"要求：\n"
        f"- 用 Markdown 输出。\n"
        f"- 必须包含 `## Reasoning`（裁判推理过程，条理清晰）和 `## Verdict`（结论）。\n"
        f"- 在结论中用 `Winner: Pro` 或 `Winner: Con` 指明胜方。\n"
        f"- 简洁客观，避免复读。\n"
    )

    return [
        Message.system(system_content),
        Message.user(f"完整辩论记录：\n{history}"),
    ]
