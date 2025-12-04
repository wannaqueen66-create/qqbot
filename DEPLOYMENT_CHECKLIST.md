# 快速部署清单 - AI 回复合并转发功能

## 📋 部署前检查

- [ ] 确认 NapCatQQ 正常运行
- [ ] 确认 OneBot 11 协议版本兼容
- [ ] 备份当前代码（如需要）

## 📦 文件清单

### 需要上传到 VPS 的文件：

```
✅ 新增文件:
   d:/AAA所有应用/资源/qqbot/src/utils/message_forwarder.py

✅ 修改文件:
   d:/AAA所有应用/资源/qqbot/src/plugins/chat/__init__.py
   d:/AAA所有应用/资源/qqbot/.env.example (仅供参考)

📖 文档文件（可选）:
   d:/AAA所有应用/资源/qqbot/FORWARDING_GUIDE.md
```

## ⚙️ 配置步骤

### 1. 编辑 `.env` 文件

在 VPS 上编辑您的 `.env` 文件，添加以下配置：

```bash
# AI 回复合并转发配置
FORWARD_THRESHOLD=100
BOT_NICKNAME=AI 助手
```

> 💡 提示: 
> - `FORWARD_THRESHOLD`: 触发合并转发的字符数阈值，建议 100-150
> - `BOT_NICKNAME`: 转发消息中显示的 Bot 名称，可自定义

### 2. 重启服务

```bash
# 进入项目目录
cd /path/to/qqbot

# 使用 Docker Compose 重启
docker-compose down
docker-compose up -d --build

# 或仅重启（不重新构建）
docker-compose restart
```

### 3. 查看日志

```bash
# 实时查看日志
docker-compose logs -f

# 或查看最近的日志
docker-compose logs --tail=100
```

## ✅ 验证功能

### 测试步骤：

1. **短消息测试（群聊）**
   - 在群聊中 @Bot 发送: "你好"
   - 预期: 普通消息回复

2. **长消息测试（群聊）**
   - 在群聊中 @Bot 询问: "详细介绍一下 Python 的特点和应用场景"
   - 预期: 合并转发消息回复
   - 操作: 点开转发消息，查看分段内容

3. **长消息测试（私聊）** ⭐ v2.0 新增
   - 私聊 Bot 发送长问题: "详细介绍一下 Python 的特点和应用场景"
   - 预期: 合并转发消息回复（不再是普通发送）
   - 操作: 点开转发消息，查看分段内容

4. **短消息测试（私聊）**
   - 私聊 Bot: "你好"
   - 预期: 普通消息回复

### 预期日志输出：

```
# 短消息（群聊/私聊）
[INFO] Message length 85 <= threshold 100, sending normally

# 长消息（群聊）
[INFO] Message length 256 > threshold 100, using forward message
[INFO] Sending 3 forward nodes to group 123456789
[INFO] Group forward message sent successfully

# 长消息（私聊）⭐ v2.0 新增
[INFO] Message length 256 > threshold 100, using forward message
[INFO] Sending 3 forward nodes to user 987654321
[INFO] Private forward message sent successfully

# 风控降级（如果发生）
[ERROR] Failed to send group/private forward message: ...
[WARNING] Falling back to normal group/private message sending (possible anti-spam)
```

## 🔧 故障排查

### 问题 1: 转发消息发送失败

**日志：**
```
[ERROR] Failed to send forward message: ...
[WARNING] Falling back to normal message sending
```

**可能原因：**
- NapCatQQ 版本不支持 `send_group_forward_msg`
- Bot 权限不足
- OneBot 11 API 配置问题

**解决方法：**
1. 检查 NapCatQQ 版本，建议升级到最新稳定版
2. 检查 Bot 在群内的权限
3. 查看 NapCatQQ 的详细日志

### 问题 2: 导入错误

**日志：**
```
[ERROR] ModuleNotFoundError: No module named 'src.utils.message_forwarder'
```

**解决方法：**
1. 确认 `message_forwarder.py` 文件已正确上传
2. 检查文件路径是否正确
3. 重启服务

### 问题 3: 配置不生效

**解决方法：**
1. 确认 `.env` 文件已保存
2. 重启 Docker 容器（`docker-compose restart`）
3. 检查环境变量是否正确加载

## 📊 监控指标

建议关注以下指标：

- 转发消息发送成功率
- 降级为普通发送的频率
- 平均分段数量
- 群聊 vs 私聊消息比例

可以通过日志分析工具或自定义脚本统计。

## 🎯 优化建议

### 根据使用情况调整阈值：

| 观察到的问题 | 调整建议 |
|------------|---------|
| 仍然刷屏 | 降低阈值（如改为 50） |
| 转发消息太频繁 | 提高阈值（如改为 150） |
| 段落过长 | 修改 `max_paragraph_length` |

### 自定义分段策略：

如果需要更细粒度的控制，可以修改 `src/utils/message_forwarder.py` 中的 `split_text_into_paragraphs()` 函数。

## 📚 参考文档

- [FORWARDING_GUIDE.md](file:///d:/AAA所有应用/资源/qqbot/FORWARDING_GUIDE.md) - 详细使用指南
- [OneBot 11 协议文档](https://github.com/botuniverse/onebot-11)
- [NapCatQQ 文档](https://napneko.github.io/)

## 🎉 部署完成

部署成功后，您的 QQ Bot 将自动：
- ✅ 识别长文本回复
- ✅ 智能切分段落
- ✅ 使用合并转发发送
- ✅ 降级处理确保可靠性

享受更好的群聊体验！🚀

---

**需要帮助**: 如有问题，请检查日志或参考 FORWARDING_GUIDE.md 中的常见问题章节。
