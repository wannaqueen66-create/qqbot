"""
图片压缩工具
使用 Pillow 压缩图片以减少 token 消耗
"""
import os
from pathlib import Path
from typing import Tuple
from nonebot.log import logger

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    logger.warning("Pillow not installed. Image compression will be disabled.")
    logger.warning("Install: pip install Pillow")
    PIL_AVAILABLE = False


class ImageCompressor:
    """图片压缩器"""
    
    def __init__(self):
        # 从环境变量读取配置
        self.max_size = int(os.getenv("IMAGE_MAX_SIZE", "1024"))
        self.quality = int(os.getenv("IMAGE_QUALITY", "85"))
        self.enabled = os.getenv("ENABLE_IMAGE_COMPRESSION", "true").lower() == "true"
        
        logger.info(
            f"ImageCompressor initialized: max_size={self.max_size}, "
            f"quality={self.quality}, enabled={self.enabled}"
        )
    
    def compress_image(self, file_path: Path) -> Tuple[Path, bool]:
        """
        压缩图片
        
        Args:
            file_path: 图片文件路径
            
        Returns:
            Tuple[Path, bool]: (压缩后的文件路径, 是否进行了压缩)
        """
        if not self.enabled:
            logger.debug("Image compression disabled")
            return file_path, False
        
        if not PIL_AVAILABLE:
            logger.warning("Pillow not available, skipping compression")
            return file_path, False
        
        try:
            # 打开图片
            img = Image.open(file_path)
            original_size = file_path.stat().st_size
            
            # 获取原始尺寸
            width, height = img.size
            original_dimensions = f"{width}x{height}"
            
            # 判断是否需要压缩
            needs_resize = max(width, height) > self.max_size
            
            if needs_resize:
                # 计算新尺寸（保持宽高比）
                if width > height:
                    new_width = self.max_size
                    new_height = int(height * (self.max_size / width))
                else:
                    new_height = self.max_size
                    new_width = int(width * (self.max_size / height))
                
                logger.info(
                    f"Resizing image from {original_dimensions} to "
                    f"{new_width}x{new_height}"
                )
                
                # 调整大小（使用高质量重采样）
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为 RGB（如果是 RGBA 或其他模式）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 生成压缩后的文件名
            compressed_path = file_path.with_stem(f"{file_path.stem}_compressed")
            
            # 保存压缩后的图片
            img.save(
                compressed_path,
                format='JPEG',
                quality=self.quality,
                optimize=True
            )
            
            compressed_size = compressed_path.stat().st_size
            
            # 计算压缩率
            compression_ratio = (1 - compressed_size / original_size) * 100
            
            logger.info(
                f"Image compressed: {original_size} → {compressed_size} bytes "
                f"({compression_ratio:.1f}% reduction)"
            )
            
            # 删除原始文件
            try:
                file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete original file: {e}")
            
            return compressed_path, True
            
        except Exception as e:
            logger.error(f"Image compression failed: {e}")
            return file_path, False
    
    def get_image_info(self, file_path: Path) -> dict:
        """
        获取图片信息
        
        Args:
            file_path: 图片文件路径
            
        Returns:
            dict: 图片信息
        """
        if not PIL_AVAILABLE:
            return {}
        
        try:
            img = Image.open(file_path)
            return {
                "size": img.size,
                "mode": img.mode,
                "format": img.format,
                "file_size": file_path.stat().st_size
            }
        except Exception as e:
            logger.error(f"Failed to get image info: {e}")
            return {}


# 全局单例
image_compressor = ImageCompressor()
