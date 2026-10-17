import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  ArrowPathIcon,
  ArrowRightIcon,
  BellIcon,
  BookOpenIcon,
  CalendarDaysIcon,
  ChartBarIcon,
  CheckIcon,
  ChevronDownIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  CpuChipIcon,
  DocumentTextIcon,
  EyeIcon,
  FunnelIcon,
  HomeIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PaperAirplaneIcon,
  PencilSquareIcon,
  PhotoIcon,
  PlusIcon,
  QueueListIcon,
  SparklesIcon,
  TrashIcon,
  UserCircleIcon,
  UsersIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";
import type { ComponentType, SVGProps } from "react";
import { cn } from "@/utils/cn";

const iconMap = {
  home: HomeIcon,
  ai: CpuChipIcon,
  sparkles: SparklesIcon,
  tasks: ClipboardDocumentListIcon,
  catalog: BookOpenIcon,
  borrowing: CalendarDaysIcon,
  calendar: CalendarDaysIcon,
  readers: UsersIcon,
  notifications: BellIcon,
  data: ChartBarIcon,
  settings: Cog6ToothIcon,
  search: MagnifyingGlassIcon,
  bell: BellIcon,
  user: UserCircleIcon,
  lock: LockClosedIcon,
  down: ChevronDownIcon,
  filter: FunnelIcon,
  eye: EyeIcon,
  edit: PencilSquareIcon,
  delete: TrashIcon,
  export: ArrowDownTrayIcon,
  send: PaperAirplaneIcon,
  right: ArrowRightIcon,
  left: ArrowLeftIcon,
  refresh: ArrowPathIcon,
  plus: PlusIcon,
  check: CheckIcon,
  close: XMarkIcon,
  image: PhotoIcon,
  document: DocumentTextIcon,
  queue: QueueListIcon,
} satisfies Record<string, ComponentType<SVGProps<SVGSVGElement>>>;

export type AppIconName = keyof typeof iconMap;

type AppIconProps = {
  name: AppIconName;
  size?: number;
  className?: string;
};

export function AppIcon({ name, size = 20, className }: AppIconProps) {
  const Icon = iconMap[name];
  return <Icon className={cn("shrink-0", className)} style={{ width: size, height: size }} aria-hidden="true" />;
}
