import os
import json
import re
from dataclasses import dataclass


@dataclass
class ModelChoice:
    model: str
    reason: str


def _get_models_cfg() -> dict:
    """Model configuration.

    Override via OPENAI_MODELS_JSON, e.g.
    {
      "chat_short": "gemini-3-flash",
      "chat_long": "gemini-3-pro-high",
      "summary": "claude-sonnet-4.5-thinking",
      "image": "gemini-3-pro-image",
      "thinking": "claude-sonnet-4.5-thinking"
    }
    """
    raw = os.getenv("OPENAI_MODELS_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {
        "chat_short": os.getenv("MODEL_CHAT_SHORT", "gemini-3-flash"),
        "chat_long": os.getenv("MODEL_CHAT_LONG", "gemini-3-pro-high"),
        "summary": os.getenv("MODEL_SUMMARY", "claude-sonnet-4.5-thinking"),
        "image": os.getenv("MODEL_IMAGE", "gemini-3-pro-image"),
        # optional alias for reasoning-heavy tasks
        "thinking": os.getenv("MODEL_THINKING", os.getenv("MODEL_SUMMARY", "claude-sonnet-4.5-thinking")),
    }


_REASONING_KEYWORDS = re.compile(
    r"(推理|证明|严谨|推导|算法|复杂度|debug|bug|报错|traceback|stack|代码|code|实现|refactor|设计|架构|optimi[sz]e)",
    re.IGNORECASE,
)

_SUMMARY_KEYWORDS = re.compile(r"(总结|summary|tl;dr|要点|梳理|概括)", re.IGNORECASE)


def choose_model(prompt: str, task_type: str = "chat", has_media: bool = False) -> ModelChoice:
    cfg = _get_models_cfg()

    if has_media:
        return ModelChoice(cfg.get("image") or cfg.get("chat_long"), "has_media")

    p = (prompt or "").strip()

    # explicit summary requests
    if task_type == "summary" or _SUMMARY_KEYWORDS.search(p):
        return ModelChoice(cfg.get("summary") or cfg.get("chat_long"), "summary")

    # reasoning-heavy hint
    if _REASONING_KEYWORDS.search(p):
        return ModelChoice(cfg.get("thinking") or cfg.get("chat_long"), "reasoning_keywords")

    n = len(p)
    if n < 150:
        return ModelChoice(cfg.get("chat_short") or cfg.get("chat_long"), f"chat_short len={n}")
    return ModelChoice(cfg.get("chat_long") or cfg.get("chat_short"), f"chat_long len={n}")
