import os
import json
import asyncio
import aiohttp
from nonebot.log import logger
from src.utils.model_router import choose_model
from typing import List, Dict, Optional, Any


def _history_to_openai_messages(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """Convert internal history format ({role, parts:[{text}]}) to OpenAI messages."""
    if not history:
        return []

    messages: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        # our db stores roles: "user" and "model"
        if role == "model":
            role = "assistant"
        if role not in ("system", "user", "assistant"):
            role = "user"

        parts = item.get("parts") or []
        text = ""
        if isinstance(parts, list) and parts:
            p0 = parts[0]
            if isinstance(p0, dict):
                text = p0.get("text") or ""
        if not text:
            # fallback
            text = item.get("content") or ""

        if text:
            messages.append({"role": role, "content": text})

    return messages


class OpenAIClient:
    """OpenAI-compatible client.

    Designed to work with an OpenAI-style endpoint (e.g. Antigravity-Manager /v1).
    """

    def __init__(self):
        self.base_url = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_sec = int(os.getenv("OPENAI_TIMEOUT_SEC", "60"))

        if not self.base_url:
            # allow user to set full /v1 base; if they set host only, append /v1
            host = os.getenv("OPENAI_HOST", "").rstrip("/")
            if host:
                self.base_url = host + "/v1"

        logger.info(f"OpenAIClient init: base_url={self.base_url!r}, model={self.model!r}, timeout={self.timeout_sec}s")

    async def chat_completions(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        if not self.base_url:
            return "[Error] OPENAI_BASE_URL 未配置（例如：https://anti.freeapp.tech/v1）"
        if not self.api_key:
            return "[Error] OPENAI_API_KEY 未配置"

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": 0.7,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_sec)

        # lightweight retry: network errors + 429/5xx
        max_attempts = int(os.getenv("OPENAI_MAX_RETRIES", "2")) + 1
        base_sleep = float(os.getenv("OPENAI_RETRY_BASE_SEC", "0.6"))

        last_status = None
        last_body = ""

        for attempt in range(1, max_attempts + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, headers=headers, json=payload) as resp:
                        last_status = resp.status
                        last_body = await resp.text()

                        if resp.status in (429,) or 500 <= resp.status <= 599:
                            logger.warning(
                                f"OpenAI API transient error: status={resp.status} attempt={attempt}/{max_attempts} body={last_body[:200]}"
                            )
                            if attempt < max_attempts:
                                await asyncio.sleep(base_sleep * (2 ** (attempt - 1)))
                                continue

                        if resp.status >= 400:
                            logger.error(f"OpenAI API error: status={resp.status} body={last_body[:500]}")
                            if resp.status == 401:
                                return "[Error] 后端鉴权失败（401）"
                            if resp.status == 429:
                                return "[Error] 后端限流（429），请稍后再试"
                            return f"[Error] API 调用失败（HTTP {resp.status}）"

                        try:
                            data = json.loads(last_body)
                        except Exception:
                            logger.error(f"OpenAI API invalid JSON: {last_body[:500]}")
                            return "[Error] API 返回格式异常"

                        try:
                            return (data["choices"][0]["message"]["content"] or "").strip()
                        except Exception:
                            logger.error(f"OpenAI API unexpected response: {str(data)[:500]}")
                            return "[Error] API 返回缺少 choices/message"

            except aiohttp.ClientConnectorError as e:
                logger.warning(f"OpenAI API connect error attempt={attempt}/{max_attempts}: {e}")
            except asyncio.TimeoutError as e:
                logger.warning(f"OpenAI API timeout attempt={attempt}/{max_attempts}: {e}")
            except Exception as e:
                logger.warning(f"OpenAI API unknown error attempt={attempt}/{max_attempts}: {type(e).__name__}: {e}")

            if attempt < max_attempts:
                await asyncio.sleep(base_sleep * (2 ** (attempt - 1)))
                continue

        # final fallback
        if last_status is not None:
            return f"[Error] API 调用失败（HTTP {last_status}）"
        return "[Error] 无法连接到后端 API"
    async def generate_content(self, model: str, prompt: str, task_type: str = "chat", auto_select: bool = True, history=None, has_media: bool = False):
        """Gemini-like interface used by existing plugins.

        If model is 'auto' (recommended), it will route to an appropriate backend model
        (e.g. gemini-3-flash / gemini-3-pro-high / claude-sonnet-4.5-thinking / gemini-3-pro-image).
        """
        messages = _history_to_openai_messages(history)

        max_hist = int(os.getenv("OPENAI_MAX_HISTORY_MESSAGES", "20"))
        if len(messages) > max_hist:
            messages = messages[-max_hist:]

        max_in = int(os.getenv("OPENAI_MAX_INPUT_CHARS", "4000"))
        if prompt and len(prompt) > max_in:
            prompt = prompt[-max_in:]
        messages.append({"role": "user", "content": prompt})

        chosen_model = model
        if not chosen_model or chosen_model == "auto":
            choice = choose_model(prompt=prompt, task_type=task_type, has_media=has_media)
            chosen_model = choice.model
            logger.info(f"[model_router] choose model={chosen_model} reason={choice.reason}")

        return await self.chat_completions(messages, model=chosen_model)


openai_client = OpenAIClient()
