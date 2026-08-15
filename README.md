# AI Server Notify

通过 [ntfy](https://ntfy.sh/) 将服务器上的 Codex、Claude Code 和 `tmux` 长任务状态推送到 Windows 通知中心。PowerShell、SSH、VS Code 可以最小化或关闭，不必反复打开终端查看 AI 是否已经完成。

项目默认只发送主机、项目、时间、短会话号、任务名和退出码，不发送提示词、源代码、日志或完整回答。

## 能通知什么

| 场景 | 触发方式 |
| --- | --- |
| Codex 完成一轮工作 | Codex `notify` |
| Claude Code 完成一轮工作 | Claude `Stop` Hook |
| Claude API 限流、认证或模型错误 | Claude `StopFailure` Hook |
| Claude 等待权限或用户输入 | `PermissionRequest` / `Notification` Hook |
| Claude 会话结束 | Claude `SessionEnd` Hook |
| 训练、评估或脚本成功/失败/中断 | `notify-run` 捕获真实退出码 |

```text
Codex notify ───────────┐
Claude Hooks ───────────┤
tmux / shell command ───┼──> ai-notify ──> ntfy ──> Windows / 手机
                       ┘
```

## 依赖

服务器端只需要：

- Linux
- Python 3.9 或更高版本
- Bash
- Codex CLI、Claude Code 和 tmux 均为可选，按需接入

不需要安装额外 Python 包。

## 快速安装

```bash
git clone git@github.com:genmlite/ai-server-notify.git
cd ai-server-notify
./install.sh
```

安装器会：

- 安装 `ai-notify` 和 `notify-run` 到 `~/.local/bin`
- 创建权限为 `700` 的配置和状态目录
- 首次安装时创建权限为 `600` 的配置文件
- 保留已有配置，不覆盖真实主题或令牌

如果 `~/.local/bin` 不在 `PATH` 中，把下面一行加入 shell 配置：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 配置 ntfy

先生成一个足够长、不可猜测的主题名：

```bash
python3 -c 'import secrets; print("ai-" + secrets.token_hex(18))'
```

编辑 `~/.config/ai-notify/config.json`：

```json
{
  "server_url": "https://ntfy.sh",
  "topic": "ai-replace-with-your-random-value",
  "host_label": "gpu-server-01",
  "token": ""
}
```

字段说明：

- `server_url`：公共 ntfy 或自建 ntfy 地址。
- `topic`：相当于订阅密码，不要使用简单名称或提交到 Git。
- `host_label`：通知中显示的服务器名称；留空时使用系统 hostname。
- `token`：自建 ntfy 启用认证时填写；公共随机主题通常留空。

发送测试：

```bash
ai-notify test
```

通知器的本地轮转日志位于：

```text
~/.local/state/ai-notify/notify.log
```

## Windows 订阅

1. 使用 Edge 或 Chrome 打开 `https://ntfy.sh/<你的主题>`。
2. 点击订阅并允许浏览器通知。
3. 建议将 ntfy 网页安装为 PWA 应用。
4. 在“Windows 设置 → 系统 → 通知”中允许 Edge、Chrome 或 ntfy 通知。
5. 在服务器再次执行 `ai-notify test` 验证右下角弹窗。

订阅成功后，不需要保持 PowerShell 或 SSH 窗口打开。电脑关机期间服务器仍可继续运行 tmux 任务；ntfy 的消息保留时长取决于服务端配置。

## 接入 Codex

将下面配置加入 `~/.codex/config.toml` 的顶层，并放在任何 `[table]` 之前。把 `YOUR_USER` 替换为 Linux 用户名：

```toml
notify = ["/home/YOUR_USER/.local/bin/ai-notify", "codex"]
```

示例文件见 [`examples/codex-config.toml`](examples/codex-config.toml)。重新启动 Codex 会话后生效。

Codex 当前的外部 `notify` 事件主要是 `agent-turn-complete`，因此它表示 AI 一轮工作结束，不保证 AI 启动的后台训练已经完成。训练和评估应另外使用 `notify-run`。

参考：[OpenAI Codex notifications](https://learn.chatgpt.com/docs/config-file/config-advanced#notifications)。

## 接入 Claude Code

把 [`examples/claude-hooks.json`](examples/claude-hooks.json) 中的 `hooks` 合并到 `~/.claude/settings.json`。不要直接覆盖已有的 `env`、权限或其他 Hooks。

配置覆盖：

- `Stop`
- `StopFailure`
- `PermissionRequest`
- `Notification` 中的 `agent_needs_input` 和 MCP elicitation
- `SessionEnd`

重新启动 Claude Code 会话后生效。Claude Code 需要能够从 `PATH` 找到 `ai-notify`；也可以把示例中的命令改成绝对路径。

参考：[Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)。

## 接入 tmux 长任务

`notify-run` 会运行给定命令，保留原始退出码，并在成功、失败或中断时发送通知：

```bash
notify-run --name "train-baseline" -- python -u train.py
```

在 tmux 中使用并持久记录日志：

```bash
mkdir -p logs
tmux new-session -d -s project_train_20260815 \
  'bash -lc "set -o pipefail; notify-run --name train-baseline -- python -u train.py 2>&1 | tee -a logs/train-baseline.log"'
```

常用查看命令：

```bash
tmux attach -t project_train_20260815
tail -f logs/train-baseline.log
```

建议每个长任务使用独立 tmux session、持久日志和 checkpoint。不要用强制杀进程的方式停止训练；优先进入 tmux 后按 `Ctrl-C`，`notify-run` 会将常见中断标记为 interrupted。

## 命令行接口

通常由 Hooks 调用，无需手工执行：

```text
ai-notify test
ai-notify codex '<codex-json-payload>'
ai-notify claude-stop              # 从 stdin 读取 Claude Hook JSON
ai-notify claude-failure
ai-notify claude-permission
ai-notify claude-needs-input
ai-notify claude-session-end
ai-notify task STATUS NAME EXIT_CODE ELAPSED_SECONDS
```

可用于测试和自动化的环境变量：

| 变量 | 用途 |
| --- | --- |
| `AI_NOTIFY_CONFIG` | 覆盖配置文件路径 |
| `AI_NOTIFY_LOG` | 覆盖日志路径 |
| `AI_NOTIFY_DRY_RUN=1` | 完成解析但不向 ntfy 发请求 |
| `AI_NOTIFY_BIN` | 让 `notify-run` 使用指定通知器路径 |

## 安全建议

- 将 ntfy 主题当作密码，使用至少 128 位随机值。
- 确保配置文件权限为 `600`：`chmod 600 ~/.config/ai-notify/config.json`。
- 不要把真实主题、Token 或带秘密的日志提交到 Git。
- 公共 ntfy 主题只适合发送低敏感度状态信息。
- 对敏感环境，建议自建 ntfy、启用访问控制，并填写 `token`。
- 本项目默认不读取或发送 Codex/Claude 的完整回答和提示词。

## 已知边界

- 服务器断电或网络完全中断时，服务器无法主动发出 ntfy 消息。要监控整机掉线，需要 Healthchecks.io、Uptime Kuma 或独立监控机的外部心跳。
- “进程仍存在但已经卡住”没有可靠的通用判断标准，需要按任务设置超时或业务心跳。
- Codex 的 turn complete 与后台训练完成是两个不同事件。
- 已经运行的任务不会被追溯包装，需要在启动命令中使用 `notify-run`。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试使用 dry-run 和临时配置，不会发送真实 ntfy 消息。
