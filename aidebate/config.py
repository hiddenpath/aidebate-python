"""Configuration and provider detection for AI Debate."""

import os
import logging
from pathlib import Path

from ai_lib_python import AiClient

from .types import AvailableModel, AvailableProvider, ClientInfo

logger = logging.getLogger("aidebate")

# ---------------------------------------------------------------------------
# Default model assignments
# ---------------------------------------------------------------------------

PRO_DEFAULT_MODEL = "deepseek/deepseek-chat"
CON_DEFAULT_MODEL = "zhipu/glm-4-plus"
JUDGE_DEFAULT_MODEL = "groq/llama-3.3-70b-versatile"
FALLBACK_MODEL = "mistral/mistral-small-latest"

# ---------------------------------------------------------------------------
# Provider registry for auto-detection
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY = [
    ("deepseek", "DeepSeek", "DEEPSEEK_API_KEY", [
        ("deepseek/deepseek-chat", "DeepSeek Chat"),
        ("deepseek/deepseek-reasoner", "DeepSeek Reasoner"),
    ]),
    ("zhipu", "Zhipu (智谱)", "ZHIPU_API_KEY", [
        ("zhipu/glm-4-plus", "GLM-4 Plus"),
        ("zhipu/glm-4-flash", "GLM-4 Flash"),
    ]),
    ("groq", "Groq", "GROQ_API_KEY", [
        ("groq/llama-3.3-70b-versatile", "Llama 3.3 70B"),
        ("groq/llama-3.1-8b-instant", "Llama 3.1 8B Instant"),
    ]),
    ("mistral", "Mistral", "MISTRAL_API_KEY", [
        ("mistral/mistral-small-latest", "Mistral Small"),
        ("mistral/mistral-large-latest", "Mistral Large"),
    ]),
    ("openai", "OpenAI", "OPENAI_API_KEY", [
        ("openai/gpt-4o", "GPT-4o"),
        ("openai/gpt-4o-mini", "GPT-4o Mini"),
    ]),
    ("anthropic", "Anthropic", "ANTHROPIC_API_KEY", [
        ("anthropic/claude-3-5-sonnet", "Claude 3.5 Sonnet"),
        ("anthropic/claude-3-5-haiku", "Claude 3.5 Haiku"),
    ]),
    ("minimax", "MiniMax", "MINIMAX_API_KEY", [
        ("minimax/abab6.5s-chat", "ABAB 6.5s Chat"),
    ]),
]


def init_protocol_env():
    """Set up AI protocol directory (local or GitHub fallback)."""
    if os.environ.get("AI_PROTOCOL_DIR") or os.environ.get("AI_PROTOCOL_PATH"):
        return

    local_paths = ["ai-protocol", "../ai-protocol", "../../ai-protocol"]
    for path in local_paths:
        if Path(path).joinpath("v1/providers").exists():
            os.environ["AI_PROTOCOL_DIR"] = path
            logger.info("Using local AI-Protocol: %s", path)
            return

    logger.info("Using remote AI-Protocol from GitHub (may be slow)")
    os.environ["AI_PROTOCOL_DIR"] = "https://raw.githubusercontent.com/hiddenpath/ai-protocol/main"


def detect_available_providers() -> list[AvailableProvider]:
    """Detect available providers by checking environment variables."""
    providers = []
    for provider_id, display_name, env_var, models in PROVIDER_REGISTRY:
        has_key = bool(os.environ.get(env_var))
        providers.append(AvailableProvider(
            provider=provider_id,
            display_name=display_name,
            env_var=env_var,
            has_key=has_key,
            models=[AvailableModel(model_id=m[0], display_name=m[1]) for m in models],
        ))
    return providers


def default_models() -> tuple[str, str, str]:
    """Return default model IDs for pro, con, judge."""
    pro = os.environ.get("PRO_MODEL_ID", PRO_DEFAULT_MODEL)
    con = os.environ.get("CON_MODEL_ID", CON_DEFAULT_MODEL)
    judge = os.environ.get("JUDGE_MODEL_ID", JUDGE_DEFAULT_MODEL)
    return pro, con, judge


def _mask_key(key: str) -> str:
    if len(key) > 4:
        return key[:4] + "..."
    return "***"


async def build_client(model_id: str) -> ClientInfo:
    """Build an AI client for the given model_id with fallback support."""
    provider = model_id.split("/")[0] if "/" in model_id else model_id

    client = await (
        AiClient.builder()
        .model(model_id)
        .with_fallbacks([FALLBACK_MODEL])
        .build()
    )

    logger.info("Client ready: %s (%s)", model_id, provider)
    return ClientInfo(name=provider, model_id=model_id, client=client)


async def init_default_clients() -> tuple[ClientInfo, ClientInfo, ClientInfo]:
    """Initialize default clients for the three debate roles."""
    init_protocol_env()

    pro_model, con_model, judge_model = default_models()

    # Log key availability
    for name, env_var in [
        ("DeepSeek", "DEEPSEEK_API_KEY"),
        ("Zhipu", "ZHIPU_API_KEY"),
        ("Groq", "GROQ_API_KEY"),
        ("Mistral", "MISTRAL_API_KEY"),
    ]:
        key = os.environ.get(env_var)
        if key:
            logger.info("Key: %s (%s) SET [%s]", name, env_var, _mask_key(key))
        else:
            logger.info("Key: %s (%s) MISSING", name, env_var)

    pro = await build_client(pro_model)
    con = await build_client(con_model)
    judge = await build_client(judge_model)

    return pro, con, judge
