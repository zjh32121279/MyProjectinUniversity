"""邮件发送模块 —— 通过 SMTP 发送验证码等通知邮件。"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from bookflow_core.core.config import settings, smtp_enabled

logger = logging.getLogger("bookflow.mailer")

SUBJECT_MAP = {
    "register": "BookFlow 注册验证码",
    "reset_password": "BookFlow 重置密码验证码",
    "login": "BookFlow 登录验证码",
    "general": "BookFlow 验证码",
}


def _html_body(code: str, purpose: str, expire_minutes: int = 10) -> str:
    label = SUBJECT_MAP.get(purpose, "BookFlow 验证码")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'PingFang SC','Microsoft YaHei',sans-serif">
<table width="100%%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:40px 0">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.06)">
<tr><td style="background:linear-gradient(135deg,#3b82f6,#7c3aed);padding:32px 40px;text-align:center">
<h1 style="margin:0;color:#fff;font-size:26px;font-weight:800">BookFlow</h1>
<p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px">{label}</p>
</td></tr>
<tr><td style="padding:36px 40px">
<p style="margin:0 0 12px;color:#374151;font-size:15px">你好，</p>
<p style="margin:0 0 24px;color:#6b7280;font-size:14px;line-height:1.7">你正在使用 BookFlow 图书馆管理系统。请使用以下验证码完成操作：</p>
<div style="background:#f0f4ff;border:1px solid #c7d2fe;border-radius:12px;padding:20px 24px;text-align:center;margin-bottom:24px">
<span style="font-size:36px;font-weight:900;letter-spacing:8px;color:#1d4ed8;font-family:'SF Mono','Consolas','Monaco',monospace">{code}</span>
</div>
<p style="margin:0 0 8px;color:#9ca3af;font-size:13px">验证码 {expire_minutes} 分钟内有效。如非本人操作，请忽略此邮件。</p>
</td></tr>
<tr><td style="background:#f9fafb;padding:20px 40px;text-align:center">
<p style="margin:0;color:#9ca3af;font-size:12px">此邮件由 BookFlow 系统自动发送，请勿回复。</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def send_verification_email(to_email: str, code: str, purpose: str = "general") -> bool:
    """发送验证码邮件。返回 True 表示发送成功。"""
    if not smtp_enabled():
        logger.warning("SMTP 未配置，跳过邮件发送。")
        return False

    subject = SUBJECT_MAP.get(purpose, "BookFlow 验证码")
    html = _html_body(code, purpose)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"BookFlow <{settings.smtp_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(f"您的验证码是：{code}，有效期 10 分钟。", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.smtp_port == 465:
            # SSL 直连
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            # STARTTLS
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        logger.info(f"验证码邮件已发送至 {to_email}（purpose={purpose}）。")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 认证失败，请检查邮箱地址和授权码。")
        return False
    except smtplib.SMTPConnectError:
        logger.error(f"无法连接 SMTP 服务器 {settings.smtp_host}:{settings.smtp_port}。")
        return False
    except Exception as exc:
        logger.error(f"邮件发送失败：{exc}")
        return False
