"""
音频格式转换工具
将 QQ 语音格式（amr/silk）转换为 Gemini 支持的格式（mp3/wav）
"""
import os
import subprocess
from pathlib import Path
from nonebot.log import logger
from typing import Optional


class AudioConverter:
    """音频格式转换器"""
    
    def __init__(self):
        # 检查 ffmpeg 是否可用
        self.ffmpeg_available = self._check_ffmpeg()
        
        if not self.ffmpeg_available:
            logger.warning("FFmpeg not found. Audio conversion may not work properly.")
            logger.warning("Install FFmpeg: apt-get install ffmpeg")
    
    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否安装"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def convert_to_mp3(
        self, 
        input_path: Path, 
        output_path: Optional[Path] = None
    ) -> Path:
        """
        转换音频文件为 MP3 格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            
        Returns:
            Path: 转换后的文件路径
            
        Raises:
            Exception: 转换失败
        """
        if not self.ffmpeg_available:
            logger.warning("FFmpeg not available, skipping conversion")
            return input_path
        
        # 生成输出路径
        if output_path is None:
            output_path = input_path.with_suffix('.mp3')
        
        # 如果已经是 mp3，直接返回
        if input_path.suffix.lower() == '.mp3':
            logger.debug(f"File is already MP3: {input_path}")
            return input_path
        
        logger.info(f"Converting {input_path.name} to MP3...")
        
        try:
            # 使用 ffmpeg 转换
            result = subprocess.run([
                'ffmpeg',
                '-i', str(input_path),      # 输入文件
                '-acodec', 'libmp3lame',    # MP3 编码器
                '-ar', '44100',              # 采样率 44.1kHz
                '-ab', '192k',               # 比特率 192kbps
                '-ac', '2',                  # 双声道
                '-y',                        # 覆盖输出文件
                str(output_path)             # 输出文件
            ], 
            capture_output=True,
            timeout=30,
            text=True
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg conversion failed: {result.stderr}")
                raise Exception(f"Audio conversion failed: {result.stderr}")
            
            logger.info(f"Converted to MP3: {output_path}")
            
            # 删除原始文件以节省空间（可选）
            if input_path != output_path and input_path.exists():
                try:
                    input_path.unlink()
                    logger.debug(f"Removed original file: {input_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove original file: {e}")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Audio conversion timeout")
        except Exception as e:
            raise Exception(f"Audio conversion error: {e}")
    
    def convert_to_wav(
        self, 
        input_path: Path, 
        output_path: Optional[Path] = None
    ) -> Path:
        """
        转换音频文件为 WAV 格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            
        Returns:
            Path: 转换后的文件路径
        """
        if not self.ffmpeg_available:
            logger.warning("FFmpeg not available, skipping conversion")
            return input_path
        
        if output_path is None:
            output_path = input_path.with_suffix('.wav')
        
        if input_path.suffix.lower() == '.wav':
            logger.debug(f"File is already WAV: {input_path}")
            return input_path
        
        logger.info(f"Converting {input_path.name} to WAV...")
        
        try:
            result = subprocess.run([
                'ffmpeg',
                '-i', str(input_path),
                '-acodec', 'pcm_s16le',   # PCM 16-bit
                '-ar', '44100',            # 采样率
                '-ac', '2',                # 双声道
                '-y',
                str(output_path)
            ],
            capture_output=True,
            timeout=30,
            text=True
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg conversion failed: {result.stderr}")
                raise Exception(f"Audio conversion failed: {result.stderr}")
            
            logger.info(f"Converted to WAV: {output_path}")
            
            # 删除原始文件
            if input_path != output_path and input_path.exists():
                try:
                    input_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove original file: {e}")
            
            return output_path
            
        except subprocess.TimeoutExpired:
            raise Exception("Audio conversion timeout")
        except Exception as e:
            raise Exception(f"Audio conversion error: {e}")
    
    def get_audio_info(self, file_path: Path) -> dict:
        """
        获取音频文件信息
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            dict: 音频信息（时长、比特率等）
        """
        if not self.ffmpeg_available:
            return {}
        
        try:
            result = subprocess.run([
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ],
            capture_output=True,
            timeout=10,
            text=True
            )
            
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                return info
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {e}")
            return {}


# 全局单例
audio_converter = AudioConverter()
