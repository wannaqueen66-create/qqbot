import os
import json
import time
from datetime import datetime
from nonebot.log import logger
from google import genai

USAGE_FILE = "data/usage.json"  # Store in data directory for persistence

# Model Limits Configuration
# Tier 1 (Free / Key 1)
LIMITS_TIER_1 = {
    "gemini-2.5-pro": {"rpm": 2, "tpm": 125000, "rpd": 50},
    "gemini-2.5-flash": {"rpm": 10, "tpm": 250000, "rpd": 250},
    "gemini-2.5-flash-lite": {"rpm": 15, "tpm": 250, "rpd": 1000}
}

# Tier 2 (Paid / Key 2)
LIMITS_TIER_2 = {
    "gemini-2.5-pro": {"rpm": 150, "tpm": 2000000, "rpd": 10000},
    "gemini-2.5-flash": {"rpm": 1000, "tpm": 1000000, "rpd": 10000},
    "gemini-2.5-flash-lite": {"rpm": 2000, "tpm": 4000000, "rpd": 1000000000}
}

class GeminiClient:
    def __init__(self):
        env_keys = os.getenv("GEMINI_API_KEYS", "[]")
        logger.info(f"DEBUG: Raw GEMINI_API_KEYS env var: '{env_keys}'")
        try:
            self.api_keys = json.loads(env_keys)
        except json.JSONDecodeError:
            # Fallback: try splitting by comma if not valid JSON
            if "," in env_keys:
                self.api_keys = [k.strip() for k in env_keys.split(",") if k.strip()]
            else:
                self.api_keys = [env_keys.strip()] if env_keys.strip() else []

        if not self.api_keys:
            # Fallback to single key legacy var
            single_key = os.getenv("GEMINI_API_KEY")
            if single_key:
                self.api_keys.append(single_key)
        
        # Remove duplicates and empty strings
        self.api_keys = list(set([k for k in self.api_keys if k]))
        
        logger.info(f"DEBUG: Loaded {len(self.api_keys)} Gemini API keys.")
        
        self.usage_data = self._load_usage()
        self._clean_old_usage()

    def _load_usage(self):
        if not os.path.exists(USAGE_FILE):
            return {}
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_usage(self):
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.usage_data, f, indent=4)

    def _clean_old_usage(self):
        # Reset daily counters if day changed
        today = datetime.now().strftime("%Y-%m-%d")
        if self.usage_data.get("date") != today:
            self.usage_data = {"date": today, "keys": {}}
            self._save_usage()

    def _get_usage(self, key, model):
        if key not in self.usage_data["keys"]:
            self.usage_data["keys"][key] = {}
        if model not in self.usage_data["keys"][key]:
            self.usage_data["keys"][key][model] = {
                "rpd": 0,
                "minute_requests": [], # List of timestamps
                "minute_tokens": []    # List of (timestamp, count)
            }
        return self.usage_data["keys"][key][model]

    def _get_limits(self, key):
        # Determine limits based on key index
        try:
            index = self.api_keys.index(key)
        except ValueError:
            index = 0
        
        if index == 0:
            return LIMITS_TIER_1
        else:
            return LIMITS_TIER_2

    def _check_limits(self, key, model):
        limits_config = self._get_limits(key)
        limits = limits_config.get(model)
        
        if not limits:
            logger.info(f"DEBUG: No limits found for model {model}, allowing.")
            return True # No limits defined, allow

        usage = self._get_usage(key, model)
        now = time.time()

        # Check RPD
        if usage["rpd"] >= limits["rpd"]:
            logger.warning(f"Key {key[:4]}... hit RPD limit for {model}")
            return False

        # Clean old minute data
        usage["minute_requests"] = [t for t in usage["minute_requests"] if now - t < 60]
        usage["minute_tokens"] = [(t, c) for t, c in usage["minute_tokens"] if now - t < 60]

        # Check RPM
        if len(usage["minute_requests"]) >= limits["rpm"]:
            logger.warning(f"Key {key[:4]}... hit RPM limit for {model}")
            return False

        # Check TPM
        current_tpm = sum(c for t, c in usage["minute_tokens"])
        if current_tpm >= limits["tpm"]:
            logger.warning(f"Key {key[:4]}... hit TPM limit for {model}")
            return False

        return True

    def _record_usage(self, key, model, tokens=0):
        usage = self._get_usage(key, model)
        now = time.time()
        
        usage["rpd"] += 1
        usage["minute_requests"].append(now)
        usage["minute_tokens"].append((now, tokens))
        
        self._save_usage()

    def select_model(self, prompt, task_type='chat', prefer_tier='flash'):
        """
        Intelligently select the best model based on task type and prompt complexity.
        
        Args:
            prompt: The text prompt
            task_type: 'chat', 'summary', or 'complex'
            prefer_tier: 'lite', 'flash', or 'pro' (default preference)
        
        Returns:
            Model name string
        """
        prompt_length = len(prompt)
        
        # Task-based routing
        if task_type == 'summary':
            # Summaries need reasoning, use Pro for medium+ content
            if prompt_length > 500:  # Aggressive: Pro for 500+ chars
                return 'gemini-2.5-pro'
            else:
                return 'gemini-2.5-flash'
        
        elif task_type == 'complex':
            # Complex reasoning always uses Pro
            return 'gemini-2.5-pro'
        
        else:  # task_type == 'chat'
            # Chat: optimize for quality over cost
            if prompt_length < 30:
                # Very short messages -> Lite ("ok", "hi")
                return 'gemini-2.5-flash-lite'
            elif prompt_length < 150:
                # Short-medium messages -> Flash
                return 'gemini-2.5-flash'
            else:
                # Medium+ messages -> Pro (better understanding)
                return 'gemini-2.5-pro'

    async def generate_content(self, model, prompt, task_type='chat', auto_select=True, history=None):
        """
        Generate content using Gemini API.
        
        Args:
            model: Model name or 'auto' for intelligent selection
            prompt: The text prompt
            task_type: Type of task ('chat', 'summary', 'complex')
            auto_select: If True and model='auto', automatically select best model
            history: Optional list of previous messages for context
        """
        # Auto-select model if requested
        if model == 'auto' or (auto_select and model in ['gemini-2.5-flash', 'gemini-2.5-flash-lite']):
            model = self.select_model(prompt, task_type)
            logger.info(f"Auto-selected model: {model} for task_type={task_type}, prompt_len={len(prompt)}")
        
        # Try keys in order
        for key in self.api_keys:
            if self._check_limits(key, model):
                try:
                    logger.info(f"Attempting API call with key {key[:4]}... (history: {len(history) if history else 0} messages)")
                    return await self._call_api(key, model, prompt, history)
                except Exception as e:
                    logger.error(f"API call failed with key {key[:4]}...: {e}")
                    continue # Try next key
        
        return "[Error] All API keys exhausted or failed."

    async def _call_api(self, key, model, prompt, history=None):
        # Initialize client with API key
        client = genai.Client(api_key=key)
        
        # Build contents with history
        if history:
            # History format: [{"role": "user", "parts": [{"text": "..."}]}, ...]
            contents = history + [{"role": "user", "parts": [{"text": prompt}]}]
        else:
            contents = prompt
        
        # Call the API
        response = client.models.generate_content(
            model=model,
            contents=contents
        )
        
        # Check finish_reason to detect abnormal termination
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            # Handle both enum and integer types
            # Convert to string for comparison (SDK returns enum objects)
            finish_reason_str = str(finish_reason).upper() if finish_reason else None
            finish_reason_name = getattr(finish_reason, 'name', None) if hasattr(finish_reason, 'name') else finish_reason_str
            
            # STOP (or FinishReason.STOP or 1) indicates normal completion
            is_normal_stop = (
                finish_reason_name == 'STOP' or
                finish_reason == 1 or
                finish_reason_str == 'STOP' or
                finish_reason_str == 'FINISHREASON.STOP' or
                finish_reason_str == '1'
            )
            
            if finish_reason and not is_normal_stop:
                # Map finish_reason to human-readable messages
                reason_map = {
                    'MAX_TOKENS': "MAX_TOKENS - 输出超出最大token限制",
                    'SAFETY': "SAFETY - 内容被安全过滤器拦截",
                    'RECITATION': "RECITATION - 内容因重复而被过滤",
                    'OTHER': "OTHER - 其他原因中断",
                    2: "MAX_TOKENS - 输出超出最大token限制",
                    3: "SAFETY - 内容被安全过滤器拦截",
                    4: "RECITATION - 内容因重复而被过滤",
                    5: "OTHER - 其他原因中断"
                }
                reason_text = reason_map.get(finish_reason_name, reason_map.get(finish_reason, f"UNKNOWN({finish_reason})"))
                logger.warning(f"API response finished abnormally: {reason_text}")
                raise ValueError(f"生成未正常完成: {reason_text}")
        
        # Extract token count from response (if available)
        usage_metadata = getattr(response, 'usage_metadata', None)
        total_tokens = 0
        if usage_metadata:
            total_tokens = getattr(usage_metadata, 'total_token_count', len(prompt) // 4)
        else:
            total_tokens = len(prompt) // 4  # Fallback estimate
        
        self._record_usage(key, model, total_tokens)
        
        # Validate response text
        try:
            response_text = response.text
        except Exception as e:
            logger.error(f"Failed to access response.text: {e}")
            raise ValueError(f"API返回空响应或无法访问: {type(e).__name__}")
        
        if not response_text or not response_text.strip():
            raise ValueError("API返回空响应")
        
        # Return text response
        return response_text
    
    async def upload_file(self, file_path, mime_type: str = None):
        """
        上传文件到 Gemini Files API
        
        Args:
            file_path: 本地文件路径 (Path 或 str)
            mime_type: MIME 类型，如果为 None 则自动检测
            
        Returns:
            上传后的文件对象（包含 uri 等信息）
            
        Raises:
            Exception: 上传失败
        """
        from pathlib import Path
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 自动检测 MIME 类型
        if not mime_type:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'
        
        logger.info(f"Uploading file: {file_path.name} ({mime_type})")
        
        # 尝试所有可用的 API key
        for key in self.api_keys:
            try:
                client = genai.Client(api_key=key)
                
                # 使用新版SDK的上传方法
                # 直接传入文件路径，SDK会自动处理
                uploaded_file = client.files.upload(file=str(file_path))
                
                logger.info(f"File uploaded successfully: {uploaded_file.name}, URI: {uploaded_file.uri}, MIME: {uploaded_file.mime_type}")
                return uploaded_file
                
            except Exception as e:
                logger.error(f"File upload failed with key {key[:4]}...: {e}")
                import traceback
                logger.error(f"Upload traceback: {traceback.format_exc()}")
                continue
        
        raise Exception("All API keys failed to upload file")
    
    async def generate_multimodal_content(
        self,
        model: str,
        text: str,
        files: list = None,
        history: list = None,
        task_type: str = 'chat'
    ) -> str:
        """
        生成多模态内容（支持文本+图片+音频+视频）
        
        Args:
            model: 模型名称或 'auto'
            text: 文本提示
            files: 上传的文件对象列表
            history: 对话历史
            task_type: 任务类型
            
        Returns:
            str: 生成的文本响应
        """
        # 自动选择模型
        if model == 'auto':
            model = self.select_model(text, task_type)
            logger.info(f"Auto-selected model: {model}")
        
        # 尝试所有 API key
        for key in self.api_keys:
            if self._check_limits(key, model):
                try:
                    logger.info(
                        f"Multimodal API call: model={model}, files={len(files) if files else 0}, "
                        f"history={len(history) if history else 0}"
                    )
                    return await self._call_multimodal_api(
                        key, model, text, files, history
                    )
                except Exception as e:
                    logger.error(f"Multimodal API call failed with key {key[:4]}...: {e}")
                    continue
        
        return "[Error] All API keys exhausted or failed."
    
    async def _call_multimodal_api(
        self,
        key: str,
        model: str,
        text: str,
        files: list = None,
        history: list = None
    ) -> str:
        """
        调用 Gemini 多模态 API
        
        Args:
            key: API key
            model: 模型名称
            text: 文本提示
            files: 上传的文件对象列表
            history: 对话历史
            
        Returns:
            str: 生成的文本
        """
        client = genai.Client(api_key=key)
        
        # 构建当前消息的 parts
        current_parts = []
        
        # 添加文本
        if text:
            current_parts.append({"text": text})
        
        # 添加文件（图片/音频/视频）
        if files:
            for file in files:
                current_parts.append({
                    "file_data": {
                        "file_uri": file.uri,
                        "mime_type": file.mime_type
                    }
                })
        
        # 构建完整的 contents
        if history:
            # 有历史记录：追加当前消息
            contents = history + [{
                "role": "user",
                "parts": current_parts
            }]
        else:
            # 无历史记录：仅使用当前消息
            contents = [{
                "role": "user",
                "parts": current_parts
            }]
        
        logger.debug(f"Multimodal contents: {len(contents)} messages, current parts: {len(current_parts)}")
        
        # 调用 API
        response = client.models.generate_content(
            model=model,
            contents=contents
        )
        
        # 检查 finish_reason
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            finish_reason_str = str(finish_reason).upper() if finish_reason else None
            finish_reason_name = getattr(finish_reason, 'name', None) if hasattr(finish_reason, 'name') else finish_reason_str
            
            is_normal_stop = (
                finish_reason_name == 'STOP' or
                finish_reason == 1 or
                finish_reason_str == 'STOP' or
                finish_reason_str == 'FINISHREASON.STOP' or
                finish_reason_str == '1'
            )
            
            if finish_reason and not is_normal_stop:
                reason_map = {
                    'MAX_TOKENS': "MAX_TOKENS - 输出超出最大token限制",
                    'SAFETY': "SAFETY - 内容被安全过滤器拦截",
                    'RECITATION': "RECITATION - 内容因重复而被过滤",
                    'OTHER': "OTHER - 其他原因中断",
                    2: "MAX_TOKENS - 输出超出最大token限制",
                    3: "SAFETY - 内容被安全过滤器拦截",
                    4: "RECITATION - 内容因重复而被过滤",
                    5: "OTHER - 其他原因中断"
                }
                reason_text = reason_map.get(finish_reason_name, reason_map.get(finish_reason, f"UNKNOWN({finish_reason})"))
                logger.warning(f"Multimodal API response finished abnormally: {reason_text}")
                raise ValueError(f"生成未正常完成: {reason_text}")
        
        # 提取响应文本
        usage_metadata = getattr(response, 'usage_metadata', None)
        total_tokens = 0
        if usage_metadata:
            total_tokens = getattr(usage_metadata, 'total_token_count', len(text) // 4)
        else:
            total_tokens = len(text) // 4
        
        self._record_usage(key, model, total_tokens)
        
        # 验证响应
        try:
            response_text = response.text
        except Exception as e:
            logger.error(f"Failed to access multimodal response.text: {e}")
            raise ValueError(f"API返回空响应或无法访问: {type(e).__name__}")
        
        if not response_text or not response_text.strip():
            raise ValueError("API返回空响应")
        
        return response_text

gemini_client = GeminiClient()

