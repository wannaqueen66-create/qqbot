# 成本优化功能部署指南

## 📋 新增功能

### 1. 图片压缩 🖼️
- **目的**: 减少图片文件大小，降低 token 消耗
- **效果**: 节省 40-60% 图片相关成本
- **方法**: 自动压缩至 1024px，质量 85%

### 2. 用户配额管理 📊
- **目的**: 限制每用户每日多模态调用次数
- **效果**: 控制总成本在预算内
- **方法**: 每用户每日 100 次多模态请求（可配置）

## 🔧 部署步骤

### 1. 安装依赖

在 Ubuntu VPS 上：

```bash
# 更新 requirements.txt
pip install Pillow>=10.0.0

# 或重新安装所有依赖
pip install -r requirements.txt
```

### 2. 上传新增文件

```bash
# 上传新增模块
scp src/utils/image_compressor.py user@vps:/path/to/qqbot/src/utils/
scp src/utils/quota_manager.py user@vps:/path/to/qqbot/src/utils/

# 上传修改文件
scp src/plugins/chat/__init__.py user@vps:/path/to/qqbot/src/plugins/chat/
scp requirements.txt user@vps:/path/to/qqbot/
scp .env.example user@vps:/path/to/qqbot/
```

### 3. 配置环境变量

编辑 `.env` 文件：

```bash
# 图片压缩配置
ENABLE_IMAGE_COMPRESSION=true
IMAGE_MAX_SIZE=1024              # 最大尺寸（像素）
IMAGE_QUALITY=85                 # JPEG 质量 (0-100)

# 用户配额配置
ENABLE_QUOTA_LIMIT=true
DAILY_MULTIMODAL_LIMIT=100       # 每用户每日多模态次数
QUOTA_FILE=data/user_quotas.json
```

### 4. 创建数据目录

```bash
mkdir -p data
touch data/user_quotas.json
chmod 644 data/user_quotas.json
```

### 5. 重启服务

```bash
# Docker 环境
docker-compose down
docker-compose up -d --build

# 或直接重启
docker-compose restart
```

## ✅ 功能验证

### 测试 1: 图片压缩

```bash
# 查看日志
docker-compose logs -f | grep "compress"

# 预期输出
[INFO] ImageCompressor initialized: max_size=1024, quality=85
[INFO] Resizing image from 2048x1536 to 1024x768
[INFO] Image compressed: 245678 → 98234 bytes (60.0% reduction)
[INFO] Image compressed: abc123_compressed.jpg
```

### 测试 2: 用户配额

**场景**: 用户发送图片

```bash
# 日志输出
[INFO] Processing multimodal message: 1 images (quota: 1/100)
[INFO] User user_12345 used multimodal quota: 1/100
```

**场景**: 用户达到限额

```
用户: 🖼️ [图片]
Bot: ⚠️ 您今日的多模态功能使用次数已达上限 (100/100)
     明日0点自动重置，或继续使用纯文本对话。
```

## 📊 监控指标

### 查看图片压缩效果

```bash
# 统计压缩率
grep "Image compressed:" logs/ | grep "reduction" | \
  awk -F'[()]' '{sum+=$(NF-1)} END {print sum/NR"%"}'

# 输出示例: 45.6%（平均压缩率）
```

### 查看配额使用情况

```bash
# 查看配额文件
cat data/user_quotas.json

# 输出示例:
{
  "date": "2025-11-30",
  "users": {
    "user_12345": {
      "total": 150,
      "multimodal": 45
    },
    "group_67890_user_11111": {
      "total": 80,
      "multimodal": 25
    }
  }
}
```

### 统计今日使用

```bash
# 统计今日多模态次数
grep "used multimodal quota" logs/ | wc -l

# 统计不同用户数
jq '.users | length' data/user_quotas.json
```

## 🎯 配置建议

### 场景 1: 省钱优先

```bash
# 激进压缩
IMAGE_MAX_SIZE=800
IMAGE_QUALITY=75

# 严格限额
DAILY_MULTIMODAL_LIMIT=50
```

**预期成本**: 节省 60-70%

### 场景 2: 平衡模式（推荐）

```bash
# 适度压缩
IMAGE_MAX_SIZE=1024
IMAGE_QUALITY=85

# 合理限额
DAILY_MULTIMODAL_LIMIT=100
```

**预期成本**: 节省 40-50%

### 场景 3: 质量优先

```bash
# 轻度压缩
IMAGE_MAX_SIZE=2048
IMAGE_QUALITY=90

# 宽松限额
DAILY_MULTIMODAL_LIMIT=200
```

**预期成本**: 节省 20-30%

## 🔧 故障排查

### 问题 1: Pillow 未安装

**日志**:
```
[WARNING] Pillow not installed. Image compression will be disabled.
[WARNING] Install: pip install Pillow
```

**解决**:
```bash
pip install Pillow>=10.0.0
docker-compose restart
```

### 问题 2: 图片压缩失败

**日志**:
```
[ERROR] Image compression failed: ...
```

**原因**: 图片格式不支持或文件损坏

**结果**: 自动使用原始图片（不影响功能）

### 问题 3: 配额文件权限错误

**日志**:
```
[ERROR] Failed to save quotas: Permission denied
```

**解决**:
```bash
chmod 644 data/user_quotas.json
chown your-user:your-group data/user_quotas.json
```

### 问题 4: 用户抱怨限额太低

**调整配置**:
```bash
# 增加限额
DAILY_MULTIMODAL_LIMIT=200
```

**或临时重置用户**:
需要实现管理命令（可选功能）

## 💡 优化技巧

### 1. 动态调整压缩质量

根据图片大小自动调整：

```python
# 建议添加到 image_compressor.py
if original_size > 5_000_000:  # 5MB
    quality = 70  # 高压缩
elif original_size > 2_000_000:  # 2MB
    quality = 80  # 中压缩
else:
    quality = 85  # 轻压缩
```

### 2. VIP 用户无限额

```python
# 建议添加到 quota_manager.py
VIP_USERS = ["user_vip1", "user_vip2"]

if user_id in VIP_USERS:
    return True, 0, 99999
```

### 3. 图片缓存复用

当前已实现 URL 缓存，相同图片不重复下载和压缩。

### 4. 监控告警

设置告警脚本：

```bash
#!/bin/bash
# alert_quota.sh

total=$(jq '[.users[].multimodal] | add' data/user_quotas.json)

if [ "$total" -gt 5000 ]; then
    echo "WARNING: Daily quota usage > 5000!" | mail admin@example.com
fi
```

## 📈 成本节省估算

### 压缩效果

| 原始大小 | 压缩后 | 节省 |
|---------|--------|------|
| 2MB | 800KB | 60% |
| 1MB | 500KB | 50% |
| 500KB | 300KB | 40% |

### 配额效果

**假设**: 100 用户，原本每人每天 150 次多模态

- **无限额**: 100 × 150 = 15,000 次/天
- **限额 100**: 100 × 100 = 10,000 次/天
- **节省**: 33%

### 综合效果

```
图片压缩节省: 50%
配额限制节省: 33%
总体节省: 约 65-70%
```

**实际案例**:
- 原成本: $50/月
- 优化后: $15-17/月
- **节省**: $33-35/月

## 📋 部署清单

- [x] 安装 Pillow
- [x] 上传新文件
- [x] 配置环境变量
- [x] 创建数据目录
- [x] 重启服务
- [ ] 验证图片压缩
- [ ] 验证配额限制
- [ ] 监控使用情况
- [ ] 调整配置参数

---

**部署人**: _______  
**部署日期**: _______  
**验证状态**: ☐ 通过 ☐ 失败  
**备注**: _________________________
