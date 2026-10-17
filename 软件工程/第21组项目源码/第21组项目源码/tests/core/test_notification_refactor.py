from __future__ import annotations

"""
通知中心重构测试

覆盖：
1. 未发送通知不会出现在读者端
2. send_message 后 delivery_status=sent 且 read_status=unread
3. 读者标记已读只改自己的 delivery
4. 读者不能读取或标记其他读者 delivery
5. 到期提醒重复触发不会重复创建 delivery
6. 逾期提醒重复触发不会重复创建 delivery
7. 预约到书提醒重复触发不会重复创建 delivery
8. 任务提醒重复触发不会重复创建 delivery
9. GET /notifications 需要管理员权限
10. 管理员通知中心统计 message 和 delivery 数量正确
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"


def _reset_notification_data(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM notification_deliveries")
        connection.execute("DELETE FROM notification_messages")
        connection.commit()


def _run_backend_script(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    db_path = tmp_path / "bookflow_test.db"
    shutil.copy2(SOURCE_DB, db_path)
    _reset_notification_data(db_path)
    env = os.environ.copy()
    env["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


# ---------------------------------------------------------------------------
# 测试 1: 未发送通知不会出现在读者端
# ---------------------------------------------------------------------------
def test_unsent_message_not_visible_to_reader(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import (
            create_message,
            create_deliveries,
            list_deliveries_for_reader,
            send_message,
        )

        ensure_schema()
        with get_session() as db:
            # 创建消息（草稿状态，未发送）
            msg = create_message(
                db,
                title="测试草稿消息",
                content="此消息尚未发送",
                notification_type="system",
                lifecycle_status="draft",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            # 创建投递记录（queued 状态，未发送）
            create_deliveries(
                db,
                message_id=msg.id,
                recipients=[{"recipient_type": "reader", "recipient_id": 1}],
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            db.commit()

            # 读者端查询 —— 只应看到 delivery_status='sent' 的记录
            result = list_deliveries_for_reader(db, reader_id=1)
            assert result["total"] == 0, (
                f"未发送的消息不应出现在读者端，但找到 {result['total']} 条"
            )
            print("PASS: 未发送通知不会出现在读者端")

            # 发送消息
            send_message(
                db,
                msg.id,
                actor_type="admin",
                actor_id="test_admin",
                commit=True,
            )

        with get_session() as db:
            # 发送后读者端应能看到
            result2 = list_deliveries_for_reader(db, reader_id=1)
            assert result2["total"] >= 1, (
                f"发送后的消息应出现在读者端，但找到 {result2['total']} 条"
            )
            print("PASS: 发送后读者端正确显示通知")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 2: send_message 后 delivery_status=sent 且 read_status=unread
# ---------------------------------------------------------------------------
def test_send_message_delivery_status_sent_and_read_status_unread(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import NotificationDelivery
        from bookflow_core.services.notification_service import (
            create_message,
            create_deliveries,
            send_message,
        )
        from sqlalchemy import select

        ensure_schema()
        with get_session() as db:
            msg = create_message(
                db,
                title="测试发送消息",
                content="此消息将被发送",
                notification_type="system",
                lifecycle_status="queued",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            create_deliveries(
                db,
                message_id=msg.id,
                recipients=[{"recipient_type": "reader", "recipient_id": 1}],
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            db.commit()

            # 发送
            result = send_message(db, msg.id, actor_type="admin", actor_id="test_admin", commit=True)
            assert result["sent_count"] >= 1, f"发送计数应为 >=1，实际: {result['sent_count']}"

        with get_session() as db:
            deliveries = db.scalars(
                select(NotificationDelivery).where(
                    NotificationDelivery.message_id == msg.id
                )
            ).all()
            for d in deliveries:
                assert d.delivery_status == "sent", (
                    f"投递状态应为 'sent'，实际: {d.delivery_status}"
                )
                assert d.read_status == "unread", (
                    f"阅读状态应为 'unread'（发送成功≠已读），实际: {d.read_status}"
                )
            print("PASS: send_message 后 delivery_status=sent 且 read_status=unread")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 3: 读者标记已读只改自己的 delivery
# ---------------------------------------------------------------------------
def test_reader_mark_read_only_own_delivery(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.models import NotificationDelivery
        from bookflow_core.services.notification_service import (
            create_message,
            create_deliveries,
            send_message,
            mark_delivery_read,
        )
        from sqlalchemy import select

        ensure_schema()
        with get_session() as db:
            msg = create_message(
                db,
                title="测试已读隔离",
                content="两个读者各一条",
                notification_type="system",
                lifecycle_status="queued",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            create_deliveries(
                db,
                message_id=msg.id,
                recipients=[
                    {"recipient_type": "reader", "recipient_id": 1},
                    {"recipient_type": "reader", "recipient_id": 2},
                ],
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            db.commit()
            send_message(db, msg.id, actor_type="admin", actor_id="test_admin", commit=True)

        with get_session() as db:
            # 获取读者 1 的 delivery
            d1 = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.message_id == msg.id,
                    NotificationDelivery.recipient_type == "reader",
                    NotificationDelivery.recipient_id == 1,
                )
            )
            assert d1 is not None
            assert d1.read_status == "unread"

            # 读者 1 标记已读
            mark_delivery_read(
                db, d1.id,
                recipient_type="reader",
                recipient_id=1,
                actor_type="reader",
                actor_id="reader_1",
                commit=True,
            )

        with get_session() as db:
            # 验证读者 1 的已读
            d1_after = db.get(NotificationDelivery, d1.id)
            assert d1_after.read_status == "read", f"读者 1 的投递应为已读，实际: {d1_after.read_status}"

            # 验证读者 2 的仍然未读
            d2 = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.message_id == msg.id,
                    NotificationDelivery.recipient_type == "reader",
                    NotificationDelivery.recipient_id == 2,
                )
            )
            assert d2 is not None
            assert d2.read_status == "unread", (
                f"读者 2 的投递不应被读者 1 影响，但状态是: {d2.read_status}"
            )
            print("PASS: 读者标记已读只改自己的 delivery")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 4: 读者不能读取或标记其他读者 delivery
# ---------------------------------------------------------------------------
def test_reader_cannot_access_other_reader_delivery(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.exceptions import BookFlowError
        from bookflow_core.models import NotificationDelivery
        from bookflow_core.services.notification_service import (
            create_message,
            create_deliveries,
            send_message,
            mark_delivery_read,
            list_deliveries_for_reader,
        )
        from sqlalchemy import select

        ensure_schema()
        with get_session() as db:
            msg = create_message(
                db,
                title="权限隔离测试",
                content="仅读者 2 可见",
                notification_type="system",
                lifecycle_status="queued",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            create_deliveries(
                db,
                message_id=msg.id,
                recipients=[{"recipient_type": "reader", "recipient_id": 2}],
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            db.commit()
            send_message(db, msg.id, actor_type="admin", actor_id="test_admin", commit=True)

        with get_session() as db:
            # 读者 1 查询 —— 不应看到读者 2 的投递
            r1_result = list_deliveries_for_reader(db, reader_id=1)
            assert r1_result["total"] == 0, (
                f"读者 1 不应看到读者 2 的投递，但找到 {r1_result['total']} 条"
            )

            # 获取读者 2 的 delivery
            d2 = db.scalar(
                select(NotificationDelivery).where(
                    NotificationDelivery.message_id == msg.id,
                    NotificationDelivery.recipient_type == "reader",
                    NotificationDelivery.recipient_id == 2,
                )
            )

            # 读者 1 尝试标记读者 2 的 delivery 为已读 —— 应被拒绝
            try:
                mark_delivery_read(
                    db, d2.id,
                    recipient_type="reader",
                    recipient_id=1,
                    actor_type="reader",
                    actor_id="reader_1",
                )
                assert False, "读者 1 不应能标记读者 2 的投递为已读，但没有抛出异常"
            except BookFlowError:
                print("PASS: 读者 1 被正确拒绝标记读者 2 的投递")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 5: 到期提醒重复触发不会重复创建 delivery
# ---------------------------------------------------------------------------
def test_due_reminders_idempotency(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import create_due_reminders

        ensure_schema()
        with get_session() as db:
            r1 = create_due_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第一次到期提醒: created={r1['created_count']}, skipped={r1['skipped_count']}")

            r2 = create_due_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第二次到期提醒: created={r2['created_count']}, skipped={r2['skipped_count']}")

            # 第二次触发不应再创建新投递（幂等键相同）
            assert r2["created_count"] == 0, (
                f"第二次到期提醒不应创建新投递（幂等），但创建了 {r2['created_count']} 条"
            )
            print("PASS: 到期提醒幂等去重正确")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 6: 逾期提醒重复触发不会重复创建 delivery
# ---------------------------------------------------------------------------
def test_overdue_reminders_idempotency(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import create_overdue_reminders

        ensure_schema()
        with get_session() as db:
            r1 = create_overdue_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第一次逾期提醒: created={r1['created_count']}, skipped={r1['skipped_count']}")

            r2 = create_overdue_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第二次逾期提醒: created={r2['created_count']}, skipped={r2['skipped_count']}")

            assert r2["created_count"] == 0, (
                f"第二次逾期提醒不应创建新投递（幂等），但创建了 {r2['created_count']} 条"
            )
            print("PASS: 逾期提醒幂等去重正确")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 7: 预约到书提醒重复触发不会重复创建 delivery
# ---------------------------------------------------------------------------
def test_reservation_ready_reminders_idempotency(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import create_reservation_ready_reminders

        ensure_schema()
        with get_session() as db:
            r1 = create_reservation_ready_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第一次预约到书提醒: created={r1['created_count']}, skipped={r1['skipped_count']}")

            r2 = create_reservation_ready_reminders(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第二次预约到书提醒: created={r2['created_count']}, skipped={r2['skipped_count']}")

            assert r2["created_count"] == 0, (
                f"第二次预约到书提醒不应创建新投递（幂等），但创建了 {r2['created_count']} 条"
            )
            print("PASS: 预约到书提醒幂等去重正确")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 8: 任务提醒重复触发不会重复创建 delivery
# ---------------------------------------------------------------------------
def test_task_notifications_idempotency(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import create_task_notifications

        ensure_schema()
        with get_session() as db:
            r1 = create_task_notifications(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第一次任务提醒: created={r1['created_count']}, skipped={r1['skipped_count']}")

            r2 = create_task_notifications(db, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"第二次任务提醒: created={r2['created_count']}, skipped={r2['skipped_count']}")

            assert r2["created_count"] == 0, (
                f"第二次任务提醒不应创建新投递（幂等），但创建了 {r2['created_count']} 条"
            )
            print("PASS: 任务提醒幂等去重正确")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 9: GET /notifications 需要管理员权限
# ---------------------------------------------------------------------------
def test_notifications_endpoint_requires_permission(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from fastapi.testclient import TestClient
        from uuid import uuid4

        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.core.security import create_access_token, hash_password
        from bookflow_core.main import app
        from bookflow_core.models import AdminUser

        ensure_schema()
        suffix = uuid4().hex[:8]
        admin_id = None

        try:
            with get_session() as db:
                admin = AdminUser(
                    admin_code=f"PYTEST-NTF-{suffix}",
                    name="pytest notification admin",
                    email=f"ntf-{suffix}@pytest.local",
                    password_hash=hash_password("test123"),
                    status="active",
                    is_super_admin=False,
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
                admin_id = admin.id
                token = create_access_token(admin.id, role="admin", subject_type="admin", admin_code=admin.admin_code)

            client = TestClient(app)

            # 无 token 请求 —— 应返回 401
            no_auth = client.get("/notifications")
            assert no_auth.status_code in (401, 403), (
                f"无认证请求应返回 401/403，实际: {no_auth.status_code}"
            )
            print(f"PASS: 无认证请求被拒绝 ({no_auth.status_code})")

            # 有 token 请求 —— admin 角色有 notifications:read 权限
            auth_resp = client.get("/notifications", headers={"Authorization": f"Bearer {token}"})
            assert auth_resp.status_code == 200, (
                f"有权限的管理员请求应返回 200，实际: {auth_resp.status_code}, body: {auth_resp.text[:500]}"
            )
            data = auth_resp.json()
            assert data["success"] is True
            print("PASS: 管理员可正常访问通知中心")

        finally:
            # 清理测试数据，防止污染数据库（即使是临时库）
            from sqlalchemy import text
            with get_session() as db:
                db.execute(text(f"DELETE FROM admin_login_events WHERE admin_code LIKE 'PYTEST-NTF-%'"))
                db.execute(text("DELETE FROM admin_user_roles WHERE admin_id IN (SELECT id FROM admin_users WHERE admin_code LIKE 'PYTEST-NTF-%')"))
                db.execute(text("DELETE FROM admin_users WHERE admin_code LIKE 'PYTEST-NTF-%'"))
                db.commit()
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"


# ---------------------------------------------------------------------------
# 测试 10: 管理员通知中心统计 message 和 delivery 数量正确
# ---------------------------------------------------------------------------
def test_admin_message_stats_correct(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.core.database import ensure_schema, get_session
        from bookflow_core.services.notification_service import (
            create_message,
            create_deliveries,
            send_message,
            message_stats,
            list_messages_for_admin,
        )

        ensure_schema()
        with get_session() as db:
            # 创建草稿消息
            draft = create_message(
                db,
                title="草稿消息",
                content="draft content",
                notification_type="system",
                lifecycle_status="draft",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )

            # 创建待发送消息
            queued = create_message(
                db,
                title="待发送消息",
                content="queued content",
                notification_type="due",
                lifecycle_status="queued",
                created_by_type="admin",
                created_by_code="test_admin",
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            create_deliveries(
                db,
                message_id=queued.id,
                recipients=[
                    {"recipient_type": "reader", "recipient_id": 1},
                    {"recipient_type": "reader", "recipient_id": 2},
                    {"recipient_type": "reader", "recipient_id": 3},
                ],
                actor_type="admin",
                actor_id="test_admin",
                commit=False,
            )
            db.commit()

            # 发送第二條消息
            send_result = send_message(db, queued.id, actor_type="admin", actor_id="test_admin", commit=True)
            print(f"发送结果: {send_result}")

        with get_session() as db:
            stats = message_stats(db)
            print(f"统计: {stats}")

            # 应有 1 条草稿 (draft)
            assert stats["draft_queued_count"] >= 1, (
                f"草稿/待发送计数应 >=1，实际: {stats['draft_queued_count']}"
            )
            # 应有至少 1 条已完成消息
            assert stats["completed_count"] >= 1, (
                f"已完成消息计数应 >=1，实际: {stats['completed_count']}"
            )
            # 今日发送应 >= 3
            assert stats["sent_today_count"] >= 3, (
                f"今日发送计数应 >=3，实际: {stats['sent_today_count']}"
            )
            print("PASS: 统计数量正确")

            # 验证 list_messages_for_admin 返回正确的投递统计
            result = list_messages_for_admin(db, limit=50, offset=0)
            assert result["total"] >= 2
            for item in result["items"]:
                assert "total_deliveries" in item
                assert "sent_deliveries" in item
                assert "lifecycle_status" in item
            print(f"PASS: list_messages_for_admin 返回 {result['total']} 条消息，投递统计正确")
        """,
    )
    assert result.returncode == 0, f"STDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
