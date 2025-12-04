"""
媒体文件下载器和管理器
下载、缓存和清理多媒体文件
"""
import os
import hashlib
import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta
from nonebot.log import logger
import mimetypes


class MediaDownloader:
    """媒体文件下载和管理"""
    
    def __init__(self):
        # 配置
        self.cache_dir = Path(os.getenv("MEDIA_CACHE_DIR", "data/temp_media"))
        self.cache_expire_hours = int(os.getenv("MEDIA_CACHE_EXPIRE_HOURS", "24"))
        self.max_download_size_mb = int(os.getenv("MEDIA_MAX_DOWNLOAD_SIZE_MB", "50"))
        
        # 创建目录结构
        self.images_dir = self.cache_dir / "images"
        self.audios_dir = self.cache_dir / "audios"
        self.videos_dir = self.cache_dir / "videos"
        
        for dir_path in [self.images_dir, self.audios_dir, self.videos_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MediaDownloader initialized: cache_dir={self.cache_dir}")
    
    def _get_url_hash(self, url: str) -> str:
        """
        生成 URL 的哈希值用于缓存文件名
        
        Args:
            url: 文件 URL
            
        Returns:
            str: MD5 哈希值
        """
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cached_path(self, url: str, media_type: str) -> Optional[Path]:
        """
        获取缓存文件路径（如果存在且未过期）
        
        Args:
            url: 文件 URL
            media_type: 媒体类型 (image/audio/video)
            
        Returns:
            Optional[Path]: 缓存文件路径，如果不存在或已过期则返回 None
        """
        url_hash = self._get_url_hash(url)
        
        # 选择目录
        if media_type == "image":
            base_dir = self.images_dir
        elif media_type == "audio":
            base_dir = self.audios_dir
        elif media_type == "video":
            base_dir = self.videos_dir
        else:
            return None
        
        # 查找匹配的文件（可能有不同扩展名）
        for file_path in base_dir.glob(f"{url_hash}.*"):
            # 检查是否过期
            if self._is_expired(file_path):
                logger.debug(f"Cache expired: {file_path}")
                file_path.unlink()  # 删除过期文件
                return None
            
            logger.debug(f"Cache hit: {file_path}")
            return file_path
        
        return None
    
    def _is_expired(self, file_path: Path) -> bool:
        """
        检查文件是否过期
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否过期
        """
        if not file_path.exists():
            return True
        
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        expire_time = datetime.now() - timedelta(hours=self.cache_expire_hours)
        
        return mtime < expire_time
    
    def _normalize_url(self, url: str) -> str:
        """
        标准化URL，处理跨容器访问问题
        
        Args:
            url: 原始URL
            
        Returns:
            str: 标准化后的URL
        """
        # 如果URL中包含localhost或127.0.0.1，替换为napcat容器名
        # 这是因为在Docker环境中，localhost指向当前容器，无法访问其他容器
        if 'localhost' in url or '127.0.0.1' in url:
            # 替换为napcat容器名
            url = url.replace('localhost', 'napcat')
            url = url.replace('127.0.0.1', 'napcat')
            logger.info(f"Normalized URL for cross-container access: {url}")
        
        return url
    
    async def _download_file(
        self, 
        url: str, 
        save_path: Path,
        timeout: int = 30
    ) -> Path:
        """
        下载文件到指定路径
        
        Args:
            url: 文件 URL
            save_path: 保存路径
            timeout: 超时时间（秒）
            
        Returns:
            Path: 下载后的文件路径
            
        Raises:
            Exception: 下载失败
        """
        # 标准化URL（处理跨容器访问）
        url = self._normalize_url(url)
        
        logger.info(f"Downloading from {url[:50]}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://im.qq.com/",
        }
        
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        response.raise_for_status()
                        
                        # 检查文件大小
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            size_mb = int(content_length) / (1024 * 1024)
                            if size_mb > self.max_download_size_mb:
                                raise ValueError(
                                    f"File too large: {size_mb:.1f}MB > "
                                    f"{self.max_download_size_mb}MB"
                                )
                        
                        # 下载文件
                        content = await response.read()
                        
                        # 保存文件
                        save_path.write_bytes(content)
                        logger.info(f"Downloaded {len(content)} bytes to {save_path}")
                        
                        return save_path
                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Download attempt {attempt+1}/3 failed: {e}")
                if attempt == 2:
                    raise Exception(f"Download failed after 3 attempts: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                raise Exception(f"Download error: {e}")
    
    def _guess_extension(self, url: str, content_type: Optional[str] = None) -> str:
        """
        猜测文件扩展名
        
        Args:
            url: 文件 URL
            content_type: Content-Type 头
            
        Returns:
            str: 文件扩展名（带点）
        """
        # 尝试从 URL 查询参数中提取（QQ的URL格式如：...?file=xxx.jpg&...）
        from urllib.parse import urlparse, parse_qs
        try:
            parsed = urlparse(url)
            # 检查查询参数中的file字段
            query_params = parse_qs(parsed.query)
            if 'file' in query_params:
                filename = query_params['file'][0]
                if '.' in filename:
                    ext = '.' + filename.split('.')[-1].lower()
                    if len(ext) <= 5:  # 合理的扩展名长度
                        logger.debug(f"Extracted extension from URL param: {ext}")
                        return ext
        except Exception as e:
            logger.debug(f"Failed to parse URL params: {e}")
        
        # 尝试从 URL 路径提取
        if "." in url.split("/")[-1]:
            ext = "." + url.split(".")[-1].split("?")[0]
            if len(ext) <= 5:  # 合理的扩展名长度
                return ext
        
        # 尝试从 Content-Type 推断
        if content_type:
            ext = mimetypes.guess_extension(content_type)
            if ext:
                return ext
        
        # 默认扩展名
        return ".bin"
    
    async def download_image(self, url: str, filename_hint: str = None) -> Path:
        """
        下载图片
        
        Args:
            url: 图片 URL
            filename_hint: 可选的文件名提示（用于提取扩展名）
            
        Returns:
            Path: 下载后的文件路径
        """
        # 检查缓存
        cached = self._get_cached_path(url, "image")
        if cached:
            return cached
        
        # 下载
        url_hash = self._get_url_hash(url)
        
        # 优先从filename_hint提取扩展名
        ext = ".bin"
        if filename_hint and "." in filename_hint:
            hint_ext = "." + filename_hint.split(".")[-1].lower()
            if len(hint_ext) <= 5:
                ext = hint_ext
                logger.debug(f"Using extension from filename hint: {ext}")
        
        # 如果filename_hint没有提供有效扩展名，使用URL猜测
        if ext == ".bin":
            ext = self._guess_extension(url)
        
        save_path = self.images_dir / f"{url_hash}{ext}"
        
        return await self._download_file(url, save_path)
    
    async def download_audio(self, url: str) -> Path:
        """
        下载音频
        
        Args:
            url: 音频 URL
            
        Returns:
            Path: 下载后的文件路径
        """
        # 检查缓存
        cached = self._get_cached_path(url, "audio")
        if cached:
            return cached
        
        # 下载
        url_hash = self._get_url_hash(url)
        ext = self._guess_extension(url)
        save_path = self.audios_dir / f"{url_hash}{ext}"
        
        return await self._download_file(url, save_path)
    
    async def download_video(self, url: str) -> Path:
        """
        下载视频
        
        Args:
            url: 视频 URL
            
        Returns:
            Path: 下载后的文件路径
        """
        # 检查缓存
        cached = self._get_cached_path(url, "video")
        if cached:
            return cached
        
        # 下载
        url_hash = self._get_url_hash(url)
        ext = self._guess_extension(url)
        save_path = self.videos_dir / f"{url_hash}{ext}"
        
        return await self._download_file(url, save_path)
    
    def get_mime_type(self, file_path: Path) -> str:
        """
        检测文件的 MIME 类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: MIME 类型
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        if mime_type:
            return mime_type
        
        # 根据扩展名手动判断
        ext = file_path.suffix.lower()
        ext_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.mp3': 'audio/mp3',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/m4a',
            '.amr': 'audio/amr',
            '.mp4': 'video/mp4',
            '.avi': 'video/avi',
            '.mov': 'video/quicktime',
            '.webm': 'video/webm',
        }
        
        return ext_map.get(ext, 'application/octet-stream')
    
    def cleanup_old_files(self):
        """清理过期的缓存文件"""
        logger.info("Cleaning up old cache files...")
        
        total_removed = 0
        for dir_path in [self.images_dir, self.audios_dir, self.videos_dir]:
            for file_path in dir_path.iterdir():
                if file_path.is_file() and self._is_expired(file_path):
                    file_path.unlink()
                    total_removed += 1
        
        logger.info(f"Removed {total_removed} expired files")


# 全局单例
media_downloader = MediaDownloader()
