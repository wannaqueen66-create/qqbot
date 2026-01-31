# NapCat 快速接入说明

## 1. 启动 NapCat
建议使用官方方式启动 NapCat（容器或本地安装均可）。

## 2. 打开 WebUI
在浏览器打开：
```
http://<napcat_host>:6099/webui
```
若提示 Token，可通过日志获取（示例）：
```bash
docker compose logs napcat | grep Token
```

## 3. 扫码登录
在 WebUI 内扫码登录你的 QQ 号。

## 4. 配置 OneBot 反向 WebSocket
在 WebUI → **网络配置** 中新增 **Reverse WS**：
- URL: `ws://<qqbot_host>:8080/onebot/v11/ws`
- Enable: `true`

> 如果 NapCat 和 qqbot 在同一台机器，`<qqbot_host>` 可写 `127.0.0.1`。

## 5. 验证连接
查看 qqbot 控制台或日志，确认连接成功。

---

## Docker 示例（参考）
```yaml
services:
  napcat:
    image: napcat/napcat:latest
    ports:
      - "6099:6099"
    volumes:
      - ./napcat/qq:/app/qq
      - ./napcat/config:/app/config
```
