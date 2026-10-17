import * as Dialog from "@radix-ui/react-dialog";
import type { PropsWithChildren, ReactNode } from "react";
import { ActionButton } from "@/components/ui/ActionButton";
import { cn } from "@/utils/cn";

type FormDialogProps = PropsWithChildren<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  trigger?: ReactNode;
  className?: string;
}>;

export function FormDialog({ open, onOpenChange, title, trigger, className, children }: FormDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger ? <Dialog.Trigger asChild>{trigger}</Dialog.Trigger> : null}
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#071334]/35" />
        <Dialog.Content className={cn("fixed left-1/2 top-1/2 z-50 w-[580px] max-w-[95vw] -translate-x-1/2 -translate-y-1/2 rounded-[20px] border border-[#e8eef6] bg-white px-8 py-7 shadow-[0_30px_80px_rgba(15,23,42,0.18)]", className)}>
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-[20px] font-black text-[#071334]">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <ActionButton variant="ghost" icon="close" />
            </Dialog.Close>
          </div>
          <div className="mt-6 max-h-[65vh] overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
