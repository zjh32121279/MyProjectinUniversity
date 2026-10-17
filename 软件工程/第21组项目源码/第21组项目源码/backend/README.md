# BookFlow Backend

后端是 BookFlow 的业务核心，负责认证、权限、馆藏、借阅、预约、读者、通知、任务、数据分析、审计治理和 AI 工具调度。

## 技术栈

- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- SQLite
- pytest

包配置在 `pyproject.toml`，应用入口是 `bookflow_core.main:app`。

## 目录

```text
bookflow_core/
  main.py       创建 FastAPI app、CORS、异常处理和路由挂载
  api/          HTTP 路由层
  services/     业务服务和页面级聚合
  db/           数据库模型、建表和元数据脚本
  schemas/      Pydantic 请求和响应模型
  core/         配置、数据库、安全、异常和时间工具
  ai/           AI 对话规划、工具注册、策略守卫和执行内核
  ai_tools/     面向 AI 的业务工具实现
  data/         本地运行数据库和上传文件，不提交到 Git
```

## 运行

```bash
cd backend
python -m pip install -e .
python -m uvicorn bookflow_core.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```text
GET /health
```

## 配置

复制 `.env.example` 后填写本地配置。关键项：

```text
BOOKFLOW_DATABASE_URL=sqlite:///./data/bookflow.db
BOOKFLOW_SECRET_KEY=replace-with-a-local-secret
BOOKFLOW_AI_ENGINE_BASE_URL=https://your-provider.example/v1
BOOKFLOW_AI_ENGINE_API_KEY=replace-with-your-key
BOOKFLOW_AI_ENGINE_NAME=your-model-name
```

## HTTP 接口边界

- 管理员认证：`/auth`
- 读者认证：`/reader-auth`
- 读者公开检索：`/public`
- 读者门户：`/reader`
- 读者 AI：`/reader-ai`
- 普通管理员业务：`/catalog`、`/circulation`、`/readers`、`/notifications`、`/tasks`、`/dashboard`、`/analytics`
- 普通管理员规则只读：`/rules/borrow`
- 管理员 AI 工作台：`/ai/engine/status`、`/ai/conversations`、`/ai/chat`
- 超级管理员治理：`/super-admin/overview`、`/super-admin/admins`、`/super-admin/ai-rules`、`/super-admin/audit-security/*`

旧的直连 AI 工具执行、审批、快照回滚、独立预约列表、手动提醒触发等 HTTP 面已经移除。内部服务函数和 AI 工具按业务链路保留，不直接暴露给前端页面。

## AI 对话链路

管理员端和读者端 AI 都采用同一类规划链路：

```text
recent messages -> standalone_request -> structured tool plan -> permission guard -> tool/kernel execution -> grounded reply
```

模型负责语言理解和工具选择；后端负责工具白名单、权限校验、参数 schema 校验、审计和异常兜底。禁止为单个截图、关键词或固定问法写硬编码特例。

## 验证

```bash
python -m compileall -q bookflow_core
python -m pytest ../tests/core
python ../scripts/check_data_consistency.py
python ../scripts/audit_business_chains.py
```
