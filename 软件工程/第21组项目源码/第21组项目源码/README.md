# BookFlow

BookFlow 是一个前后端分离的图书馆管理系统，包含读者端、管理端（普管）、超级管理员端和 FastAPI 后端。系统覆盖馆藏编目、借阅流通、预约管理、读者信用、通知提醒、数据看板、审计治理和 AI 辅助运营，共约 5.5 万行代码。

## 项目结构

```
BookFlow_演示版/
├── backend/                         # Python 后端 (FastAPI)
│   ├── bookflow_core/
│   │   ├── api/                     #   API 路由层 (19 个模块)
│   │   ├── services/                #   服务层 (40 个模块)
│   │   ├── ai/                      #   AI 内核 (聊天/引擎/工具/工作流)
│   │   ├── schemas/                 #   Pydantic 请求/响应模型
│   │   ├── db/                      #   数据库初始化与迁移
│   │   └── core/                    #   配置、数据库会话、异常处理
│   └── data/
│       ├── bookflow.db              #   SQLite 数据库 (100 本预置图书)
│       └── uploads/                 #   图书封面、读者头像
├── frontend/
│   ├── user/                        # 读者端 (端口 5173)
│   ├── bookflow-admin/              # 管理端 (端口 5174)
│   ├── bookflow_superadmin/         # 超管端 (端口 5175)
│   └── common/                      # 三端共享 (登录组件、HTTP 封装、工具函数)
├── tests/core/                      # 后端测试 (10 个文件, 49 个用例)
├── scripts/                         # 数据导入、一致性校验、冒烟测试
├── docs/                            # UI 设计参考截图
└── artifacts/                       # 导出文件
```

## 环境配置

### 前置要求

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Python | ≥ 3.11 | 后端运行环境 |
| Node.js | ≥ 18 | 前端运行环境（推荐 20 LTS） |
| npm | ≥ 9 | 随 Node.js 附带 |

验证安装：

```bash
python --version   # 应输出 3.11 或更高
node --version     # 应输出 v18 或更高
npm --version      # 应输出 9 或更高
```

### 1. 后端配置

```bash
# 进入后端目录
cd backend

# 安装 Python 依赖
pip install fastapi python-multipart sqlalchemy pydantic uvicorn

# 或使用 pyproject.toml 一键安装
pip install -e .

# 配置环境变量（从模板复制）
cp .env.example .env
```

编辑 `backend/.env`，按需修改以下配置：

```text
# 数据库路径（默认 SQLite，无需改动）
BOOKFLOW_DATABASE_URL=sqlite:///./data/bookflow.db

# AI 引擎配置（如需使用 AI 功能，请填写实际的 API 地址和密钥）
BOOKFLOW_AI_ENGINE_BASE_URL=https://api.deepseek.com
BOOKFLOW_AI_ENGINE_API_KEY=sk-your-api-key
BOOKFLOW_AI_ENGINE_NAME=deepseek-v4-pro

# SMTP 邮件配置（用于发送验证码和通知邮件，请填写实际的邮箱信息）
BOOKFLOW_SMTP_HOST=smtp.example.com
BOOKFLOW_SMTP_PORT=465
BOOKFLOW_SMTP_USER=your-email@example.com
BOOKFLOW_SMTP_PASSWORD=your-smtp-password
BOOKFLOW_SMTP_FROM=your-email@example.com

# 验证码调试模式（true=跳过邮件，控制台打印验证码；false=发送真实邮件）
BOOKFLOW_DEBUG_VERIFICATION_CODE=false
```

> 💡 **说明**：项目预置了包含 100 本图书的 SQLite 数据库 `backend/data/bookflow.db`，无需额外迁移。AI 功能为可选模块，不配置不影响基础借阅管理。SMTP 默认使用 163 邮箱，开发调试时可设置 `BOOKFLOW_DEBUG_VERIFICATION_CODE=true` 跳过邮件发送。

### 2. 前端配置

三个前端项目需要分别安装依赖：

```bash
# 读者端
cd frontend/user
npm install

# 管理端
cd ../bookflow-admin
npm install

# 超管端
cd ../bookflow_superadmin
npm install
```

> 💡 `frontend/common/` 为共享模块，已被其他三个项目引用，无需单独安装。

### 3. 验证环境

启动全部服务，确认各端口可访问：

```bash
# 回到项目根目录，一键启动
manage.bat
```

正常启动后应看到四个服务就绪，访问对应地址确认页面可打开。详细账号密码见下方快速启动章节。

---

## 快速启动

项目根目录提供 `manage.bat` 脚本一键管理全部四个服务：

```bat
manage.bat          # 启动全部服务（默认）
manage.bat start    # 同上
manage.bat stop     # 关闭全部服务
```

启动后可访问：

| 服务 | 地址 | 登录凭据 |
|------|------|---------|
| 读者端 | http://localhost:5173 | reader-adult-001@bookflow.local / Reader@2026 |
| 管理端 | http://localhost:5174 | A02-001 / BookFlow@123456 |
| 超管端 | http://localhost:5175 | A01-001 / BookFlow@123456 |
| 后端 API | http://127.0.0.1:8000 | — |

也可手动启动单个服务：

```bash
# 后端
cd backend
python -m uvicorn bookflow_core.main:create_app --factory --host 127.0.0.1 --port 8000 --reload

# 前端（三个目录分别执行）
cd frontend/user && npx vite --host 127.0.0.1 --port 5173
cd frontend/bookflow-admin && npx vite --host 127.0.0.1 --port 5174
cd frontend/bookflow_superadmin && npx vite --host 127.0.0.1 --port 5175
```

必要环境变量参考 `backend/.env.example`，本地默认数据库为 `backend/data/bookflow.db`。三个前端通过 Vite proxy 将 `/api` 和 `/uploads` 请求转发至后端 8000 端口，默认 API 地址也可通过 `VITE_API_BASE_URL` 覆盖。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | SQLite + SQLAlchemy ORM |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS |
| 状态管理 | TanStack Query + Zustand |
| 图表 | ECharts |
| AI 引擎 | DeepSeek API (OpenAI-compatible) |
| 测试 | pytest |

## AI 架构

BookFlow AI 使用 OpenAI-compatible Chat Completions 接口接入 DeepSeek 大模型。后端通过 AI 内核（`bookflow_core/ai/kernel/`）管理任务队列、工作流引擎（SOP）、工具调度和权限治理，形成"语言理解 → 工具规划 → 权限校验 → 执行 → 有依据回答"的完整链路。关键设计原则是**人机协同**——AI 生成建议但不直接执行高风险操作，所有写操作需管理员在待处理中心审核确认后生效。

关键环境变量：

```text
BOOKFLOW_AI_ENGINE_BASE_URL
BOOKFLOW_AI_ENGINE_API_KEY
BOOKFLOW_AI_ENGINE_NAME
```

## 测试

```bash
# 后端单元测试
cd backend
PYTHONPATH=. python -m pytest ../tests/ -v

# 数据一致性校验
python scripts/check_data_consistency.py

# 业务链审计
python scripts/audit_business_chains.py
```

测试结果：10 个测试文件共 49 个用例，47 通过，2 失败，通过率 95.9%。两个失败用例为 AI 预约通知的边界幂等性场景，核心借阅闭环不受影响。三端共 20 个手工测试场景全部通过。

## Git 提交边界

应提交源代码、测试、脚本、README 和配置示例。不要提交：

- `backend/data/*.db`
- `backend/data/uploads/`
- `node_modules/`、`dist/`
- `artifacts/`
- `.pytest_cache/`
- `.env`
