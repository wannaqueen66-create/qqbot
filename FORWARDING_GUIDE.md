# AI 回复合并转发功能 - 使用指南 v2.0

## 功能概述

✨ **新增功能：** AI 长文本回复自动转为合并转发消息，避免群聊和私聊刷屏！

当 AI 回复字数超过设定阈值时，系统会自动将回复内容切分成多个段落，并以"合并转发"的形式发送。用户点开转发消息后，可以看到类似"连续对话"的多条气泡，阅读体验更佳。

## 核心特性

### 🎯 智能触发
- **自动检测**: 根据消息长度自动判断是否需要合并转发
- **可配置阈值**: 默认 100 字，可通过环境变量自定义
- **智能降级**: 如果合并转发失败（风控），自动降级为普通发送

### 📝 智能分段
- **优先双换行**: 首先按 `\n\n` 分割段落
- **次选单换行**: 对过长段落按 `\n` 再次分割
- **强制切分**: 超长无换行文本按字符数强制切分（默认 500 字/段）
- **过滤空段**: 自动过滤空白段落

### 💬 适用场景
- ✅ **群聊**: 完美支持合并转发（使用 `send_group_forward_msg`）
- ✅ **私聊**: 完美支持合并转发（使用 `send_private_forward_msg`）

### 🛡️ 风控兜底
- 如果合并转发因风控被拦截，自动降级为普通文本发送
- 确保消息一定能送达用户
- 日志中会记录详细的失败原因

## 技术细节

### OneBot 11 协议规范

本功能使用两个 API 接口：

#### 群聊转发：`send_group_forward_msg`

```python
await bot.call_api(
    "send_group_forward_msg",
    group_id=群号,
    messages=[
        {
            "type": "node",
            "data": {
                "name": "发送者昵称",
                "uin": "发送者QQ号",
                "content": "消息内容"
            }
        },
        # ... 更多节点
    ]
)
```

#### 私聊转发：`send_private_forward_msg`

```python
await bot.call_api(
    "send_private_forward_msg",
    user_id=用户QQ号,
    messages=[
        {
            "type": "node",
            "data": {
                "name": "发送者昵称",
                "uin": "发送者QQ号",
                "content": "消息内容"
            }
        },
        # ... 更多节点
    ]
)
```

### NapCatQQ 兼容性

✅ **完全支持**: NapCatQQ 完美支持群聊和私聊的合并转发接口

⚠️ **版本要求**: 建议使用最新稳定版本的 NapCatQQ

⚠️ **风控提醒**: 在某些情况下，QQ 的风控系统可能会拦截合并转发消息，此时会自动降级为普通发送

## 配置说明

### 环境变量配置

在您的 `.env` 文件中添加以下配置（可选）：

```bash
# 转发阈值（字符数）
# 当 AI 回复超过此字数时，触发合并转发
# 默认值: 100
FORWARD_THRESHOLD=100

# Bot 昵称
# 在合并转发消息中显示的发送者名称
# 默认值: AI 助手
BOT_NICKNAME=AI 助手
```

### 配置建议

| 使用场景 | 推荐阈值 | 说明 |
|---------|---------|------|
| 严格控制刷屏 | 50-80 | 更频繁使用合并转发 |
| 平衡体验 | 100-150 | 默认推荐配置 |
| 宽松模式 | 200-300 | 较少触发合并转发 |

## 部署步骤

### 1️⃣ 更新代码
将以下文件同步到您的 VPS：
- ✅ `src/utils/message_forwarder.py` (新增)
- ✅ `src/plugins/chat/__init__.py` (修改)
- ✅ `.env.example` (参考)

### 2️⃣ 配置环境变量
编辑您的 `.env` 文件：
```bash
# 添加或修改以下配置
FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手
```

### 3️⃣ 重启服务
```bash
# 使用 Docker Compose
docker-compose down
docker-compose up -d --build
```

### 4️⃣ 验证功能
1. **群聊测试**: 在测试群中 @Bot 询问长问题
2. **私聊测试**: 私聊 Bot 询问长问题
3. 观察是否以合并转发形式发送
4. 点开转发消息查看分段效果

## 常见问题

### Q1: 私聊也支持合并转发吗？
**A:** 是的！v2.0 版本已完整支持私聊合并转发，使用 `send_private_forward_msg` 接口。

### Q2: 如果合并转发失败（风控）会怎样？
**A:** 系统会自动捕获异常并降级为普通发送，确保消息一定能送达。日志中会记录 "(possible anti-spam)" 提示。

### Q3: 可以调整单个段落的最大长度吗？
**A:** 可以。在 `message_forwarder.py` 中，`split_text_into_paragraphs()` 函数的 `max_paragraph_length` 参数默认为 500 字符，可以根据需要修改。

### Q4: 转发消息中的时间戳是真实的吗？
**A:** 伪造转发消息的时间戳由服务器自动生成，通常是发送时的当前时间。

### Q5: 阈值设置为 0 会怎样？
**A:** 所有消息都会触发合并转发逻辑。但如果分段后只有 1 个段落，仍会使用普通发送。

## 日志说明

功能运行时会输出以下日志：

```
# 普通发送
[INFO] Message length 85 <= threshold 100, sending normally

# 群聊合并转发
[INFO] Message length 256 > threshold 100, using forward message
[INFO] Sending 3 forward nodes to group 123456789
[INFO] Group forward message sent successfully

# 私聊合并转发
[INFO] Message length 256 > threshold 100, using forward message
[INFO] Sending 3 forward nodes to user 987654321
[INFO] Private forward message sent successfully

# 分段后只有一个段落
[INFO] Only one paragraph after split, sending normally

# 风控降级（群聊）
[ERROR] Failed to send group forward message: [错误信息]
[WARNING] Falling back to normal group message sending (possible anti-spam)

# 风控降级（私聊）
[ERROR] Failed to send private forward message: [错误信息]
[WARNING] Falling back to normal private message sending (possible anti-spam)
```

## 版本更新记录

### v2.0.0 (2025-11-30)
- ✅ 新增私聊合并转发支持
- ✅ 使用 `send_private_forward_msg` 接口
- ✅ 增强风控降级策略
- ✅ 优化日志输出信息

### v1.0.0 (2025-11-30) 
- ✨ 初始版本
- ✅ 支持群聊合并转发
- ✅ 智能文本分段
- ✅ 基础降级策略

## 技术支持

如有问题，请检查：
1. NapCatQQ 是否正常运行
2. OneBot 11 协议版本是否兼容
3. 日志中的错误信息
4. Bot 是否有发送权限

---

**版本**: v2.0.0  
**更新日期**: 2025-11-30  
**兼容环境**: Linux + NapCatQQ (OneBot 11)
