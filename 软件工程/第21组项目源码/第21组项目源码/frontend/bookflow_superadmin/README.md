# BookFlow Super Admin Frontend

超级管理员端是独立的 React + Vite 应用，负责治理首页、管理员管理、AI 与规则控制、审计与安全。

## 目录

```text
src/
  app/          路由和全局 Provider
  api/          超级管理员页面级 API 契约
  components/   超管专属布局、图标和状态组件
  pages/        超级管理员页面
  stores/       登录态和当前管理员信息
  styles/       超管样式
```

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
node scripts/quick_screenshots.mjs --only=superadmin --start-dev
```

## 路由范围

- `/super-admin/home`
- `/super-admin/admins`
- `/super-admin/ai-rules`
- `/super-admin/audit-security`

## 后端契约

本应用优先调用 `/super-admin/*` 页面级接口。关键接口集中封装在 `src/api/superAdmin.ts`：

- `/super-admin/overview`
- `/super-admin/admins`
- `/super-admin/admins/login-events`
- `/super-admin/ai-rules`
- `/super-admin/ai-rules/{rule_id}/toggle`
- `/super-admin/audit-security/events`
- `/super-admin/audit-security/export`
- `/super-admin/audit-security/export-jobs/{export_code}/download`

页面不再从多个底层接口临时拼装风险、Token、权限或 AI 审批队列。规则治理统一走 `/super-admin/ai-rules`。

## 边界

普通管理员业务页面不放在本应用。共享登录、HTTP、格式化、标签和通用类型放 `frontend/common`；超管专属组件和页面保留在 `bookflow_superadmin`。
