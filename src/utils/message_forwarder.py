"""
消息转发工具模块
提供长文本消息的合并转发功能，避免群聊刷屏
"""
from typing import List, Dict, Any, Union
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent, MessageEvent
from nonebot.log import logger
import os
import re


_CODE_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


def _is_code_heavy(text: str) -> bool:
    if not text:
        return False
    # treat fenced code blocks as code-heavy
    return bool(_CODE_FENCE.search(text))


def split_text_into_paragraphs(text: str, max_paragraph_length: int = 500) -> List[str]:
    """
    将长文本切分为多个段落
    
    Args:
        text: 待切分的文本
        max_paragraph_length: 单个段落的最大长度
        
    Returns:
        段落列表
    """
    if not text or not text.strip():
        return []
    
    paragraphs = []
    
    # 首先按双换行符分割
    parts = text.split('\n\n')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # 如果段落过长，按单换行符再次分割
        if len(part) > max_paragraph_length:
            sub_parts = part.split('\n')
            for sub_part in sub_parts:
                sub_part = sub_part.strip()
                if not sub_part:
                    continue
                    
                # 如果仍然过长，强制按字符数分割
                if len(sub_part) > max_paragraph_length:
                    for i in range(0, len(sub_part), max_paragraph_length):
                        chunk = sub_part[i:i + max_paragraph_length].strip()
                        if chunk:
                            paragraphs.append(chunk)
                else:
                    paragraphs.append(sub_part)
        else:
            paragraphs.append(part)
    
    return paragraphs


def create_forward_nodes(
    paragraphs: List[str],
    bot_uin: str,
    bot_name: str = "AI 助手"
) -> List[Dict[str, Any]]:
    """
    根据段落列表创建转发节点
    
    Args:
        paragraphs: 段落列表
        bot_uin: Bot 的 QQ 号
        bot_name: Bot 的昵称
        
    Returns:
        转发节点列表
    """
    nodes = []
    
    for paragraph in paragraphs:
        node = {
            "type": "node",
            "data": {
                "name": bot_name,
                "uin": bot_uin,
                "content": paragraph
            }
        }
        nodes.append(node)
    
    return nodes


async def send_message_smart(
    bot: Bot,
    message: str,
    event: MessageEvent,
    threshold: int = 100
) -> None:
    """
    智能发送消息：根据消息长度选择普通发送或合并转发
    同时支持群聊和私聊的合并转发功能
    
    Args:
        bot: Bot 实例
        message: 要发送的消息内容
        event: 消息事件对象
        threshold: 触发合并转发的字符数阈值
    """
    # 计算消息长度（去除首尾空白）
    message = message.strip()
    message_length = len(message)
    
    # 获取 Bot 配置
    bot_uin = str(bot.self_id)
    bot_name = os.getenv("BOT_NICKNAME", "AI 助手")
    # Code-aware behavior: do not use forward messages for code blocks by default
    disable_forward_for_code = os.getenv("DISABLE_FORWARD_FOR_CODE", "true").lower() in ("1","true","yes","on")
    max_normal_len = int(os.getenv("MAX_NORMAL_MESSAGE_LEN", "1800"))
    if disable_forward_for_code and _is_code_heavy(message):
        logger.info(f"Code-heavy message detected (len={message_length}), sending as normal message")
        # If too long for a single QQ message, fall back to chunked normal sends
        if message_length <= max_normal_len:
            if isinstance(event, GroupMessageEvent):
                await bot.send_group_msg(group_id=event.group_id, message=message)
            else:
                await bot.send_private_msg(user_id=event.user_id, message=message)
            return
        # chunked send
        chunks = [message[i:i+max_normal_len] for i in range(0, message_length, max_normal_len)]
        for idx, ch in enumerate(chunks):
            prefix = "" if len(chunks) == 1 else f"({idx+1}/{len(chunks)})\n"
            if isinstance(event, GroupMessageEvent):
                await bot.send_group_msg(group_id=event.group_id, message=prefix + ch)
            else:
                await bot.send_private_msg(user_id=event.user_id, message=prefix + ch)
        return

    # 判断是否需要合并转发
    if message_length <= threshold:
        # 普通发送
        logger.info(f"Message length {message_length} <= threshold {threshold}, sending normally")
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_msg(group_id=event.group_id, message=message)
        else:
            await bot.send_private_msg(user_id=event.user_id, message=message)
    else:
        # 消息超过阈值，使用合并转发
        logger.info(f"Message length {message_length} > threshold {threshold}, using forward message")
        
        # 切分文本
        paragraphs = split_text_into_paragraphs(message)
        
        # 如果切分后只有一个段落，直接发送
        if len(paragraphs) <= 1:
            logger.info("Only one paragraph after split, sending normally")
            if isinstance(event, GroupMessageEvent):
                await bot.send_group_msg(group_id=event.group_id, message=message)
            else:
                await bot.send_private_msg(user_id=event.user_id, message=message)
            return
        
        # 创建转发节点
        nodes = create_forward_nodes(paragraphs, bot_uin, bot_name)
        
        # 根据场景选择接口
        if isinstance(event, GroupMessageEvent):
            # 群聊合并转发
            logger.info(f"Sending {len(nodes)} forward nodes to group {event.group_id}")
            try:
                await bot.call_api(
                    "send_group_forward_msg",
                    group_id=event.group_id,
                    messages=nodes
                )
                logger.info("Group forward message sent successfully")
            except Exception as e:
                logger.error(f"Failed to send group forward message: {e}")
                logger.warning("Falling back to normal group message sending (possible anti-spam)")
                # 降级为普通发送（风控兜底）
                await bot.send_group_msg(group_id=event.group_id, message=message)
        else:
            # 私聊合并转发
            logger.info(f"Sending {len(nodes)} forward nodes to user {event.user_id}")
            try:
                await bot.call_api(
                    "send_private_forward_msg",
                    user_id=event.user_id,
                    messages=nodes
                )
                logger.info("Private forward message sent successfully")
            except Exception as e:
                logger.error(f"Failed to send private forward message: {e}")
                logger.warning("Falling back to normal private message sending (possible anti-spam)")
                # 降级为普通发送（风控兜底）
                await bot.send_private_msg(user_id=event.user_id, message=message)


async def send_group_forward_message(
    bot: Bot,
    group_id: int,
    paragraphs: List[str],
    bot_name: str = "AI 助手"
) -> None:
    """
    直接发送群组合并转发消息
    
    Args:
        bot: Bot 实例
        group_id: 群号
        paragraphs: 段落列表
        bot_name: Bot 昵称
    """
    bot_uin = str(bot.self_id)
    nodes = create_forward_nodes(paragraphs, bot_uin, bot_name)
    
    try:
        await bot.call_api(
            "send_group_forward_msg",
            group_id=group_id,
            messages=nodes
        )
        logger.info(f"Forward message with {len(nodes)} nodes sent to group {group_id}")
    except Exception as e:
        logger.error(f"Failed to send forward message to group {group_id}: {e}")
        raise


async def send_private_forward_message(
    bot: Bot,
    user_id: int,
    paragraphs: List[str],
    bot_name: str = "AI 助手"
) -> None:
    """
    直接发送私聊合并转发消息
    
    Args:
        bot: Bot 实例
        user_id: 用户 QQ 号
        paragraphs: 段落列表
        bot_name: Bot 昵称
    """
    bot_uin = str(bot.self_id)
    nodes = create_forward_nodes(paragraphs, bot_uin, bot_name)
    
    try:
        await bot.call_api(
            "send_private_forward_msg",
            user_id=user_id,
            messages=nodes
        )
        logger.info(f"Forward message with {len(nodes)} nodes sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send forward message to user {user_id}: {e}")
        raise
