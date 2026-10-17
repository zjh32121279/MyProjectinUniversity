import { BookMarked } from "lucide-react";

type CategoryPillProps = {
  label: string;
  code?: string | null;
  onClick?: () => void;
};

export function CategoryPill({ label, code, onClick }: CategoryPillProps) {
  return (
    <button className="category-pill" type="button" onClick={onClick}>
      <BookMarked size={18} />
      <span>{code ? `${code} ` : ""}{label}</span>
    </button>
  );
}
