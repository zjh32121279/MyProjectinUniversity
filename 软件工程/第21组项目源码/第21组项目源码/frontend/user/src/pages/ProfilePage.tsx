import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { HelpCircle, ShieldCheck, UserRound } from "lucide-react";
import { FlowFeedback } from "@/components/common/FlowFeedback";
import { GlassCard } from "@/components/common/GlassCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useBorrowSummary } from "@/hooks/useBorrowList";
import { useProfileCenter, useReaderProfile } from "@/hooks/useReaderProfile";
import { useReservationSummary } from "@/hooks/useReservationList";
import { readerApi } from "@/services/readerApi";
import type { ProfileCenterAction, ProfileCenterSection } from "@/types/user";
import { ProfileDetailDialog } from "./profile/ProfileDetailDialog";
import { BorrowHistoryDialog, CategorySelectDialog, RecommendationSelectDialog } from "./profile/ProfilePreferenceDialogs";
import { ProfilePanel } from "./profile/ProfilePanel";
import { buildFallbackSections, display, groupIcons, readerType } from "./profile/profileSections";

export function ProfilePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profile = useReaderProfile();
  const center = useProfileCenter();
  const borrow = useBorrowSummary();
  const reservation = useReservationSummary();
  const data = center.data?.profile ?? profile.data;
  const fallbackSections = useMemo(() => buildFallbackSections(data, borrow.data, reservation.data), [borrow.data, data, reservation.data]);
  const sections = center.data?.sections?.length ? center.data.sections : fallbackSections;
  const [activeSection, setActiveSection] = useState<ProfileCenterSection | null>(null);
  const [message, setMessage] = useState("");
  const [showCategorySelect, setShowCategorySelect] = useState(false);
  const [showRecommendationSelect, setShowRecommendationSelect] = useState(false);
  const [showBorrowHistory, setShowBorrowHistory] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const avatarMutation = useMutation({
    mutationFn: readerApi.uploadAvatar,
    onMutate: () => setUploadingAvatar(true),
    onSettled: () => setUploadingAvatar(false),
    onSuccess: async () => {
      setMessage("头像已更新。");
      await refreshProfile();
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "头像上传失败"),
  });

  function handleAvatarClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    avatarMutation.mutate(file);
    event.target.value = "";
  }

  useEffect(() => {
    if (activeSection && !sections.some((item) => item.key === activeSection.key)) {
      setActiveSection(null);
    }
  }, [activeSection, sections]);

  const grouped = useMemo(() => {
    const map = new Map<string, ProfileCenterSection[]>();
    sections.forEach((section) => {
      map.set(section.group, [...(map.get(section.group) ?? []), section]);
    });
    return Array.from(map.entries());
  }, [sections]);

  const refreshProfile = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reader-profile"] }),
      queryClient.invalidateQueries({ queryKey: ["profile-center"] }),
    ]);
  };

  const contactMutation = useMutation({
    mutationFn: readerApi.updateContact,
    onSuccess: async () => {
      setMessage("联系方式已更新。");
      await refreshProfile();
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : "联系方式更新失败"),
  });

  const passwordMutation = useMutation({
    mutationFn: readerApi.changePassword,
    onSuccess: () => setMessage("密码已修改。"),
    onError: (error) => setMessage(error instanceof Error ? error.message : "密码修改失败"),
  });

  const feedbackMutation = useMutation({
    mutationFn: readerApi.submitFeedback,
    onSuccess: () => setMessage("反馈已提交。"),
    onError: (error) => setMessage(error instanceof Error ? error.message : "反馈提交失败"),
  });

  function runAction(action: ProfileCenterAction) {
    if (action.type === "navigate" && action.to) {
      setActiveSection(null);
      navigate(action.to);
    }
    if (action.type === "category_select") {
      setActiveSection(null);
      setShowCategorySelect(true);
    }
    if (action.type === "recommendation_select") {
      setActiveSection(null);
      setShowRecommendationSelect(true);
    }
    if (action.type === "borrow_history") {
      setActiveSection(null);
      setShowBorrowHistory(true);
    }
  }

  return (
    <main className="user-page profile-page profile-page--refined">
      <GlassCard className="profile-hero-card profile-hero-card--refined">
        <button
          type="button"
          className="profile-avatar profile-avatar--large"
          onClick={handleAvatarClick}
          disabled={uploadingAvatar}
          title="点击上传头像"
          aria-label="上传头像"
          style={{
            cursor: "pointer",
            border: "none",
            padding: 0,
            opacity: uploadingAvatar ? 0.5 : 1,
            transition: "opacity 0.2s",
          }}
        >
          {data?.avatar_url ? <img src={data.avatar_url} alt="" /> : <UserRound size={62} />}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
        <div className="profile-main profile-main--refined">
          <div className="profile-name-row">
            <h1>{data?.name || "—"}</h1>
            <span>{readerType(data)}</span>
          </div>
          <dl>
            <div><dt>读者证号</dt><dd>{data?.reader_code || "—"}</dd></div>
            <div><dt>读者类型</dt><dd>{readerType(data)}</dd></div>
            <div><dt>账号状态</dt><dd>{data?.status ? <StatusBadge status={data.status} /> : "—"}</dd></div>
            <div><dt>手机号</dt><dd>{display(data?.phone_masked)}</dd></div>
            <div><dt>邮箱</dt><dd>{display(data?.email)}</dd></div>
            <div><dt>注册时间</dt><dd>{display(data?.registered_at).slice(0, 10)}</dd></div>
          </dl>
        </div>
        <div className="credit-panel credit-panel--refined">
          <ShieldCheck size={36} />
          <span>信用分</span>
          <strong>{data?.credit_score ?? "—"}</strong>
          <small>{data?.credit_status || "信用状态以接口返回为准"}</small>
        </div>
      </GlassCard>

      <FlowFeedback message={message} />

      <div className="profile-grid profile-grid--restored">
        {grouped.length ? grouped.map(([group, groupSections]) => (
          <ProfilePanel
            key={group}
            icon={groupIcons[group] ?? <HelpCircle size={20} />}
            title={group}
            sections={groupSections}
            activeKey={activeSection?.key ?? ""}
            onOpen={setActiveSection}
            wide={groupSections.length > 3}
          />
        )) : (
          <GlassCard className="profile-panel profile-panel--wide">
            <div className="profile-panel__title"><span><UserRound size={20} /></span><h2>个人中心</h2></div>
            <div className="profile-panel__items"><div className="profile-entry">正在加载个人中心数据</div></div>
          </GlassCard>
        )}
      </div>

      <ProfileDetailDialog
        section={activeSection}
        profile={data}
        onClose={() => setActiveSection(null)}
        onAction={runAction}
        onContactSubmit={(body) => contactMutation.mutate(body)}
        contactPending={contactMutation.isPending}
        onPasswordSubmit={(body) => passwordMutation.mutate(body)}
        passwordPending={passwordMutation.isPending}
        onFeedbackSubmit={(body) => feedbackMutation.mutate(body)}
        feedbackPending={feedbackMutation.isPending}
      />

      {showCategorySelect && (
        <CategorySelectDialog
          onClose={() => setShowCategorySelect(false)}
          onSaved={() => {
            setShowCategorySelect(false);
            queryClient.invalidateQueries({ queryKey: ["profile-center"] });
            queryClient.invalidateQueries({ queryKey: ["home-overview"] });
          }}
        />
      )}

      {showRecommendationSelect && (
        <RecommendationSelectDialog
          onClose={() => setShowRecommendationSelect(false)}
          onSaved={() => {
            setShowRecommendationSelect(false);
            queryClient.invalidateQueries({ queryKey: ["profile-center"] });
            queryClient.invalidateQueries({ queryKey: ["home-overview"] });
          }}
        />
      )}

      {showBorrowHistory && (
        <BorrowHistoryDialog onClose={() => setShowBorrowHistory(false)} />
      )}
    </main>
  );
}
