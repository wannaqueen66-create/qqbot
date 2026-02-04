import os
import json
import asyncio
import aiohttp
from nonebot.log import logger
from src.utils.model_router import choose_model, _get_models_cfg, ModelChoice
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


    async def chat_completions_vision(self, text_prompt: str, image_data_urls: list[str], model: str) -> str:
        """Vision chat via OpenAI-compatible /v1/chat/completions.

        image_data_urls: list of data:image/...;base64,...
        """
        if not self.base_url:
            return "[Error] OPENAI_BASE_URL 未配置"
        if not self.api_key:
            return "[Error] OPENAI_API_KEY 未配置"

        content = [{"type": "text", "text": text_prompt or "请描述这张图片"}]
        for u in image_data_urls:
            content.append({"type": "image_url", "image_url": {"url": u}})

        messages = [{"role": "user", "content": content}]

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    logger.error(f"OpenAI vision API error: status={resp.status} body={body[:500]}")
                    if resp.status == 401:
                        return "[Error] 后端鉴权失败（401）"
                    if resp.status == 429:
                        return "[Error] 后端限流（429），请稍后再试"
                    return f"[Error] API 调用失败（HTTP {resp.status}）"
                data = json.loads(body)

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            logger.error(f"OpenAI vision API unexpected response: {str(data)[:500]}")
            return "[Error] API 返回缺少 choices/message"

    async def _chat_completions_raw(self, messages: List[Dict[str, Any]], model: str) -> str:
        """Call /chat/completions with explicit model and minimal processing."""
        # Convert content to OpenAI messages format (allow list content for vision; here we use text only)
        msgs = []
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if role in ("system", "user", "assistant") and content is not None:
                msgs.append({"role": role, "content": content})
        return await self.chat_completions(msgs, model=model)

    async def _smart_route(self, prompt: str, history_messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """Two-stage router: use a cheap model to classify task into a small JSON."""
        enable = os.getenv("ENABLE_SMART_ROUTER", "false").lower() in ("1", "true", "yes", "on")
        if not enable:
            return None

        router_model = os.getenv("ROUTER_MODEL", os.getenv("MODEL_CHAT_SHORT", "gemini-3-flash"))
        max_in = int(os.getenv("ROUTER_MAX_INPUT_CHARS", "2500"))
        max_hist = int(os.getenv("ROUTER_MAX_HISTORY_MESSAGES", "6"))

        p = (prompt or "").strip()
        if len(p) > max_in:
            p = p[-max_in:]

        hist = history_messages[-max_hist:] if history_messages else []

        sys = (
            "You are a routing classifier for a chatbot. "
            "Return ONLY a strict JSON object (no markdown). "
            "Schema: {\"task\": one of [\"chat\",\"summary\",\"code\",\"debug\",\"translation\",\"rewrite\"], "
            "\"complexity\": one of [\"low\",\"high\"], "
            "\"need_long_context\": true/false}."
        )

        user = "Conversation (most recent first):\n" + "\n".join([f"{m['role']}: {m['content']}" for m in hist]) + "\n\nUser prompt:\n" + p

        raw = await self._chat_completions_raw(
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            model=router_model,
        )

        try:
            data = json.loads((raw or "").strip())
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

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
            # two-stage smart router (optional)
            routed = await self._smart_route(prompt=prompt, history_messages=messages[:-1])
            if routed and isinstance(routed, dict):
                cfg_choice = None
                task = str(routed.get("task") or "").lower()
                complexity = str(routed.get("complexity") or "").lower()
                need_long = bool(routed.get("need_long_context"))

                # Map classifier output -> model
                if has_media:
                    cfg_choice = choose_model(prompt=prompt, task_type=task_type, has_media=True)
                elif task in ("summary",):
                    cfg_choice = choose_model(prompt=prompt, task_type="summary", has_media=False)
                elif task in ("code", "debug"):
                    # prefer thinking model for code/debug when high complexity
                    if complexity == "high" or need_long:
                        cfg_choice = ModelChoice(_get_models_cfg().get("thinking") or _get_models_cfg().get("chat_long"), "smart_router code/debug high")
                    else:
                        cfg_choice = ModelChoice(_get_models_cfg().get("chat_long"), "smart_router code/debug")
                elif task in ("translation", "rewrite"):
                    cfg_choice = ModelChoice(_get_models_cfg().get("chat_long"), f"smart_router {task}")
                else:
                    # chat
                    cfg_choice = ModelChoice(_get_models_cfg().get("chat_long") if (need_long or len((prompt or ''))>=150) else _get_models_cfg().get("chat_short"), "smart_router chat")

                if cfg_choice and cfg_choice.model:
                    chosen_model = cfg_choice.model
                    logger.info(f"[smart_router] model={chosen_model} routed={routed}")
                else:
                    choice = choose_model(prompt=prompt, task_type=task_type, has_media=has_media)
                    chosen_model = choice.model
                    logger.info(f"[model_router] choose model={chosen_model} reason={choice.reason}")
            else:
                choice = choose_model(prompt=prompt, task_type=task_type, has_media=has_media)
                chosen_model = choice.model
                logger.info(f"[model_router] choose model={chosen_model} reason={choice.reason}")

        return await self.chat_completions(messages, model=chosen_model)


    async def image_generations(self, prompt: str, model: str) -> str:
        """Generate image via OpenAI-compatible /v1/images/generations.

        Returns base64 string (no prefix) suitable for OneBot base64:// sending.
        """
        if not self.base_url:
            raise RuntimeError('OPENAI_BASE_URL empty')

        url = f"{self.base_url}/images/generations"
        size = os.getenv('OPENAI_IMAGE_SIZE', '1024x1024')
        payload = {
            'model': model,
            'prompt': prompt,
            'n': 1,
            'size': size,
            # request base64 if supported
            'response_format': 'b64_json',
        }
        headers = {
            'Authorization': f"Bearer {self.api_key}",
            'Content-Type': 'application/json',
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    logger.error(f"OpenAI image API error: status={resp.status} body={body[:500]}")
                    raise RuntimeError(f"image api failed: HTTP {resp.status}")
                data = json.loads(body)
        try:
            item = (data.get('data') or [])[0]
            if 'b64_json' in item and item['b64_json']:
                return item['b64_json']
            # fallback if url returned
            if 'url' in item and item['url']:
                return item['url']
        except Exception:
            logger.error(f"OpenAI image API unexpected response: {str(data)[:500]}")
        raise RuntimeError('image api missing data')


openai_client = OpenAIClient()
