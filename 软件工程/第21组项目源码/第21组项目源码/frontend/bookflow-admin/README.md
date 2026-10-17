# BookFlow Admin Frontend

普通管理员端是独立的 React + Vite 应用，负责日常图书馆运营：馆藏、借阅、预约、读者、通知、任务、数据中心和 AI 工作台。

## 目录

```text
src/
  app/          路由和全局 Provider
  api/          普通管理员 API 封装
  components/   页面组件、布局组件、AI 组件和 UI 基础组件
  pages/        普通管理员页面
  stores/       登录态和当前管理员信息
  styles/       全局样式
  types/        前端类型
  utils/        格式化、图表、导出等工具
```

`src/api/http.ts` 复用 `frontend/common/src/api/http.ts`，不要在本应用里维护第二套 HTTP 拦截器。

## 运行

```bash
npm install
npm run dev
```

构建：

```bash
npm run build
```

截图验收从仓库根目录运行：

```bash
node scripts/quick_screenshots.mjs --only=admin --start-dev
```

## 路由范围

普通管理员业务路由使用 `/admin/*`：

- `/admin/home`
- `/admin/ai`
- `/admin/tasks`
- `/admin/catalog`
- `/admin/borrowing/*`
- `/admin/readers`
- `/admin/notifications`
- `/admin/data`
- `/admin/settings`

登录页共用 `frontend/common` 的 `SharedLoginView`。超级管理员页面、菜单和治理逻辑不要放进本应用。

## 后端契约

当前页面实际使用的主要接口：

- `/ai/engine/status`、`/ai/conversations`、`/ai/chat`
- `/catalog/books`、`/catalog/copies`、`/catalog/categories`、`/catalog/subcategories`
- `/circulation/borrow`、`/circulation/return`、`/circulation/renew`
- `/circulation/pending-requests`、`/circulation/requests/{code}/*`、`/circulation/reservations`
- `/readers`
- `/notifications`、`/notifications/stats`、`/notifications/recipient-options`、`/notifications/batch`
- `/tasks`
- `/dashboard/admin`、`/analytics/*`
- `/rules/borrow`

不再从本端调用旧的直连 AI 工具、审批、快照、独立预约列表、手动提醒触发或超管治理接口。

## AI 工作台

AI 工作台只负责对话展示、会话管理、运行结果和错误状态。语言理解、上下文改写、工具规划和权限校验由后端 AI 链路完成。聊天请求使用更长超时，不继承普通接口的 18 秒默认超时。
