# WAA — WeChat AI Auto Reply Agent

macOS 本地运行的个人微信 AI 自动回复系统。通过 Accessibility API 读取微信消息，由 LLM 生成回复，自动发送。

## 系统要求

- macOS 26+ (Apple Silicon arm64)
- Python 3.12+
- 微信 Mac 客户端已登录
- **Accessibility 权限**（必须在系统设置中授予终端应用）

## 安装

```bash
# 1. 克隆仓库
git clone <repo> && cd Ai-coding-program-001/waa

# 2. 安装依赖（创建 .venv）
./scripts/install.sh

# 3. 配置环境变量
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
# 健康检查（需要微信已启动）
./scripts/status.sh

# 启动 Agent（前台运行）
./scripts/start.sh

# 运行测试
./scripts/test.sh

# 停止
./scripts/stop.sh

# 系统诊断
./scripts/doctor.sh
```

## launchd 自动启动（可选）

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

### REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 系统健康状态 |
| `/stats` | GET | 今日统计数据（收/回/拦截/失败） |
| `/events` | GET | 最近事件（默认 50 条） |
| `/contacts` | GET | 联系人列表 |
| `/replies` | GET | AI 回复记录（默认 100 条） |
| `/settings` | GET | 当前配置 |
| `/settings` | POST | 更新配置 |
| `/persona` | GET | 人格配置 |
| `/persona` | PUT | 更新人格 |
| `/system-state` | GET | 系统运行状态 |
| `/emergency-stop` | POST | 紧急停止（禁用所有自动回复） |
| `/` | GET | HTML Dashboard 界面 |

## 架构

```
WeChat.app (Accessibility API)
    ↓
MessageListener (轮询 2s)
    ↓
SQLite Queue (WAL mode)
    ↓
MessageWorker (去重 + 安全检查 + AI 生成 + 发送)
    ↓
Watchdog (心跳监控)
    ↓
FastAPI Dashboard (127.0.0.1:8765)
```

### 核心模块

| 模块 | 说明 |
|------|------|
| `app/state.py` | AppState 单例 — auto_reply / safe_mode / emergency_stop |
| `app/config.py` | Pydantic BaseSettings + Persona YAML 持久化 |
| `app/logging_config.py` | 日志（轮转 + SecretRedactor 密钥脱敏） |
| `app/safety/policy.py` | 安全策略引擎（4 级风险：critical/high/medium/low） |
| `app/safety/validator.py` | 回复验证器（长度、敏感词过滤） |
| `app/deduplicator.py` | 消息去重（SHA-256 key + TTL + 线程锁） |
| `app/throttle.py` | 回复节流（防止快速连发，冷却窗口 3-8s） |
| `app/agent.py` | AI 对话代理（OpenAI 兼容接口，支持自定义 base_url） |
| `app/worker.py` | 消息处理主循环（安全→AI→验证→发送） |
| `app/listener.py` | 消息监听器（轮询未读消息） |
| `app/watchdog.py` | 系统监控（心跳 + 超时检测） |
| `app/dashboard.py` | FastAPI 仪表盘（11 个 REST 端点） |
| `app/database.py` | SQLite 数据库层（参数化查询，防 SQL 注入） |
| `app/wechat/accessibility_adapter.py` | Accessibility API 消息采集 |

## 安全特性

- **Prompt Injection 防护**：安全策略引擎检测注入攻击
- **敏感词拦截**：金钱/密码/验证码/合同类消息自动阻止（critical 风险）
- **黑名单话题匹配**：政治/暴力/色情/赌博等 topic 自动 block
- **回复验证器**：生成后二次校验长度和敏感内容
- **API Key 脱敏**：SecretRedactor 确保密钥不写入日志
- **本地持久化**：所有消息存 SQLite，不上传云端
- **最小上下文**：只发送最近 20 条消息给 LLM
- **Dashboard 绑定 127.0.0.1**：不接受外部网络访问
- **紧急停止**：一键禁用全部自动回复

## 配置说明

通过 `.env` 文件配置（见 `.env.example`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | — | OpenAI 兼容 API Key |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API 端点 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `HIGH_RISK_MODE` | `block` | 高风险处理方式（block/warn） |
| `SAFE_MODE` | `true` | 安全模式（仅记录不发送） |
| `AUTO_REPLY_ENABLED` | `true` | 是否启用自动回复 |
| `DASHBOARD_HOST` | `127.0.0.1` | Dashboard 绑定地址 |
| `DASHBOARD_PORT` | `8765` | Dashboard 端口 |
| `MAX_REPLY_LENGTH` | `120` | 最大回复字符数 |
| `REPLY_MIN_DELAY` | `3` | 最小回复间隔（秒） |
| `REPLY_MAX_DELAY` | `8` | 最大回复间隔（秒） |

### Persona 配置

通过 Dashboard `PUT /persona` 或编辑 `data/persona.yaml` 调整 AI 人格：

```yaml
name: 小助手
personality: 你是一个友好、热情的AI助手
tone: friendly
emoji: true
response_length: short
rules:
  - 回复要简洁，不超过120字
  - 用对方使用的语言回复
blacklist_topics:
  - 政治敏感
  - 暴力内容
  - 色情内容
  - 赌博相关
  - 非法活动
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `Accessibility denied` | 在系统设置 → 辅助功能中授予终端权限 |
| `WeChat not running` | 确保微信 Mac 客户端已打开并登录 |
| `Database locked` | 检查是否有其他进程占用数据库 |
| `LLM timeout` | 检查网络或 LLM API 配置是否正确 |
| `Dashboard unreachable` | 检查 127.0.0.1:8765 是否被防火墙阻止 |
| 发送消息后无回复 | 检查 Dashboard `/health` 和 `/events` 日志 |
| 重复消息 | 检查去重器 TTL 配置（默认 3600s） |
| 回复过慢 | 降低 `REPLY_MIN_DELAY` / `REPLY_MAX_DELAY` |

## 开发

```bash
# 从项目根目录运行测试
python -m pytest tests/ -v
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

## CI/CD

GitHub Actions 自动运行（全绿 ✅）：
- Python 3.11 / 3.12 / 3.13 多版本测试
- 61 项测试通过（含压力测试）
- 覆盖率报告
- 健康检查

## 文件结构

```
waa/
├── app/                    # 核心应用
│   ├── __init__.py
│   ├── main.py            # 入口 + 进程管理
│   ├── config.py          # 配置 + Persona
│   ├── state.py           # AppState 单例
│   ├── agent.py           # AI 对话代理
│   ├── database.py        # SQLite 层
│   ├── dashboard.py       # FastAPI 仪表盘
│   ├── listener.py        # 消息监听
│   ├── worker.py          # 消息处理
│   ├── watchdog.py        # 系统监控
│   ├── deduplicator.py    # 去重器
│   ├── throttle.py        # 节流器
│   ├── logging_config.py  # 日志配置
│   ├── wechat_adapter.py  # 适配器接口
│   ├── safety/            # 安全引擎
│   └── wechat/            # Accessibility 实现
├── tests/                  # 测试套件（61 项）
├── scripts/               # 运维脚本
├── launchd/               # macOS 服务配置
├── data/                  # SQLite + PID（不入库）
└── requirements.txt
```

## License

MIT
