"""Prompt templates for the AI Debate system."""

from ai_lib_python import Message

from .types import DebatePhase, Position, TranscriptEntry


def build_side_prompt(
    side: Position,
    phase: DebatePhase,
    topic: str,
    transcript: list[TranscriptEntry],
) -> list[Message]:
    """Build the prompt messages for a debate side (Pro or Con)."""
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

    # Format transcript history
    history = ""
    for entry in transcript:
        history += f"[{entry.position.label} - {entry.phase.title} - {entry.model_id}]\n{entry.content}\n\n"

    system_content = (
        f"{stance}\n"
        f"议题：{topic}\n"
        f"当前阶段：{phase_goal}\n"
        f"要求：\n"
        f"- 用 Markdown 输出。\n"
        f"- 必须包含 `## Reasoning`（推理过程，精简列点）和 `## Final Position`（本轮结论）。\n"
        f"- 语言简洁有力，避免重复。\n"
        f"- 字数建议 120-220 中文字。\n"
    )

    messages = [Message.system(system_content)]
    if history:
        messages.append(Message.user(f"已进行的辩论记录：\n{history}"))
    messages.append(Message.user(f"请完成本轮 `{phase.title}` 发言。"))

    return messages


def build_judge_prompt(
    topic: str,
    transcript: list[TranscriptEntry],
) -> list[Message]:
    """Build the prompt messages for the judge."""
    history = ""
    for entry in transcript:
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
