import os
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelChoice:
    model: str
    reason: str


def _get_models_cfg() -> dict:
    """Model configuration.

    You can override via OPENAI_MODELS_JSON, e.g.
    {
      "chat_short": "gemini-3-flash",
      "chat_long": "gemini-3-pro-high",
      "summary": "claude-sonnet-4.5-thinking",
      "image": "gemini-3-pro-image"
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

    # Defaults (as requested by Lucas). Exact availability depends on your OpenAI-compatible backend.
    return {
        "chat_short": os.getenv("MODEL_CHAT_SHORT", "gemini-3-flash"),
        "chat_long": os.getenv("MODEL_CHAT_LONG", "gemini-3-pro-high"),
        "summary": os.getenv("MODEL_SUMMARY", "claude-sonnet-4.5-thinking"),
        "image": os.getenv("MODEL_IMAGE", "gemini-3-pro-image"),
    }


def choose_model(
    prompt: str,
    task_type: str = "chat",
    has_media: bool = False,
) -> ModelChoice:
    cfg = _get_models_cfg()

    if has_media:
        return ModelChoice(cfg.get("image") or cfg.get("chat_long"), "has_media")

    if task_type == "summary":
        return ModelChoice(cfg.get("summary") or cfg.get("chat_long"), "task_type=summary")

    # chat / default
    n = len(prompt or "")
    # very short / short -> flash, long -> pro
    if n < 150:
        return ModelChoice(cfg.get("chat_short") or cfg.get("chat_long"), f"chat_short len={n}")
    return ModelChoice(cfg.get("chat_long") or cfg.get("chat_short"), f"chat_long len={n}")
