import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { GlassCard } from "@/components/common/GlassCard";
import type { ProfileCenterSection } from "@/types/user";

export function ProfilePanel({ icon, title, sections, activeKey, onOpen, wide = false }: { icon: ReactNode; title: string; sections: ProfileCenterSection[]; activeKey: string; onOpen: (section: ProfileCenterSection) => void; wide?: boolean }) {
  return (
    <GlassCard className={wide ? "profile-panel profile-panel--wide" : "profile-panel"}>
      <div className="profile-panel__title"><span>{icon}</span><h2>{title}</h2></div>
      <div className="profile-panel__items">
        {sections.map((section) => <ProfileEntry key={section.key} section={section} active={section.key === activeKey} onOpen={onOpen} />)}
      </div>
    </GlassCard>
  );
}

function ProfileEntry({ section, active, onOpen }: { section: ProfileCenterSection; active: boolean; onOpen: (section: ProfileCenterSection) => void }) {
  return (
    <button className={active ? "profile-entry profile-entry--active" : "profile-entry"} type="button" onClick={() => onOpen(section)}>
      <span className="profile-entry__text">
        <strong>{section.title}</strong>
        <em>{section.summary}</em>
      </span>
      <ChevronRight size={18} />
    </button>
  );
}
