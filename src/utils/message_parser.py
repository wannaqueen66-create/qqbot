"""
OneBot 11 消息解析器
解析消息事件，提取文本和多媒体内容
"""
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from nonebot.adapters.onebot.v11 import MessageEvent, Message, MessageSegment
from nonebot.log import logger


@dataclass
class ImageSegment:
    """图片消息段"""
    url: str
    file: str
    file_id: Optional[str] = None
    subtype: Optional[int] = None


@dataclass
class AudioSegment:
    """语音消息段"""
    file: str
    url: Optional[str] = None
    magic: Optional[int] = None


@dataclass
class VideoSegment:
    """视频消息段"""
    file: str
    url: Optional[str] = None


@dataclass
class ParsedMessage:
    """解析后的消息结构"""
    text: str
    images: List[ImageSegment]
    audios: List[AudioSegment]
    videos: List[VideoSegment]
    has_media: bool
    raw_message: Message


class MessageParser:
    """OneBot 11 消息解析器"""
    
    def parse_message(self, event: MessageEvent) -> ParsedMessage:
        """
        解析消息事件，提取文本和多媒体内容
        
        Args:
            event: OneBot 11 消息事件
            
        Returns:
            ParsedMessage: 解析后的消息结构
        """
        message = event.message
        
        # 提取各类内容
        text = self.extract_text(message)
        images = self.extract_images(message)
        audios = self.extract_audios(message)
        videos = self.extract_videos(message)
        
        has_media = bool(images or audios or videos)
        
        logger.info(
            f"Parsed message: text={len(text)} chars, "
            f"images={len(images)}, audios={len(audios)}, videos={len(videos)}"
        )
        
        return ParsedMessage(
            text=text,
            images=images,
            audios=audios,
            videos=videos,
            has_media=has_media,
            raw_message=message
        )
    
    def extract_text(self, message: Message) -> str:
        """
        提取消息中的所有文本（包括QQ表情）
        
        Args:
            message: OneBot 11 消息对象
            
        Returns:
            str: 拼接后的文本内容
        """
        text_parts = []
        
        for seg in message:
            if seg.type == "text":
                text_parts.append(seg.data.get("text", ""))
            elif seg.type == "at":
                # 保留 @ 提及（可选）
                qq = seg.data.get("qq", "")
                if qq != "all":
                    text_parts.append(f"@{qq}")
            elif seg.type == "face":
                # QQ 系统表情
                from src.utils.qq_face_map import get_face_description
                face_id = seg.data.get("id", 0)
                face_desc = get_face_description(face_id)
                text_parts.append(f"[{face_desc}]")
                logger.debug(f"Extracted face: {face_id} -> {face_desc}")
        
        return " ".join(text_parts).strip()
    
    def extract_images(self, message: Message) -> List[ImageSegment]:
        """
        提取消息中的所有图片
        
        Args:
            message: OneBot 11 消息对象
            
        Returns:
            List[ImageSegment]: 图片列表
        """
        images = []
        
        for seg in message:
            if seg.type == "image":
                data = seg.data
                
                # 优先使用 url，其次 file
                url = data.get("url") or data.get("file")
                file = data.get("file", "")
                file_id = data.get("file_id")
                subtype = data.get("subtype")
                
                if url:
                    images.append(ImageSegment(
                        url=url,
                        file=file,
                        file_id=file_id,
                        subtype=subtype
                    ))
                    logger.debug(f"Extracted image: {url[:50]}...")
        
        return images
    
    def extract_audios(self, message: Message) -> List[AudioSegment]:
        """
        提取消息中的所有语音
        
        Args:
            message: OneBot 11 消息对象
            
        Returns:
            List[AudioSegment]: 语音列表
        """
        audios = []
        
        for seg in message:
            if seg.type == "record":
                data = seg.data
                
                file = data.get("file", "")
                url = data.get("url")
                magic = data.get("magic")
                
                # 如果没有 url，尝试从 file 构造
                if not url and file:
                    # NapCatQQ 通常会提供完整URL或路径
                    url = file if file.startswith("http") else None
                
                if file or url:
                    audios.append(AudioSegment(
                        file=file,
                        url=url,
                        magic=magic
                    ))
                    logger.debug(f"Extracted audio: {file}")
        
        return audios
    
    def extract_videos(self, message: Message) -> List[VideoSegment]:
        """
        提取消息中的所有视频
        
        Args:
            message: OneBot 11 消息对象
            
        Returns:
            List[VideoSegment]: 视频列表
        """
        videos = []
        
        for seg in message:
            if seg.type == "video":
                data = seg.data
                
                file = data.get("file", "")
                url = data.get("url")
                
                # 如果没有 url，尝试从 file 构造
                if not url and file:
                    url = file if file.startswith("http") else None
                
                if file or url:
                    videos.append(VideoSegment(
                        file=file,
                        url=url
                    ))
                    logger.debug(f"Extracted video: {file}")
        
        return videos
    
    def is_multimodal(self, message: Message) -> bool:
        """
        判断消息是否包含多媒体内容
        
        Args:
            message: OneBot 11 消息对象
            
        Returns:
            bool: 是否为多模态消息
        """
        for seg in message:
            if seg.type in ["image", "record", "video"]:
                return True
        return False


# 全局单例
message_parser = MessageParser()
