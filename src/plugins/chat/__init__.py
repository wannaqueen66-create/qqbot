from nonebot import on_message, on_command, get_bot
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, Bot
from nonebot.log import logger
import os
import json
from typing import Union

# Chat Handler
chat = on_message(priority=99, block=False)

# Clear command
clear_cmd = on_command("clear", aliases={"清空记忆"}, priority=5)

# Memory stats command
stats_cmd = on_command("memory", aliases={"记忆统计"}, priority=5)

@stats_cmd.handle()
async def handle_stats(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    from src.utils.conversation_memory import conversation_memory
    from src.utils.database import db
    
    stats = conversation_memory.get_stats()
    msg = (
        f"📊 记忆统计：\n"
        f"👥 缓存用户数：{stats['users_cached']}/{200}\n"
        f"💬 个人消息数：{stats['personal_messages']}\n"
        f"🏘️ 群上下文数：{stats['group_contexts']}\n"
        f"📝 群总结数：{stats['total_summaries']}"
    )
    await stats_cmd.finish(msg)

@clear_cmd.handle()
async def handle_clear(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    from src.utils.conversation_memory import conversation_memory
    
    # Get user identifier
    if isinstance(event, GroupMessageEvent):
        user_id = f"group_{event.group_id}_user_{event.user_id}"
    else:
        user_id = f"user_{event.user_id}"
    
    conversation_memory.clear_user(user_id)

    # Also clear this user's rows from group_context in current group
    if isinstance(event, GroupMessageEvent):
        try:
            db.clear_group_context_for_user(str(event.group_id), str(event.user_id))
        except Exception:
            pass

    await clear_cmd.finish("✅ 记忆已清空，我们可以开始新的对话了！")

@chat.handle()
async def handle_chat(event: Union[GroupMessageEvent, PrivateMessageEvent]):
    try:
        # Check if message is to me
        if not event.is_tome():
            return

        # Import utilities
        from src.utils.conversation_memory import conversation_memory
        from src.utils.openai_client import openai_client
        from src.utils.image_utils import image_file_to_data_url
        from src.utils.message_parser import message_parser
        from src.utils.media_downloader import media_downloader
        
        # Parse message
        try:
            parsed = message_parser.parse_message(event)
        except Exception as e:
            logger.error(f"Message parsing failed: {e}")
            await chat.finish("消息解析失败，请重试。")
        # Media handling (OpenAI-compatible):
        # - Images: use vision endpoint
        # - Audio/Video: not supported yet
        if getattr(parsed, "has_media", False):
            if getattr(parsed, "audios", None) or getattr(parsed, "videos", None):
                await chat.finish("⚠️ 暂不支持语音/视频输入（后续可加本地 Whisper/TTS）。")
                return
            if getattr(parsed, "images", None):
                # Build vision prompt
                max_images = int(os.getenv("MAX_IMAGE_COUNT", "3"))
                max_px = int(os.getenv("IMAGE_MAX_PX", "1024"))
                quality = int(os.getenv("IMAGE_JPEG_QUALITY", "85"))

                image_urls = []
                for img in parsed.images[:max_images]:
                    if not img.url:
                        continue
                    file_path = await media_downloader.download_image(img.url, filename_hint=img.file)
                    image_urls.append(image_file_to_data_url(file_path, max_px=max_px, quality=quality))

                model_for_vision = os.getenv("MODEL_CHAT_LONG", os.getenv("MODEL_CHAT_SHORT", "auto"))
                reply = await openai_client.chat_completions_vision(
                    text_prompt=parsed.text or "请描述这张图片",
                    image_data_urls=image_urls,
                    model=model_for_vision,
                )

                from src.utils.text_formatter import markdown_to_plain_text
                reply = markdown_to_plain_text(reply)

                from src.utils.message_forwarder import send_message_smart
                threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))

                try:
                    bot = get_bot()
                    await send_message_smart(bot=bot, message=reply, event=event, threshold=threshold)
                except Exception:
                    await chat.send(reply)

                await chat.finish()

            return

        # 检查是否为命令消息（避免与命令处理器冲突）
        if parsed.text:
            text_lower = parsed.text.strip().lower()
            # 定义所有命令关键词
            command_keywords = [
                'ping', '在吗',
                'help', '帮助', '菜单',
                'weather', '天气',
                'add_rss', '订阅',
                'rss', '订阅列表', '取消订阅',
                'rss_digest', '今日摘要', 'rss摘要',
                'remind', '提醒',
                'summary', '总结',
                '水群榜', '聊天榜', '发言榜',
                'clear', '清空记忆',
                'memory', '记忆统计',
                'db', '数据库'
            ]
            
            # 检查消息是否以命令前缀开始或包含命令关键词
            # 去除@机器人后的内容进行检查
            text_to_check = text_lower.strip()
            
            # 如果消息以/开头，直接判定为命令
            if text_to_check.startswith('/'):
                logger.info(f"Skipping AI response for command: {text_to_check[:20]}")
                return
            
            # 检查是否完全匹配命令关键词或以命令关键词开头
            for keyword in command_keywords:
                keyword_lower = keyword.lower()
                if text_to_check == keyword_lower or text_to_check.startswith(keyword_lower + ' '):
                    logger.info(f"Skipping AI response for command keyword: {keyword}")
                    return
        
        # 检查是否有内容
        if not parsed.text and not parsed.has_media:
            logger.warning("Empty message received (no text, no media)")
            await chat.finish("?")
        
        # Determine identifiers
        if isinstance(event, GroupMessageEvent):
            user_id = f"group_{event.group_id}_user_{event.user_id}"
            group_id = str(event.group_id)
            # 优先使用群名片
            user_name = event.sender.card or event.sender.nickname or str(event.user_id)
            
            # Add to group context (Tier 2)
            if parsed.text:
                try:
                    conversation_memory.add_group_context(group_id, str(event.user_id), user_name, parsed.text)
                except Exception as e:
                    logger.error(f"Failed to add group context: {e}")
        else:
            user_id = f"user_{event.user_id}"
            group_id = None
            user_name = None
        
        logger.info(f"Building context for {user_id}...")
        
        # Build full context (Tier 1 + Tier 2 + Tier 3)
        try:
            personal_history, system_context = conversation_memory.build_full_context(user_id, group_id)
        except Exception as e:
            logger.error(f"Failed to build context: {e}")
            personal_history = []
            system_context = None
        
        # 处理多模态内容
        uploaded_files = []
        
        if parsed.has_media:
            # 检查用户配额
            from src.utils.quota_manager import quota_manager
            
            allowed, used, remaining = quota_manager.check_quota(user_id, is_multimodal=True)
            
            if not allowed:
                await chat.finish(
                    f"⚠️ 您今日的多模态功能使用次数已达上限 ({used}/{quota_manager.daily_limit})\n"
                    f"明日0点自动重置，或继续使用纯文本对话。"
                )
            
            # 剩余次数较少时提醒
            if remaining <= 5:
                logger.warning(f"User {user_id} has only {remaining} multimodal requests remaining today")
            
            logger.info(f"Processing multimodal message: {len(parsed.images)} images, "
                       f"{len(parsed.audios)} audios, {len(parsed.videos)} videos "
                       f"(quota: {used+1}/{quota_manager.daily_limit})")
            
            try:
                # 下载并上传图片
                from src.utils.image_compressor import image_compressor
                
                for idx, img in enumerate(parsed.images):
                    try:
                        logger.info(f"Processing image {idx+1}/{len(parsed.images)}: url={img.url[:80] if img.url else 'None'}, file={img.file[:50] if img.file else 'None'}")
                        
                        # 检查URL是否有效
                        if not img.url:
                            logger.error(f"Image {idx+1} has no URL")
                            continue
                        
                        #下载图片
                        try:
                            file_path = await media_downloader.download_image(img.url, filename_hint=img.file)
                            logger.info(f"Image {idx+1} downloaded successfully: {file_path}")
                        except Exception as download_err:
                            logger.error(f"Failed to download image {idx+1}: {download_err}")
                            raise
                        
                        # 压缩图片
                        try:
                            compressed_path, was_compressed = image_compressor.compress_image(file_path)
                            if was_compressed:
                                logger.info(f"Image {idx+1} compressed: {compressed_path.name}")
                            else:
                                logger.info(f"Image {idx+1} kept original size: {compressed_path.name}")
                        except Exception as compress_err:
                            logger.error(f"Failed to compress image {idx+1}: {compress_err}")
                            raise
                        
                        # 上传到 Gemini
                        try:
                            mime_type = media_downloader.get_mime_type(compressed_path)
                            logger.info(f"Uploading image {idx+1} to Gemini (mime_type={mime_type})...")
                            uploaded = await openai_client.upload_file(compressed_path, mime_type)
                            uploaded_files.append(uploaded)
                            logger.info(f"Image {idx+1} uploaded successfully: {uploaded.name}")
                        except Exception as upload_err:
                            logger.error(f"Failed to upload image {idx+1} to Gemini: {upload_err}")
                            raise
                            
                    except Exception as e:
                        logger.error(f"Failed to process image {idx+1}: {type(e).__name__}: {str(e)}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                
                # 下载并上传语音
                for audio in parsed.audios:
                    try:
                        if not audio.url:
                            logger.warning(f"Audio has no URL: {audio.file}")
                            continue
                        
                        # 下载音频
                        file_path = await media_downloader.download_audio(audio.url)
                        
                        # 转换格式（如果需要）
                        from src.utils.audio_converter import audio_converter
                        
                        # QQ 语音通常是 amr 或其他格式，转换为 MP3
                        try:
                            converted_path = audio_converter.convert_to_mp3(file_path)
                            logger.info(f"Audio converted: {converted_path.name}")
                        except Exception as conv_err:
                            logger.warning(f"Audio conversion failed, using original: {conv_err}")
                            converted_path = file_path
                        
                        # 上传到 Gemini
                        mime_type = media_downloader.get_mime_type(converted_path)
                        uploaded = await openai_client.upload_file(converted_path, mime_type)
                        uploaded_files.append(uploaded)
                        logger.info(f"Audio uploaded: {uploaded.name}")
                    except Exception as e:
                        logger.error(f"Failed to process audio: {e}")
                
                # 下载并上传视频
                for video in parsed.videos:
                    try:
                        if not video.url:
                            logger.warning(f"Video has no URL: {video.file}")
                            continue
                        
                        file_path = await media_downloader.download_video(video.url)
                        mime_type = media_downloader.get_mime_type(file_path)
                        uploaded = await openai_client.upload_file(file_path, mime_type)
                        uploaded_files.append(uploaded)
                        logger.info(f"Video uploaded: {uploaded.name}")
                    except Exception as e:
                        logger.error(f"Failed to process video: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing media: {e}")
                # 继续处理，降级为纯文本
        
        # Construct System Prompt
        base_instruction = "请注意：单条回复内容尽量控制在100个中文字符以内。"
        
        if system_context:
            final_system_prompt = f"[系统提示]\n{system_context}\n\n{base_instruction}\n现在回答用户的问题，如果用户的问题与上下文相关，请结合上下文回答。"
        else:
            final_system_prompt = f"[系统提示]\n{base_instruction}"
            
        system_msg = [{
            "role": "user", 
            "parts": [{"text": final_system_prompt}]
        }]
        
        # Prepend system message to history
        full_history = system_msg + personal_history
        
        logger.info(f"Chat from {user_id[:30]}... | history: {len(full_history)} | "
                   f"context: {'YES' if system_context else 'NO'} | "
                   f"media: {len(uploaded_files)}")
        
        # 调用 OpenAI-compatible API
        try:
            if uploaded_files:
                # 多模态调用
                # 根据媒体类型生成合适的默认提示
                if not parsed.text:
                    if parsed.audios:
                        text_prompt = "请转录这段语音并回答其中的问题（如果有）"
                    elif parsed.images:
                        text_prompt = "请描述并分析这张图片"
                    elif parsed.videos:
                        text_prompt = "请总结这个视频的内容"
                    else:
                        text_prompt = "请分析这个内容"
                else:
                    text_prompt = parsed.text
                
                # Force Flash or Pro for multimodal, Lite might not support it well or at all
                reply = await openai_client.generate_multimodal_content(
                    model='auto', 
                    text=text_prompt,
                    files=uploaded_files,
                    history=full_history,
                    task_type='chat'
                )
            else:
                # If user sent media but we failed to upload ANY of it
                if parsed.has_media:
                    await chat.finish("⚠️ 抱歉，我无法下载或处理您发送的图片/媒体文件。可能是网络原因或链接失效。")
    
                # 纯文本调用
                reply = await openai_client.generate_content(
                    'auto', 
                    parsed.text, 
                    task_type='chat',
                    history=full_history
                )
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            reply = "抱歉，处理您的消息时出现错误。"
        
        # 记录配额使用（成功调用后）
        if uploaded_files:
            from src.utils.quota_manager import quota_manager
            quota_manager.use_quota(user_id, is_multimodal=True)
        
        # Convert Markdown to plain text for QQ compatibility
        from src.utils.text_formatter import markdown_to_plain_text
        reply = markdown_to_plain_text(reply)
        
        # Save to personal memory (Tier 1)
        try:
            conversation_memory.add_personal_message(user_id, "user", parsed.text or "[多媒体内容]")
            conversation_memory.add_personal_message(user_id, "model", reply)
        except Exception as e:
            logger.error(f"Failed to save conversation memory: {e}")
        
        logger.info(f"Reply: {reply[:80]}...")
        
        # 使用智能发送：自动判断是否需要合并转发
        from src.utils.message_forwarder import send_message_smart
        
        try:
            # 获取 Bot 实例
            bot = get_bot()
            
            # 获取转发阈值配置
            threshold = int(os.getenv("FORWARD_THRESHOLD", "100"))
            
            # 智能发送消息
            await send_message_smart(
                bot=bot,
                message=reply,
                event=event,
                threshold=threshold
            )
        except Exception as e:
            logger.error(f"Failed to send message with smart forwarding: {e}")
            # 降级为普通发送
            await chat.send(reply)
        
        # 结束对话
        await chat.finish()

    except Exception as e:
        # Ignore NoneBot's control flow exceptions
        from nonebot.exception import FinishedException
        if isinstance(e, FinishedException):
            raise e
            
        logger.error(f"Unexpected error in handle_chat: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await chat.finish("系统发生未知错误，请联系管理员。")

