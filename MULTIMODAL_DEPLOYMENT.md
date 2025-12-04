# Phase 1 部署指南 - 图片识别功能

## 📋 新增文件清单

以下文件需要上传到您的 VPS：

```
✅ 新增文件:
   src/utils/message_parser.py       - 消息解析器
   src/utils/media_downloader.py     - 媒体下载器

✅ 修改文件:
   src/utils/gemini_client.py        - 添加多模态支持
   src/plugins/chat/__init__.py      - 添加图片处理逻辑
   .env.example                      - 添加配置示例
```

## 🔧 部署步骤

### 1. 上传文件到 VPS

使用 SCP 或其他工具上传以下文件：

```bash
# 从本地上传到 VPS
scp src/utils/message_parser.py user@your-vps:/path/to/qqbot/src/utils/
scp src/utils/media_downloader.py user@your-vps:/path/to/qqbot/src/utils/
scp src/utils/gemini_client.py user@your-vps:/path/to/qqbot/src/utils/
scp src/plugins/chat/__init__.py user@your-vps:/path/to/qqbot/src/plugins/chat/
```

### 2. 创建临时媒体目录

在 VPS 上执行：

```bash
cd /path/to/qqbot
mkdir -p data/temp_media/{images,audios,videos}
chmod -R 755 data/temp_media
```

### 3. 配置环境变量

编辑 `.env` 文件，添加以下配置：

```bash
# 多模态功能配置
MEDIA_CACHE_DIR=data/temp_media
MEDIA_CACHE_EXPIRE_HOURS=24
MEDIA_MAX_DOWNLOAD_SIZE_MB=50

# 功能开关（Phase 1 仅启用图片）
ENABLE_IMAGE_RECOGNITION=true
ENABLE_VOICE_PROCESSING=false
ENABLE_VIDEO_ANALYSIS=false
```

### 4. 重启服务

```bash
# 使用 Docker Compose
docker-compose down
docker-compose up -d --build

# 或仅重启
docker-compose restart
```

### 5. 查看日志

```bash
# 实时查看日志
docker-compose logs -f

# 查看最近日志
docker-compose logs --tail=100
```

## ✅ 功能验证

### 测试 1: 单张图片识别

1. 在群聊中 @Bot
2. 发送一张图片（如猫的照片）
3. 询问："这是什么？"
4. **预期结果**: AI 识别图片内容并回答

**日志示例：**
```
[INFO] Parsed message: text=4 chars, images=1, audios=0, videos=0
[INFO] Processing multimodal message: 1 images, 0 audios, 0 videos
[INFO] Downloading from https://...
[INFO] Downloaded 245678 bytes to data/temp_media/images/abc123.jpg
[INFO] Uploading file: abc123.jpg (image/jpeg)
[INFO] File uploaded: files/abc123, URI: https://generativelanguage.googleapis.com/...
[INFO] Image uploaded: files/abc123
[INFO] Multimodal API call: model=gemini-2.5-pro, files=1, history=2
[INFO] Reply: 这是一只可爱的橘猫...
```

### 测试 2: 多张图片对比

1. @Bot 并发送 2-3 张图片
2. 询问："有什么区别？"
3. **预期结果**: AI 分析多张图片的差异

### 测试 3: 图片 OCR（识别文字）

1. @Bot 并发送包含文字的图片
2. 询问："图片里写了什么？"
3. **预期结果**: AI 提取并返回图片中的文字

### 测试 4: 纯文本对话（回归测试）

1. @Bot 发送纯文本："你好"
2. **预期结果**: 正常文本回复（确保未破坏原功能）

## 📊 监控指标

### 关键日志

查找以下日志关键词：

```bash
# 成功处理
grep "Processing multimodal message" logs/
grep "Image uploaded" logs/
grep "Multimodal API call" logs/

# 错误处理
grep "Failed to process image" logs/
grep "Error processing media" logs/
```

### 缓存管理

查看缓存目录：

```bash
# 检查缓存文件
ls -lh data/temp_media/images/

# 查看缓存使用情况
du -sh data/temp_media/
```

## 🔧 故障排查

### 问题 1: 图片下载失败

**日志:**
```
[ERROR] Failed to process image https://...: Download failed: ...
```

**可能原因:**
- 网络连接问题
- URL 无效或已过期
- 文件过大超过限制

**解决方法:**
1. 检查 VPS 网络连接
2. 增加 `MEDIA_MAX_DOWNLOAD_SIZE_MB`
3. 检查防火墙设置

### 问题 2: 文件上传失败

**日志:**
```
[ERROR] File upload failed with key xxxx...: ...
```

**可能原因:**
- Gemini API key 配额耗尽
- 文件格式不支持
- 网络问题

**解决方法:**
1. 检查 API key 配额
2. 确认图片格式（支持 JPG/PNG/WebP）
3. 检查日志获取详细错误信息

### 问题 3: 缓存目录权限错误

**日志:**
```
[ERROR] Failed to save file: Permission denied
```

**解决方法:**
```bash
chmod -R 755 data/temp_media
chown -R your-user:your-group data/temp_media
```

### 问题 4: 降级为纯文本

**日志:**
```
[ERROR] Error processing media: ...
[INFO] Chat from ... | media: 0
```

**说明**: 媒体处理失败后自动降级为纯文本模式，用户仍能收到回复（虽然不包含图片理解）

## 🎯 性能优化建议

### 缓存清理

定期清理过期缓存：

```bash
# 创建清理脚本
cat > cleanup_cache.sh << 'EOF'
#!/bin/bash
find /path/to/qqbot/data/temp_media -type f -mtime +1 -delete
echo "Cleaned up old cache files"
EOF

chmod +x cleanup_cache.sh

# 添加到 crontab（每天凌晨 3 点执行）
0 3 * * * /path/to/cleanup_cache.sh
```

### 监控磁盘空间

```bash
# 检查磁盘使用
df -h

# 监控临时目录
watch -n 60 "du -sh data/temp_media"
```

## 📈 预期效果

### 成功指标

✅ 图片能够正常下载（日志中有 `Downloaded ... bytes`）
✅ 图片能够上传到 Gemini（日志中有 `File uploaded`）
✅ AI 能够理解图片内容（回答准确）
✅ 纯文本对话不受影响（回归测试通过）
✅ 缓存机制生效（相同图片不重复下载）

### 用户体验提升

- 🖼️ 发送图片后 AI 能识别内容
- 📝 图片中的文字能被提取（OCR）
- 🎨 能识别物品、场景、人物等
- 💬 图文混合对话更自然

## 🚀 下一步

Phase 1 验证通过后，可以继续：

- **Phase 2**: 语音处理功能
- **Phase 3**: 视频分析功能

---

**部署人**: _______  
**部署日期**: _______  
**验证状态**: ☐ 通过 ☐ 失败  
**备注**: _________________________
