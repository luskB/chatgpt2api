# ChatGPT2API 自用增强版

> 本项目基于 [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api) 二次修改而来，当前已跟进到 upstream `v1.6.0`，并保留本仓库自定义的 LuckMail、MCP 搜索与独立鉴权、`8866` 端口和 Docker 本地源码构建等功能。

## 说明

这是一个自托管的 ChatGPT 相关能力封装项目，主要用于把 ChatGPT 官网的部分能力整理成 OpenAI 兼容风格接口，并提供 Web 管理页面。

本版本在原项目基础上主要增加了：

- LuckMail 邮箱提供商支持
- 同一邮箱失败后按配置重试
- 使用 upstream v1.6.0 OutlookToken 邮箱池，支持 Microsoft Graph / IMAP XOAUTH2
- Outlook 邮箱状态管理：未使用、占用中、已使用、token 失效、失败
- 默认本地服务端口改为 `8866`
- Docker Compose 默认从本地源码构建，而不是拉取原作者镜像
- 将搜索封装成MCP使用，并添加MCP鉴权

## 免责声明

本项目涉及对 ChatGPT 官网相关能力的研究和封装，仅供个人学习、技术研究和自用测试。

请勿用于：

- 商业售卖、转售、出租或代运营
- 批量滥用、自动化攻击、恶意竞争
- 违反 OpenAI 服务条款的行为
- 违法、欺诈、骚扰、侵权或其他不当用途

使用本项目可能导致账号受限、封禁或其他风险。请自行承担使用风险和法律责任。

## 功能概览

### OpenAI 兼容接口

常用接口：

```text
GET  /v1/models
POST /v1/chat/completions
POST /v1/responses
POST /v1/images/generations
POST /v1/images/edits
POST /v1/messages
```

默认访问地址：

```text
http://服务器IP:8866/v1
```

所有 API 请求需要携带：

```http
Authorization: Bearer <auth-key>
```

### MCP 搜索接口

本项目也提供一个 HTTP MCP 入口，方便支持 MCP 的客户端直接调用 ChatGPT 原生联网搜索能力：

```text
https://<public-ip>:8866/mcp?ApiKey=<auth-key>
```

本地测试地址示例：

```text
http://127.0.0.1:8866/mcp?ApiKey=<auth-key>
```

MCP 工具名为 `chatgpt_search`，参数为：

```json
{
  "prompt": "要搜索的问题"
}
```

### Web 管理页面

默认 Web 面板：

```text
http://服务器IP:8866
```

主要页面：

- `/image`：在线生图
- `/accounts`：号池管理
- `/register`：注册机配置
- `/image-manager`：图片管理
- `/logs`：日志管理
- `/debug`：调试页面
- `/settings`：系统设置

### 邮箱注册能力

本版本支持多种邮箱提供商，包括原项目已有 provider，以及本仓库新增的：

#### LuckMail

LuckMail 使用直接购买邮箱接口，而不是一次性接码订单接口。注册失败时可以复用同一个邮箱进行多次尝试。

常用配置项：

- `api_base`：默认 `https://mails.luckyous.com`
- `api_key`：LuckMail API Key
- `project_code`：项目代码，例如 `openai`
- `email_type`：邮箱类型，例如 `ms_graph`
- `domain`：可选域名
- `variant_mode`：仅部分邮箱类型需要
- `retry_limit`：同一邮箱失败重试次数，默认 `5`

#### OutlookToken 邮箱池

适合已经拥有的 Microsoft 邮箱，例如：

- Hotmail
- Outlook
- Live

支持三种取码方式：

- `Graph`：通过 Microsoft Graph + refresh_token 读取邮件
- `IMAP`：通过 IMAP XOAUTH2 读取邮件
- `Auto`：Graph 失败后自动回退到 IMAP

在 `/register` 页面添加 `outlook_token` provider，并将邮箱凭据粘贴到“邮箱池导入”文本框。

导入格式：

```text
email----password----client_id----refresh_token
```

说明：

- 使用 `----` 作为分隔符
- 真正用于 OAuth 取码的是 `client_id` 和 `refresh_token`
- 邮箱池保存在注册机配置中，状态记录保存在 `data/outlook_token_used.json`
- 配置 API 和 SSE 只返回邮箱脱敏预览，不回传密码和 refresh_token
- 页面支持清除失败/占用状态、清空未使用凭据和重置全部状态
- 旧版 `data/imported_mailboxes.json` 不会被删除，但 v1.6.0 版本不再读取它；请按上述格式重新导入

## Docker 部署

### 1. 克隆项目

```bash
git clone https://github.com/luskB/chatgpt2api.git
cd chatgpt2api
```

### 2. 创建配置文件

在项目根目录创建 `config.json`：

```json
{
  "auth-key": "请改成你自己的密码"
}
```

也可以参考项目内的默认配置自行补充更多设置。

### 3. 启动

```bash
docker compose up -d --build
```

启动后访问：

```text
Web 面板：http://服务器IP:8866
API 地址：http://服务器IP:8866/v1
```

### 4. 数据持久化

Docker Compose 已默认挂载：

```yaml
volumes:
  - ./data:/app/data
  - ./config.json:/app/config.json
```

因此账号数据、注册配置、导入邮箱记录等会保存在本地 `data` 目录。

## 本地开发

### 后端

```bash
uv sync
uv run uvicorn main:app --host 127.0.0.1 --port 8866 --reload
```

### 前端

```bash
cd web
bun install
bun run dev
```

开发环境前端默认请求：

```text
http://127.0.0.1:8866
```

## 配置说明

### 端口

本版本默认使用：

```text
8866:80
```

也就是：

- 容器内部端口：`80`
- 宿主机访问端口：`8866`

如果要改端口，修改 `docker-compose.yml`：

```yaml
ports:
  - "8866:80"
```

### 存储后端

支持通过环境变量配置存储方式：

```yaml
environment:
  STORAGE_BACKEND: sqlite
  DATABASE_URL: sqlite:////app/data/accounts.db
```

可选后端包括：

- `json`
- `sqlite`
- `postgres`
- `git`

当前 Docker Compose 默认使用 SQLite。

## 常用 API 示例

### 查看模型

```bash
curl http://127.0.0.1:8866/v1/models \
  -H "Authorization: Bearer <auth-key>"
```

### 图片生成

```bash
curl http://127.0.0.1:8866/v1/images/generations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "prompt": "一只漂浮在太空里的猫",
    "n": 1,
    "response_format": "b64_json"
  }'
```

### Chat Completions

```bash
curl http://127.0.0.1:8866/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <auth-key>" \
  -d '{
    "model": "gpt-image-2",
    "messages": [
      {
        "role": "user",
        "content": "生成一张雨夜东京街头的赛博朋克猫"
      }
    ]
  }'
```

## 从原项目同步

本仓库当前已同步原项目：

```text
basketikun/chatgpt2api v1.6.0
```

并在此基础上保留自定义功能。后续如果继续同步 upstream，重点注意这些文件的冲突：

```text
services/register/mail_provider.py
services/register/openai_register.py
web/src/app/register/components/register-card.tsx
web/src/lib/api.ts
web/src/components/top-nav.tsx
api/app.py
```

## 不要上传到公开仓库的文件

公开上传 GitHub 时，请不要上传：

```text
config.json
data/
.venv/
web/node_modules/
web/out/
web/.next/
web_dist/
start.bat
LuckMailSdk-Python (5)/
LuckMailSdk-Python (5).zip
web/package-lock.json
```

其中 `config.json`、`data/` 可能包含 auth key、邮箱密码、refresh_token、API key 等敏感信息。

## 致谢

本项目基于原项目二次修改：

```text
https://github.com/basketikun/chatgpt2api
```

感谢原作者和上游项目贡献者。
