# WAA — WeChat AI Auto Reply Agent

macOS 本地运行的个人微信 AI 自动回复系统。

## 系统要求

- macOS 26+ (Apple Silicon arm64)
- Python 3.12+
- 微信 Mac 客户端已登录
- **Accessibility 权限**（必须在系统设置中授予终端应用）

## 安装

```bash
./scripts/install.sh
```

## 配置

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 LLM_BASE_URL
```

## 授权步骤（必须）

1. 打开 **系统设置** → **隐私与安全性** → **辅助功能**
2. 点击 `+`，添加你正在使用的终端应用（Terminal.app 或 Claude Code 所在终端）
3. 重启终端
4. 验证：
   ```bash
   osascript -e 'tell application "System Events" to tell process "WeChat" to get name of every UI element'
   ```
   如果返回 UI 元素名称而非错误，则授权成功。

## 运行

```bash
# 健康检查
./scripts/status.sh

# 启动 Agent
./scripts/start.sh

# 测试
./scripts/test.sh

# 停止
./scripts/stop.sh
```

## launchd 自动启动

```bash
# 安装
cp macos/launchd/com.arris.wechat-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.arris.wechat-agent.plist

# 卸载
launchctl unload ~/Library/LaunchAgents/com.arris.wechat-agent.plist
rm ~/Library/LaunchAgents/com.arris.wechat-agent.plist
```

## Dashboard

启动后访问: http://127.0.0.1:8765

## 架构

```
WeChat.app
    ↑
WeChatAdapter (Accessibility API)
    ↑
MessageListener → SQLite Queue
    ↑
Worker (Dedup + Safety + AI + Send)
    ↑
Watchdog (Health Monitor)
```

## 安全

- 所有消息持久化到本地 SQLite
- AI 回复经过 Safety Policy 和 Reply Validator 双重校验
- 金钱/密码/验证码/合同类消息自动拦截
- Prompt Injection 防护
- API Key 不进 Git
- Dashboard 只监听 127.0.0.1

## 隐私

- 聊天记录仅存本地，不上传
- 日志脱敏处理
- 最小化发送给 LLM 的上下文

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `Accessibility denied` | 在系统设置中授予终端 Accessibility 权限 |
| `WeChat not running` | 确保微信 Mac 客户端已打开 |
| `Database locked` | 检查是否有其他进程占用 |
| `LLM timeout` | 检查网络或 LLM API 配置 |

## License

MIT
