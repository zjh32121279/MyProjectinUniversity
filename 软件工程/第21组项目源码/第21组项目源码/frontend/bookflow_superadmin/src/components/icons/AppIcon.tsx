import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  BellIcon,
  ChartBarIcon,
  CheckIcon,
  ChevronDownIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  CpuChipIcon,
  DocumentTextIcon,
  HomeIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  UserCircleIcon,
  UsersIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import type { ComponentType, SVGProps } from "react";

const iconMap = {
  home: HomeIcon,
  readers: UsersIcon,
  ai: CpuChipIcon,
  lock: LockClosedIcon,
  settings: Cog6ToothIcon,
  left: ArrowLeftIcon,
  right: ArrowRightIcon,
  bell: BellIcon,
  user: UserCircleIcon,
  down: ChevronDownIcon,
  document: DocumentTextIcon,
  export: ArrowDownTrayIcon,
  check: CheckIcon,
  close: XMarkIcon,
  search: MagnifyingGlassIcon,
  plus: PlusIcon,
  tasks: ClipboardDocumentListIcon,
  data: ChartBarIcon,
} satisfies Record<string, ComponentType<SVGProps<SVGSVGElement>>>;

export type AppIconName = keyof typeof iconMap;

type AppIconProps = {
  name: AppIconName;
  size?: number;
  className?: string;
};

export function AppIcon({ name, size = 20, className }: AppIconProps) {
  const Icon = iconMap[name];
  return <Icon className={className} style={{ width: size, height: size, flexShrink: 0 }} aria-hidden="true" />;
}
