# Phase 2 部署指南 - 语音处理功能

## 📋 新增文件清单

以下文件需要上传到您的 VPS：

```
✅ 新增文件:
   src/utils/audio_converter.py      - 音频格式转换器

✅ 修改文件:
   src/plugins/chat/__init__.py      - 添加语音处理和转换逻辑
   .env.example                      - 启用语音功能
```

## 🔧 部署步骤

### 1. 安装 FFmpeg（必需）

在 Ubuntu VPS 上安装 FFmpeg：

```bash
# 更新包列表
sudo apt-get update

# 安装 FFmpeg
sudo apt-get install -y ffmpeg

# 验证安装
ffmpeg -version
ffprobe -version
```

**重要**: FFmpeg 是语音转换的核心依赖，必须安装！

### 2. 上传文件到 VPS

```bash
# 上传新增文件
scp src/utils/audio_converter.py user@your-vps:/path/to/qqbot/src/utils/

# 上传修改文件
scp src/plugins/chat/__init__.py user@your-vps:/path/to/qqbot/src/plugins/chat/
```

### 3. 配置环境变量

编辑 `.env` 文件：

```bash
# 启用语音处理（Phase 2）
ENABLE_VOICE_PROCESSING=true
```

### 4. 重启服务

```bash
cd /path/to/qqbot
docker-compose down
docker-compose up -d --build
```

### 5. 查看日志

```bash
docker-compose logs -f | grep -i "audio\|voice"
```

## ✅ 功能验证

### 测试 1: 语音转文字

**操作步骤**:
1. 在群聊中 @Bot
2. 发送一段语音消息（说"今天天气怎么样"）
3. 不发送文字

**预期结果**:
- Bot 识别语音内容并回答
- AI 会转录语音并理解其中的问题

**日志示例**:
```
[INFO] Parsed message: text=0 chars, images=0, audios=1, videos=0
[INFO] Processing multimodal message: 0 images, 1 audios, 0 videos
[INFO] Downloading from https://...
[INFO] Downloaded 45123 bytes to data/temp_media/audios/def456.amr
[INFO] Converting def456.amr to MP3...
[INFO] Audio converted: def456.mp3
[INFO] Uploading file: def456.mp3 (audio/mp3)
[INFO] File uploaded: files/def456
[INFO] Audio uploaded: files/def456
[INFO] Multimodal API call: model=gemini-2.5-pro, files=1
[INFO] Reply: 根据语音内容，您询问今天的天气...
```

### 测试 2: 语音+文字混合

**操作步骤**:
1. @Bot 发送语音 + 文字："翻译一下"
2. 语音内容："Hello, how are you today?"

**预期结果**:
- Bot 转录英文语音并翻译成中文

### 测试 3: 多段语音

**操作步骤**:
1. @Bot 发送 2-3 段语音
2. 询问："总结一下我说了什么"

**预期结果**:
- Bot 理解所有语音内容并总结

### 测试 4: 纯文本对话（回归测试）

**操作步骤**:
1. @Bot 发送纯文字："你好"

**预期结果**:
- 正常文本回复，确保未破坏原功能

## 📊 监控指标

### 关键日志

```bash
# 成功处理
grep "Audio downloaded" logs/
grep "Audio converted" logs/
grep "Audio uploaded" logs/

# 转换失败（但仍继续）
grep "Audio conversion failed, using original" logs/

# FFmpeg 检查
grep "FFmpeg" logs/
```

### 音频缓存管理

```bash
# 查看缓存
ls -lh data/temp_media/audios/

# 查看转换后的 MP3 文件
ls -lh data/temp_media/audios/*.mp3

# 磁盘使用
du -sh data/temp_media/audios/
```

## 🔧 故障排查

### 问题 1: FFmpeg 未安装

**日志**:
```
[WARNING] FFmpeg not found. Audio conversion may not work properly.
[WARNING] Install FFmpeg: apt-get install ffmpeg
```

**解决方法**:
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
docker-compose restart
```

### 问题 2: 音频转换失败

**日志**:
```
[ERROR] FFmpeg conversion failed: ...
[WARNING] Audio conversion failed, using original
```

**可能原因**:
- 音频格式不被 FFmpeg 支持
- 文件损坏

**解决方法**:
- 系统会自动使用原始文件继续处理
- 检查原始音频文件是否完整

### 问题 3: 音频下载失败

**日志**:
```
[ERROR] Failed to process audio: Download failed
```

**可能原因**:
- 语音消息 URL 无效
- 网络问题

**解决方法**:
1. 检查网络连接
2. 尝试手动下载 URL 验证
3. 查看 NapCatQQ 日志

### 问题 4: Gemini API 不支持音频格式

**日志**:
```
[ERROR] File upload failed: Unsupported MIME type
```

**解决方法**:
- 确保 FFmpeg 正常工作
- 检查转换后的文件格式
- 查看 `get_mime_type()` 返回值

## 🎯 支持的音频格式

### 输入格式（自动转换）
- AMR (QQ 语音常用)
- SILK (QQ 语音格式)
- WAV
- OGG
- M4A
- 其他 FFmpeg 支持的格式

### 输出格式（上传到 Gemini）
- **MP3** (默认，推荐)
- WAV (可选)

### Gemini 支持的音频格式
- audio/mp3
- audio/wav
- audio/ogg
- audio/flac
- audio/m4a
- audio/aac

## 📈 性能指标

### 处理时间

| 操作 | 平均时间 | 说明 |
|------|----------|------|
| 语音下载 | 1-2秒 | 取决于语音长度 |
| 格式转换 | 1-3秒 | FFmpeg 处理 |
| 文件上传 | 2-5秒 | 上传到 Gemini |
| API 调用 | 5-15秒 | 语音转录+理解 |
| **总计** | **9-25秒** | 完整处理流程 |

### 音频文件大小

- 短语音（5秒）: ~50KB
- 中等语音（30秒）: ~300KB
- 长语音（60秒）: ~600KB
- 转换后 MP3: 通常减小 20-40%

## 💡 使用技巧

### 语音转文字场景

**用户**: 发送语音  
**功能**: 自动转录并显示文字

### 语音翻译场景

**用户**: 语音（英文） + 文字："翻译"  
**功能**: 转录英文并翻译成中文

### 语音摘要场景

**用户**: 多段语音 + 文字："总结"  
**功能**: 总结所有语音内容

### 语音问答场景

**用户**: 语音问问题  
**功能**: 理解问题并回答

## 🔄 与 Phase 1 的协同

### 图片+语音混合

**用户**: 图片 + 语音："这张图怎么样？"  
**Bot**: 同时分析图片和语音，给出综合回答

### 完整多模态体验

```
用户: 📷 (猫的照片) + 🎤 (语音："这是什么品种？")
Bot: 根据您发送的图片和语音，这是一只橘猫...
```

## 🚀 优化建议

### 1. 压缩设置

如果希望减小文件大小，修改 `audio_converter.py`:

```python
'-ab', '128k',  # 降低比特率（原值 192k）
```

### 2. 采样率优化

对于语音（非音乐），可以降低采样率：

```python
'-ar', '22050',  # 降低采样率（原值 44100）
```

### 3. 单声道处理

语音通常不需要立体声：

```python
'-ac', '1',  # 单声道（原值 2）
```

## 📊 预期效果

### 成功指标

✅ 语音能够正常下载  
✅ 格式能够成功转换为 MP3  
✅ 音频能够上传到 Gemini  
✅ AI 能够转录语音内容  
✅ AI 能够理解语音问题并回答  
✅ 图片功能不受影响（Phase 1 回归）  

### 用户体验提升

- 🎤 发送语音后 AI 能转录和理解
- 📝 语音转文字功能
- 🌍 语音翻译功能
- 💬 语音问答更自然
- 🎨 图片+语音混合交互

## 🔜 下一步

Phase 2 验证通过后，可以继续：

- **Phase 3**: 视频分析功能（可选）

---

**部署人**: _______  
**部署日期**: _______  
**验证状态**: ☐ 通过 ☐ 失败  
**FFmpeg版本**: _______  
**备注**: _________________________
