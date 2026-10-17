import * as Dialog from "@radix-ui/react-dialog";
import { ActionButton } from "@/components/ui/ActionButton";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  onConfirm: () => void;
};

export function ConfirmDialog({ open, onOpenChange, title, description, onConfirm }: ConfirmDialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-[#071334]/35" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[420px] -translate-x-1/2 -translate-y-1/2 rounded-[18px] bg-white p-6 shadow-[0_30px_80px_rgba(15,23,42,0.2)]">
          <Dialog.Title className="text-lg font-bold text-[#071334]">{title}</Dialog.Title>
          <Dialog.Description className="mt-3 text-sm leading-6 text-[var(--bf-text-secondary)]">{description}</Dialog.Description>
          <div className="mt-6 flex justify-end gap-3">
            <Dialog.Close asChild>
              <ActionButton variant="secondary">取消</ActionButton>
            </Dialog.Close>
            <ActionButton
              onClick={() => {
                onConfirm();
                onOpenChange(false);
              }}
            >
              确认
            </ActionButton>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
