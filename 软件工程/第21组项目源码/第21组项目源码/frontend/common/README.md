# Frontend Common

`frontend/common` 存放三个前端应用共享的基础能力，不承载普通管理员、超级管理员或读者端的专属业务。

## 当前内容

```text
src/api/http.ts               axios 实例、管理员 token 注入、响应解包、统一错误类型
src/auth/types.ts             登录和管理员公开信息类型
src/login/SharedLoginView.tsx 管理员和超管共用登录界面
src/utils/cn.ts               className 合并工具
src/utils/format.ts           日期、数字、错误码格式化
src/utils/labels.ts           状态、服务类型和 AI 字段标签格式化
src/assets/login/             登录页共享图片资源
```

## 使用规则

- 可以放共享登录、HTTP、格式化、标签映射和基础类型。
- 不放普通管理员页面。
- 不放超级管理员页面。
- 不放读者端页面。
- 不放某一端专属的 API 聚合逻辑。

普通接口默认超时较短；AI 聊天接口需要在各自应用 API 文件中显式覆盖更长超时。
