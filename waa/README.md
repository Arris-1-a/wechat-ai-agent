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
# 安装依赖
./scripts/install.sh

# 健康检查
./scripts/status.sh

# 启动 Agent
./scripts/start.sh

# 运行测试
./scripts/test.sh

# 停止
./scripts/stop.sh
```

## launchd 自动启动

```bash
# 安装（使用新路径）
cp launchd/com.user.wechat-ai-agent.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.wechat-ai-agent.plist

# 卸载
launchctl unload ~/Library/LaunchAgents/com.user.wechat-ai-agent.plist
rm ~/Library/LaunchAgents/com.user.wechat-ai-agent.plist
```

## Dashboard

启动后访问: **http://127.0.0.1:8765**

支持操作：
- `GET /health` — 系统健康状态
- `GET /stats` — 今日统计数据
- `GET /events` — 最近事件
- `GET /contacts` — 联系人列表
- `GET /replies` — AI 回复记录
- `GET /settings` — 当前配置
- `POST /settings` — 更新配置
- `GET /persona` — 人格配置
- `PUT /persona` — 更新人格
- `GET /system-state` — 系统状态
- `POST /emergency-stop` — 紧急停止

## 架构

```
WeChat.app
    ↑
WeChatAdapter (Accessibility API)
    ↑
MessageListener → SQLite Queue (WAL mode)
    ↑
MessageWorker (Dedup + Safety + AI + Send)
    ↑
Watchdog (Heartbeat Monitor)
```

### 核心模块

| 模块 | 说明 |
|------|------|
| `app/state.py` | AppState 单例 — 进程级共享状态 |
| `app/config.py` | 配置 + Persona YAML 系统 |
| `app/logging_config.py` | 日志（轮转 + 密钥脱敏） |
| `app/safety/policy.py` | 安全策略引擎（4 级风险） |
| `app/safety/validator.py` | 回复验证器 |
| `app/deduplicator.py` | 消息去重（SHA-256 + TTL） |
| `app/throttle.py` | 回复节流（防止快速连发） |
| `app/agent.py` | AI 对话代理（OpenAI 兼容） |
| `app/worker.py` | 消息处理工作器 |
| `app/listener.py` | 消息监听器 |
| `app/watchdog.py` | 系统监控 |
| `app/dashboard.py` | FastAPI 仪表盘 |
| `app/database.py` | SQLite 数据库层 |

## 安全

- 所有消息持久化到本地 SQLite
- AI 回复经过 Safety Policy 和 Reply Validator 双重校验
- 金钱/密码/验证码/合同类消息自动拦截
- Prompt Injection 防护
- API Key 不进 Git / 不落库 / 不记录日志（SecretRedactor）
- Dashboard 只监听 127.0.0.1
- 紧急停止（Emergency Stop）一键禁用自动回复

## 隐私

- 聊天记录仅存本地，不上传
- 日志自动脱敏处理
- 最小化发送给 LLM 的上下文（最近 20 条消息）

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `Accessibility denied` | 在系统设置中授予终端 Accessibility 权限 |
| `WeChat not running` | 确保微信 Mac 客户端已打开 |
| `Database locked` | 检查是否有其他进程占用 |
| `LLM timeout` | 检查网络或 LLM API 配置 |
| `dashboard unreachable` | 检查 127.0.0.1:8765 是否被防火墙阻止 |

## 开发

```bash
# 安装开发依赖
python -m pip install -e ".[dev]"
# 或
pip install -r requirements.txt

# 运行测试
pytest waa/tests/ -v

# 运行测试 + 覆盖率
pytest waa/tests/ -v --cov=waa --cov-report=term-missing
```

## CI/CD

GitHub Actions 自动运行：
- Python 3.11 / 3.12 / 3.13 多版本测试
- 覆盖率报告（目标 80%+）
- 健康检查

## License

MIT
