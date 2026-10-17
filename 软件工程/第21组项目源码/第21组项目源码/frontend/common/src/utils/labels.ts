type DisplayRecord = Record<string, unknown>;

function valueText(value: unknown) {
  return String(value ?? "").trim();
}

function hasChinese(value: string) {
  return /[\u4e00-\u9fff]/.test(value);
}

function lookup(value: unknown, labels: Record<string, string>, fallback = "-") {
  const raw = valueText(value);
  if (!raw) return fallback;
  const normalized = raw.toLowerCase();
  return labels[raw] ?? labels[normalized] ?? (hasChinese(raw) ? raw : fallback);
}

const technicalTokenLabels: Record<string, string> = {
  ai: "AI",
  kernel: "内核",
  reader: "读者",
  readers: "读者",
  admin: "管理员",
  super: "超级",
  system: "系统",
  task: "任务",
  tasks: "任务",
  work: "工作",
  create: "创建",
  created: "已创建",
  update: "更新",
  updated: "已更新",
  batch: "批量",
  mark: "标记",
  low: "低",
  high: "高",
  medium: "中",
  critical: "严重",
  risk: "风险",
  risks: "风险",
  warning: "预警",
  warnings: "预警",
  active: "活跃",
  get: "查询",
  search: "检索",
  dashboard: "看板",
  analytics: "分析",
  efficiency: "效率",
  collection: "馆藏",
  health: "健康",
  circulation: "流通",
  loan: "借阅",
  loans: "借阅",
  borrow: "借书",
  borrowed: "已借出",
  return: "还书",
  returned: "已归还",
  renew: "续借",
  renewal: "续借",
  reservation: "预约",
  reservations: "预约",
  notification: "通知",
  notifications: "通知",
  overdue: "逾期",
  overdues: "逾期",
  hot: "热门",
  cold: "冷门",
  books: "图书",
  book: "图书",
  copy: "副本",
  copies: "副本",
  status: "状态",
  rule: "规则",
  rules: "规则",
  summary: "汇总",
  detail: "详情",
  activity: "活动",
  credit: "信用",
  suspend: "暂停",
  restore: "恢复",
  assign: "指派",
  resolve: "完成",
  complete: "完成",
  failed: "失败",
  failure: "失败",
  handoff: "转人工",
  human: "人工",
  confirmation: "确认",
  authorization: "授权",
  allowed: "允许",
  forbidden: "禁止",
  disabled: "停用",
  enabled: "启用",
  plan: "计划",
  sop: "流程",
  patrol: "巡检",
  event: "事件",
  events: "事件",
  security: "安全",
  source: "来源",
  queue: "队列",
  default: "默认",
};

export function formatTechnicalCode(value: unknown, fallback = "系统项目") {
  const raw = valueText(value);
  if (!raw) return "-";
  if (hasChinese(raw)) return raw;
  const tokens = raw.toLowerCase().split(/[._\s-]+/).filter(Boolean);
  if (!tokens.length) return fallback;
  const translated = tokens.map((token) => technicalTokenLabels[token]);
  if (translated.every(Boolean)) return translated.join("");
  return fallback;
}

export const statusLabels: Record<string, string> = {
  active: "正常",
  inactive: "停用",
  enabled: "启用",
  disabled: "停用",
  pending: "待处理",
  waiting: "等待中",
  waiting_authorization: "等待授权",
  needs_clarification: "需要补充信息",
  waiting_human: "待人工介入",
  admin_processing: "人工处理中",
  ai_processing: "AI处理中",
  ai_claimed: "AI处理中",
  ai_completed: "AI已完成",
  admin_claimed: "人工已接管",
  overridden_by_admin: "人工已接管",
  claimed: "已接管",
  running: "运行中",
  ready: "待馆员确认",
  ready_for_pickup: "待取书",
  completed: "已完成",
  resolved: "已完成",
  done: "已完成",
  success: "成功",
  executed: "已执行",
  approved: "已批准",
  fulfilled: "已履约",
  failed: "失败",
  error: "异常",
  rejected: "已驳回",
  rejected_by_super_admin: "超管已驳回",
  paused: "暂缓",
  deferred: "暂缓",
  cancelled: "已取消",
  canceled: "已取消",
  expired: "已过期",
  unread: "未读",
  read: "已读",
  draft: "草稿",
  sent: "已发送",
  available: "在馆可借",
  borrowed: "已借出",
  returned: "已归还",
  reserved: "预约保留",
  overdue: "逾期",
  maintenance: "维护中",
  unavailable: "暂不可借",
};

export function formatStatus(value: unknown) {
  return lookup(value, statusLabels);
}

export function formatPriority(priority: unknown) {
  const labels: Record<string, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    normal: "普通",
    low: "低",
  };
  return lookup(priority, labels);
}

export function formatRiskLevel(value: unknown) {
  const labels: Record<string, string> = {
    critical: "严重风险",
    high: "高风险",
    medium: "中风险",
    normal: "普通风险",
    low: "低风险",
    forbidden: "禁止执行",
  };
  return lookup(value, labels, "待确认");
}

export function formatQueueName(value: unknown) {
  const labels: Record<string, string> = {
    default: "默认队列",
    reader_ops: "读者流通队列",
    collection_ops: "馆藏处理队列",
    catalog: "编目处理队列",
    shelving: "排架处理队列",
    notification: "通知处理队列",
    human_review: "人工复核队列",
    exception: "异常处理队列",
    risk: "风险处理队列",
    patrol: "巡检队列",
  };
  return lookup(value, labels, "默认队列");
}

export function formatTaskGroup(value: unknown) {
  const labels: Record<string, string> = {
    borrow: "借还流通",
    reader_ops: "读者流通",
    circulation: "流通业务",
    exception: "异常处理",
    shelving: "排架管理",
    catalog: "馆藏编目",
    reservation: "预约业务",
    review: "人工复核",
    ai_review: "AI复核",
    risk: "风险治理",
    notification: "通知任务",
    other: "其他任务",
    unknown: "未分类任务",
  };
  return lookup(value, labels, "未分类任务");
}

export function formatSourceType(source: unknown) {
  const labels: Record<string, string> = {
    ai: "BookFlow AI",
    ai_admin: "BookFlow AI",
    ai_review: "AI复核",
    reader_ai: "读者AI",
    reader_event: "读者请求",
    system: "系统",
    analytics: "数据巡检",
    admin: "普通管理员",
    super_admin: "超级管理员",
    reader: "读者",
    overdue: "逾期业务",
    reservation: "预约业务",
    shelving: "排架业务",
    catalog: "馆藏业务",
    rule: "规则引擎",
    rule_engine: "规则引擎",
    risk: "风险中心",
    security: "安全治理",
    circulation: "流通业务",
    loan: "借阅业务",
    renew: "续借业务",
    patrol: "AI巡检",
    notification: "通知业务",
  };
  return lookup(source, labels, "其他来源");
}

export function formatHandlerType(value: unknown) {
  const labels: Record<string, string> = {
    ai: "AI自动处理",
    admin: "人工处理",
    mixed: "人机协同",
    system: "系统处理",
    unclaimed: "未接管",
  };
  return lookup(value, labels, "未分配");
}

export function formatServiceType(value: unknown) {
  const labels: Record<string, string> = {
    borrow: "借书",
    return: "还书",
    reservation: "预约",
    renew: "续借",
  };
  return lookup(value, labels, "流通服务");
}

export function formatDataFieldLabel(value: unknown) {
  const labels: Record<string, string> = {
    id: "ID",
    task_code: "任务编号",
    request_code: "请求码",
    voucher_code: "凭证码",
    reader_code: "读者编号",
    reader_id: "读者ID",
    reader_name: "读者姓名",
    book_code: "图书编号",
    book_id: "图书ID",
    book_title: "书名",
    copy_code: "副本编号",
    copy_id: "副本ID",
    copy_status: "副本状态",
    loan_code: "借阅编号",
    loan_id: "借阅记录ID",
    reservation_code: "预约编号",
    reservation_id: "预约ID",
    renewal_id: "续借记录ID",
    notification_id: "通知ID",
    status: "状态",
    request_type: "请求类型",
    due_at: "应还日期",
    new_due_at: "新应还日期",
    returned_at: "归还时间",
    expires_at: "到期时间",
    created_at: "创建时间",
    updated_at: "更新时间",
    title: "标题",
    content: "内容",
    reason: "原因",
    result: "结果",
    risk_level: "风险等级",
    priority: "优先级",
    queue_name: "队列",
    source_type: "来源",
    handler_type: "执行方",
    tool_name: "工具",
    action: "动作",
    next_action: "后续动作",
    sop_id: "流程",
  };
  return lookup(value, labels, "数据项");
}

export function formatDataFieldValue(key: unknown, value: unknown) {
  const field = valueText(key).toLowerCase();
  if (!valueText(value)) return "-";
  if (field.includes("status") || field.includes("状态")) return formatStatus(value);
  if (field === "copy_status") return formatStatus(value);
  if (field.includes("risk") || field.includes("风险")) return formatRiskLevel(value);
  if (field.includes("priority") || field.includes("优先级")) return formatPriority(value);
  if (field.includes("queue") || field.includes("队列")) return formatQueueName(value);
  if (field.includes("source") || field.includes("来源")) return formatSourceType(value);
  if (field.includes("handler") || field.includes("执行方")) return formatHandlerType(value);
  if (field.includes("tool") || field.includes("工具")) return formatAIToolName(value);
  if (field.includes("action") || field.includes("动作")) return formatAIAction(value);
  if (field.includes("reason") || field.includes("原因")) return formatAIReason(value);
  if (field.includes("request_type") || field.includes("请求类型")) return formatServiceType(value);
  return valueText(value) || "-";
}

const aiToolLabels: Record<string, string> = {
  ai_get_hot_books: "分析热门图书",
  ai_get_cold_books: "分析冷门图书",
  ai_search_books: "检索馆藏图书",
  ai_update_copy_status: "调整副本状态",
  ai_borrow_copy: "办理借书",
  ai_return_copy: "办理还书",
  ai_renew_borrow: "办理续借",
  ai_cancel_reservation: "取消预约",
  ai_create_reservation: "创建预约",
  ai_fulfill_reservation: "履约预约",
  ai_scan_overdues: "扫描逾期借阅",
  ai_get_loans: "查询借阅记录",
  ai_get_overdue_cases: "查询逾期记录",
  ai_get_reservations: "查询预约记录",
  ai_reader_create_borrow_request: "读者借书申请",
  ai_reader_create_return_request: "读者还书申请",
  ai_reader_create_reservation: "读者预约申请",
  ai_reader_renew_borrow: "读者续借申请",
  ai_create_notification: "创建通知",
  ai_batch_create_notifications: "批量创建通知",
  ai_send_notification: "发送通知",
  ai_create_task_notifications: "创建任务通知",
  ai_get_readers: "查询读者",
  ai_get_reader_activity: "查询读者活动",
  ai_adjust_reader_credit: "调整读者信用",
  ai_suspend_reader: "暂停读者借阅资格",
  ai_restore_reader: "恢复读者借阅资格",
  ai_create_work_task: "创建馆务任务",
  ai_get_tasks: "查询馆务任务",
  ai_assign_task_to_admin: "指派任务给管理员",
  ai_resolve_work_task: "完成馆务任务",
  ai_batch_create_tasks: "批量创建馆务任务",
  ai_batch_mark_low_risk_tasks: "批量标记低风险任务",
  ai_get_active_risks: "查询活跃风险",
  ai_get_risk_warnings: "查询风险预警",
  ai_get_dashboard: "查询运营看板",
  ai_get_collection_health: "分析馆藏健康",
  ai_get_circulation_analytics: "分析流通数据",
  ai_get_reader_analytics: "分析读者数据",
  ai_get_risk_analytics: "分析风险数据",
  ai_get_efficiency: "分析AI效率",
  ai_get_overdue_summary: "汇总逾期情况",
  ai_get_notification_summary: "汇总通知情况",
  ai_get_task_summary: "汇总任务情况",
  ai_get_rule_summary: "汇总规则情况",
  ai_get_reader_detail: "查询读者详情",
  ai_get_reader_borrow_summary: "查询读者借阅汇总",
  ai_get_dashboard_explanation: "解读运营看板",
  ai_get_operational_brief: "生成运营简报",
  ai_get_admin_security_summary: "汇总管理员安全",
  ai_get_admin_events: "查询管理员事件",
  ai_get_admins: "查询管理员",
  ai_kernel_task_agent: "AI任务处理",
  ai_kernel_process_task: "AI内核处理任务",
  reader_ai_chat: "读者AI对话",
};

export function formatAIToolName(value: unknown) {
  const raw = valueText(value);
  if (!raw) return "AI步骤";
  const normalized = raw.toLowerCase();
  if (hasChinese(raw)) return raw;
  if (normalized.startsWith("notification.create")) return "创建通知";
  if (normalized.startsWith("catalog.status")) return "调整馆藏状态";
  return aiToolLabels[raw] ?? aiToolLabels[normalized] ?? formatTechnicalCode(raw, "AI工具");
}

const aiActionLabels: Record<string, string> = {
  autonomous_decision: "自主判断",
  business_event: "业务事件处理",
  reader_ai_chat: "读者AI对话",
  reader_request: "读者请求处理",
  reader_service_request: "读者流通请求",
  execute_tool: "执行工具",
  execute_plan: "执行计划",
  split_tasks: "拆分任务包",
  dynamic_agent_loop: "动态执行循环",
  execute_followup: "执行后续步骤",
  followup: "后续处理",
  complete: "完成处理",
  completed: "已完成",
  handoff: "转人工处理",
  human_review: "人工复核",
  waiting_authorization: "等待授权",
  patrol: "AI巡检",
  daily_patrol: "日常巡检",
  overdue_patrol: "逾期巡检",
  sop_overdue_triage: "逾期任务分诊",
  sop_reader_request: "读者请求分诊",
  risk_warning_triage: "风险预警分诊",
  create_task: "创建任务",
  admin_takeover_ai_task: "人工接管AI任务",
  admin_claim_task: "人工接管任务",
  admin_resolve_task: "人工完成任务",
  ai_start_task: "AI开始处理",
  ai_complete_task: "AI完成任务",
  ai_fail_task: "AI处理失败",
  ai_kernel_failure_handoff: "AI异常转人工",
  ai_kernel_failure_retry: "AI失败后重试",
  ai_kernel_interrupt_task: "AI任务被中断",
  ai_kernel_release_task: "AI释放任务",
  task_create: "任务创建",
  "task.create": "任务创建",
  loan_check_overdue: "逾期借阅检查",
  "loan.check_overdue": "逾期借阅检查",
  reservation_check: "预约校验",
  "reservation.check": "预约校验",
  catalog_search: "馆藏检索",
  "catalog.search": "馆藏检索",
  risk_create: "风险预警创建",
  "risk.create": "风险预警创建",
  ai_request_copy_status_change: "申请调整副本状态",
  ai_request_rule_change: "申请调整规则",
  ai_request_reader_credit_adjust: "申请调整读者信用",
  ai_request_reader_suspend: "申请暂停读者借阅资格",
  ai_request_reader_restore: "申请恢复读者借阅资格",
};

export function formatAIAction(value: unknown) {
  const raw = valueText(value);
  if (!raw) return "自主判断";
  if (hasChinese(raw)) return raw;
  const normalized = raw.toLowerCase();
  return aiActionLabels[raw] ?? aiActionLabels[normalized] ?? aiToolLabels[raw] ?? aiToolLabels[normalized] ?? formatTechnicalCode(raw, "AI动作");
}

const aiReasonLabels: Record<string, string> = {
  super_authorization_required: "需要超级管理员授权",
  interactive_admin_operator_allowed: "人工交互代办已允许",
  task_requires_human_confirmation: "任务要求人工确认",
  human_confirmation_required: "需要人工确认",
  needs_clarification: "需要补充信息",
  missing_required_fields: "缺少必要信息",
  missing_required_book_identifier: "缺少图书标识",
  missing_required_loan_or_copy_identifier: "缺少借阅或副本标识",
  tool_disabled: "工具已停用",
  tool_forbidden: "工具禁止使用",
  policy_allows_execution: "策略允许执行",
  low_risk_administrative_task: "低风险任务可自动完成",
  missing_executable_tool_context: "缺少可执行上下文",
  explicit_tool_sequence: "按明确工具序列执行",
  multi_intent_task_package: "多项意图已拆分为任务包",
  dynamic_agent_loop: "动态执行循环",
  dynamic_loop_max_iterations: "动态执行达到上限",
  requires_human_confirmation: "需要人工确认",
  reader_ai_llm_plan: "读者AI已完成规划",
  ai_fail_task: "AI处理失败",
  ai_suspend: "AI建议暂停借阅资格",
  ai_restore: "AI建议恢复借阅资格",
  ai_adjust: "AI建议调整信用",
  admin_takeover: "人工接管",
  admin_claim_task: "管理员接管任务",
  admin_resolve_task: "管理员完成任务",
  manual_kernel_interrupt: "人工中断AI任务",
  manual_release: "人工释放任务",
  resolved_by_ai_tool: "AI工具已完成处理",
  rejected: "已驳回",
  super_admin_rejected: "超级管理员已驳回",
  super_admin_confirmed: "超级管理员已确认",
  deferred_by_super_admin: "超级管理员暂缓",
};

export function formatAIReason(value: unknown) {
  const raw = valueText(value);
  if (!raw) return "-";
  if (hasChinese(raw)) return raw;
  const normalized = raw.toLowerCase();
  return aiReasonLabels[raw] ?? aiReasonLabels[normalized] ?? statusLabels[raw] ?? statusLabels[normalized] ?? formatTechnicalCode(raw, "系统原因");
}

export function formatRequestedAction(value: unknown) {
  const raw = valueText(value);
  if (!raw) return "待确认事项";
  if (hasChinese(raw)) return raw;
  const normalized = raw.toLowerCase();
  return aiActionLabels[raw] ?? aiActionLabels[normalized] ?? aiToolLabels[raw] ?? aiToolLabels[normalized] ?? formatTechnicalCode(raw, "待确认事项");
}

export function formatAIName(value: unknown) {
  const raw = valueText(value);
  if (!raw) return "未知AI项目";
  if (hasChinese(raw)) return raw;
  const normalized = raw.toLowerCase();
  const sourceLabel = formatSourceType(raw);
  return statusLabels[raw]
    ?? statusLabels[normalized]
    ?? aiToolLabels[raw]
    ?? aiToolLabels[normalized]
    ?? aiActionLabels[raw]
    ?? aiActionLabels[normalized]
    ?? aiReasonLabels[raw]
    ?? aiReasonLabels[normalized]
    ?? (sourceLabel === "其他来源" ? formatTechnicalCode(raw, "未知AI项目") : sourceLabel);
}

const taskTitleLabels: Record<string, string> = {
  "Reader AI request": "读者AI请求",
  "AI patrol task: daily": "AI日常巡检任务",
  "AI patrol task: overdue": "AI逾期巡检任务",
  "Borrow completed": "借书已完成",
  "Return completed": "还书已完成",
  "Renewal completed": "续借已完成",
  "Reservation created": "预约已创建",
  "Reservation fulfilled": "预约已履约",
  "Reservation cancelled": "预约已取消",
};

export function formatTaskTitle(task: DisplayRecord | unknown) {
  const row = typeof task === "object" && task ? (task as DisplayRecord) : { title: task };
  const title = valueText(row.title);
  if (title) {
    if (hasChinese(title)) return title;
    if (taskTitleLabels[title]) return taskTitleLabels[title];
  }
  const source = valueText(row.source_type);
  const group = valueText(row.task_group);
  const type = valueText(row.task_type);
  if (source === "ai_admin" || source === "ai" || source === "reader_ai" || source === "reader_event") return "AI待处理任务";
  if (source === "risk" || source === "security" || group === "risk" || group === "exception") return "风险/异常任务";
  if (group === "reservation" || source === "reservation") return "预约处理任务";
  if (group === "notification" || source === "notification") return "通知处理任务";
  if (group === "catalog" || source === "catalog" || type === "catalog") return "馆藏处理任务";
  if (group === "shelving" || source === "shelving" || type === "shelving") return "排架处理任务";
  if (group === "borrow" || source === "circulation" || source === "loan" || source === "renew") return "流通处理任务";
  if (valueText(row.priority) === "urgent" || valueText(row.priority) === "high") return "高优先级运营任务";
  return "系统生成任务";
}
