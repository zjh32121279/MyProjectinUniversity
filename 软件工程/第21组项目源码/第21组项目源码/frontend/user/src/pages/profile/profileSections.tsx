import type { ReactNode } from "react";
import { Bell, Heart, HelpCircle, MapPinned, ShieldCheck, UserRound } from "lucide-react";
import type { ProfileCenterAction, ProfileCenterSection, ReaderProfile } from "@/types/user";

export const groupIcons: Record<string, ReactNode> = {
  完善个人信息: <UserRound size={20} />,
  账号与安全: <ShieldCheck size={20} />,
  系统设置: <Bell size={20} />,
  阅读偏好: <Heart size={20} />,
  反馈与帮助: <HelpCircle size={20} />,
  关于我们: <MapPinned size={20} />,
};

const readerTypeLabels: Record<string, string> = {
  child: "儿童读者",
  teen: "青少年读者",
  adult: "成人读者",
  senior: "老年读者",
  institution: "机构读者",
};

export function display(value: unknown, fallback = "—") {
  return String(value ?? "").trim() || fallback;
}

export function readerType(profile?: ReaderProfile | null) {
  const code = display(profile?.reader_type_code, "");
  const name = display(profile?.reader_type_name, "");
  if (name && name !== code) return name;
  return readerTypeLabels[code] || name || "普通读者";
}

function profileItem(label: string, value: unknown, description?: string | null) {
  return { label, value: display(value), ...(description ? { description } : {}) };
}

function profileSection(
  key: string,
  group: string,
  title: string,
  summary: string,
  items: ReturnType<typeof profileItem>[],
  actions: ProfileCenterAction[] = [],
): ProfileCenterSection {
  return { key, group, title, summary, items, actions };
}

export function buildFallbackSections(profile?: ReaderProfile | null, borrow?: { current?: number | null; dueSoon?: number | null }, reservation?: { active?: number | null; ready?: number | null }) {
  if (!profile) return [];
  const phone = display(profile.phone_masked, "");
  const email = display(profile.email, "");
  const typeName = readerType(profile);
  const statusName = profile.status_name || profile.status || "正常";
  return [
    profileSection("basic_info", "完善个人信息", "基本信息", "读者身份、联系方式与账号状态", [
      profileItem("姓名", profile.name),
      profileItem("读者证号", profile.reader_code),
      profileItem("读者类型", typeName),
      profileItem("账号状态", statusName),
      profileItem("手机号", phone),
      profileItem("邮箱", email),
      profileItem("注册时间", display(profile.registered_at).slice(0, 10)),
    ], [{ type: "contact_form", label: "更新联系方式" }]),
    profileSection("pickup_point", "完善个人信息", "常用取书点", "预约到书后的默认取书说明", [
      profileItem("默认取书点", "服务台 / 预约保留区"),
      profileItem("待取预约", reservation?.ready ?? 0),
      profileItem("当前说明", "到书后系统会在预约记录中显示取书截止日期和副本信息"),
    ], [{ type: "navigate", label: "查看我的预约", to: "/reservations" }]),
    profileSection("identity_info", "完善个人信息", "证件信息", "读者证和借阅资格信息", [
      profileItem("读者证号", profile.reader_code),
      profileItem("信用分", profile.credit_score),
      profileItem("借阅暂停", profile.borrow_suspended ? "是" : "否"),
      profileItem("最大可借", profile.max_borrow_count),
    ]),
    profileSection("change_password", "账号与安全", "修改密码", "使用当前密码修改登录密码", [
      profileItem("登录账号", profile.reader_code),
      profileItem("凭据状态", "正常"),
      profileItem("安全建议", "定期修改密码，不要与其他网站共用密码"),
    ], [{ type: "password_form", label: "修改密码" }]),
    profileSection("bind_phone", "账号与安全", "绑定手机号", "维护本人手机号和邮箱", [
      profileItem("当前手机号", phone),
      profileItem("当前邮箱", email),
      profileItem("用途", "登录、通知和馆员联系"),
    ], [{ type: "contact_form", label: "更新联系方式" }]),
    profileSection("login_devices", "账号与安全", "登录设备管理", "最近登录记录由系统审计生成", [
      profileItem("最近登录次数", "暂无记录"),
      profileItem("当前设备", "本机浏览器"),
      profileItem("说明", "如发现异常登录，请立即修改密码"),
    ]),
    profileSection("notification_settings", "系统设置", "消息通知设置", "借阅、预约、系统通知开关", [
      profileItem("借阅到期提醒", "开"),
      profileItem("预约到书通知", "开"),
      profileItem("系统消息", "开"),
    ], [{ type: "navigate", label: "打开通知中心", to: "/notifications" }]),
    profileSection("privacy_settings", "系统设置", "隐私设置", "个人资料展示和通知隐私", [
      profileItem("联系方式展示", "仅本人账号页显示完整值"),
      profileItem("馆员可见范围", "读者服务和借阅处理所需信息"),
      profileItem("通知内容", "只展示与本人借阅、预约、公告相关消息"),
    ]),
    profileSection("general_settings", "系统设置", "通用设置", "界面和服务默认项", [
      profileItem("语言", "简体中文"),
      profileItem("日期格式", "YYYY-MM-DD"),
      profileItem("默认入口", "首页"),
    ]),
    profileSection("favorite_categories", "阅读偏好", "感兴趣的分类", "选择感兴趣的一级分类，首页推荐将优先展示这些分类的图书", [
      profileItem("已选分类", "点击编辑选择"),
    ], [{ type: "category_select", label: "编辑偏好分类" }]),
    profileSection("reading_history", "阅读偏好", "阅读历史", "查看借阅时间线与信用记录", [
      profileItem("历史借阅", "—"),
      profileItem("当前借阅", borrow?.current ?? 0),
      profileItem("到期提醒", borrow?.dueSoon ?? 0),
    ], [{ type: "borrow_history", label: "查看借阅历史" }]),
    profileSection("recommendation_settings", "阅读偏好", "推荐设置", "选择首页推荐策略：热门图书、偏好分类，或两者混合", [
      profileItem("当前策略", "热门馆藏 + 偏好分类"),
    ], [{ type: "recommendation_select", label: "修改推荐策略" }]),
    profileSection("feedback", "反馈与帮助", "意见反馈", "提交问题或建议给馆员", [
      profileItem("反馈对象", "图书馆"),
      profileItem("处理说明", "提交后进入馆员处理流程"),
    ], [{ type: "feedback_form", label: "提交反馈" }]),
    profileSection("faq", "反馈与帮助", "常见问题", "读者端常用操作说明", [
      profileItem("如何找书", "在找书页搜索书名、作者或分类，点击定位取书"),
      profileItem("何时预约", "没有可借副本时可预约，系统会排队或保留副本"),
      profileItem("如何续借", "在我的借阅中点击可续借记录的续借按钮"),
    ]),
    profileSection("contact_service", "反馈与帮助", "联系客服", "馆内服务联系方式", [
      profileItem("服务电话", "请以图书馆公示为准"),
      profileItem("服务邮箱", "请以图书馆公示为准"),
      profileItem("开放时间", "请以图书馆公示为准"),
    ]),
    profileSection("about_bookflow", "关于我们", "关于 BookFlow", "BookFlow Core 图书馆读者服务系统", [
      profileItem("系统架构", "FastAPI + React + SQLite，前后端分离，支持 Windows / Linux 部署"),
      profileItem("服务对象", "公共图书馆、高校图书馆、社区图书馆读者及馆员"),
      profileItem("核心能力", "在线书目检索、馆内平面地图与书架定位、借阅续借、预约排队、到期与逾期自动提醒、AI 辅助编目与任务调度"),
      profileItem("读者端功能", "首页概览、找书与地图定位、我的借阅、我的预约、通知中心、个人中心与信用分"),
      profileItem("数据来源", "馆藏书目由后台导入或馆员编目维护，流通策略与借阅规则由馆员在普管端配置"),
    ]),
    profileSection("terms", "关于我们", "服务条款", "使用本系统即视为已阅读并同意以下条款", [
      profileItem("读者类型", `本馆按读者类型（儿童、青少年、成人、老年、机构）分别设置最大可借册数、借阅天数与续借次数，具体数值以普管端"流通规则"为准`),
      profileItem("热门与冷门", `近 90 天借阅或预约达到阈值的图书标记为"热门"，缩短借期；近 365 天低借阅且长期未流通的标记为"冷门"，可正常借阅`),
      profileItem("预约取书", `无可用副本时读者可提交预约，到书后系统发送通知，保留取书期限以流通策略中的预约保留天数为准，超时未取自动取消`),
      profileItem("逾期暂停", "任一借阅逾期未还期间，账号自动暂停借阅权限，归还所有逾期图书后即时恢复"),
      profileItem("信用分", "系统依据借阅归还及时性、逾期次数与严重程度自动计算读者信用分，信用分过低可能影响借阅额度"),
      profileItem("行为规范", "读者须使用本人真实身份注册登录，妥善保管账号密码，不得转借、转让或利用本系统从事违法违规活动"),
      profileItem("服务变更", "系统升级维护可能短暂影响访问，流通规则变更将在通知中心提前公告，重大调整须经馆员审批后生效"),
    ]),
    profileSection("privacy_policy", "关于我们", "隐私政策", "依据《个人信息保护法》说明信息处理规则", [
      profileItem("收集内容", "注册与登录所需的姓名与读者证号，借阅与预约产生的业务记录，通知投递所需的联系方式（手机号或邮箱）"),
      profileItem("手机号保护", "完整手机号经哈希处理后存储，读者端仅展示掩码（如 138****1234），馆员端经授权方可查看脱敏值"),
      profileItem("数据存储", "所有数据存储于馆内或指定服务器，借阅与预约记录保留至还书或取消后不少于 2 年，日志定期归档"),
      profileItem("安全措施", "登录密码加密存储（SHA-256 + 盐值），API 传输强制 HTTPS，数据库访问基于角色权限控制，关键操作写入审计日志"),
      profileItem("第三方接入", "本系统未集成第三方统计或广告 SDK，不向馆外机构共享、转让或公开披露读者个人信息"),
      profileItem("用户权利", "读者可在本页面更新联系方式与通知偏好，可申请查询、更正或删除个人信息，可随时注销账号"),
      profileItem("政策更新", "隐私政策如有重大变更，将在系统通知中心以消息形式推送，并在登录页公示更新日期"),
    ]),
  ];
}
