import { BorrowingModeCard, BorrowingStats } from "@/components/borrowing/BorrowingShared";
import rhythm from "@/styles/AdminRhythm.module.css";

const modes = [
  { title: "办理借书", description: "为读者办理图书借出，自动校验信用、借阅上限和副本状态。", icon: "borrow", tone: "blue" as const, to: "/admin/borrowing/borrow" },
  { title: "办理还书", description: "扫描或输入副本编号，同步更新借阅记录和馆藏状态。", icon: "return", tone: "green" as const, to: "/admin/borrowing/return" },
  { title: "办理续借", description: "围绕借阅记录校验续借规则，并生成新的应还日期。", icon: "overdue", tone: "orange" as const, to: "/admin/borrowing/renew" },
  { title: "预约处理", description: "创建预约、查看预约保留，并完成取消或履约处理。", icon: "reservation", tone: "purple" as const, to: "/admin/borrowing/reservation" },
];

export function BorrowingHomePage() {
  return (
    <div className={rhythm.page}>
      <div className="h-[104px] shrink-0">
        <BorrowingStats />
      </div>
      <div className={rhythm.borrowingHomeMain}>
        <div className="h-12 shrink-0">
          <h2 className="text-[22px] font-bold text-[#071334]">快捷办理</h2>
          <p className="text-sm text-[var(--bf-text-secondary)]">选择一个业务入口进入独立办理界面。</p>
        </div>
        <div className="mt-6 grid min-h-0 flex-1 grid-cols-4 gap-[22px]">
          {modes.map((mode) => (
            <BorrowingModeCard key={mode.to} {...mode} />
          ))}
        </div>
      </div>
    </div>
  );
}
