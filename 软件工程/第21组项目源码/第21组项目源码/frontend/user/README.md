# BookFlow Reader Frontend

读者端是独立的 React + Vite 应用，面向读者提供登录注册、首页推荐、图书检索、借阅记录、预约、通知、个人中心和 BookFlow AI。

## 目录

```text
src/
  components/   读者端布局、图书卡片、AI 组件和通用状态组件
  hooks/        React Query 数据 hooks
  pages/        读者业务页面和认证页面
  services/     读者 API 封装
  styles/       读者端全局样式和页面样式
  types/        前端类型
  utils/        日期、状态和 className 工具
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

## 后端契约

读者端使用独立读者接口：

- `/reader-auth/*`：读者登录、注册、验证码和找回密码
- `/reader/*`：读者首页、个人中心、借阅、预约和通知
- `/public/*`：公开图书检索
- `/reader-ai/*`：读者 AI 对话和建议

管理员 token 不能访问读者接口，读者 token 也不能访问管理员接口。

## AI 组件

`src/components/ai` 只负责读者端聊天 UI。语言理解、上下文改写、工具选择、业务权限校验和最终回答由后端 `reader_ai_service` 完成。前端不要加入关键词特例或业务规则分支。
