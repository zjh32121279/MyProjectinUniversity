from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

from bookflow_core.core.time import now

Base = declarative_base()

class LibraryProfile(Base):
    __tablename__ = "library_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    library_code = Column(String, unique=True)
    library_name = Column(String)
    library_type = Column(String)
    service_population = Column(String)
    building_area_sqm = Column(Float)
    open_floors = Column(String)
    paper_collection_count = Column(Integer)
    lendable_collection_count = Column(Integer)
    in_library_reference_count = Column(Integer)
    periodical_count = Column(Integer)
    reading_seat_count = Column(Integer)
    shelf_count = Column(Integer)
    registered_reader_count = Column(Integer)
    monthly_active_reader_count = Column(Integer)
    weekday_daily_visits = Column(String)
    weekend_daily_visits = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class LibraryZone(Base):
    __tablename__ = "library_zones"
    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_code = Column(String)
    zone_name = Column(String)
    floor = Column(String)
    area_sqm = Column(Float)
    main_use = Column(String)
    is_public = Column(Boolean, default=False)
    sort_order = Column(Integer)
    pos_x = Column(Float, default=0)
    pos_y = Column(Float, default=0)
    width = Column(Float, default=200)
    height = Column(Float, default=150)
    color = Column(String, default="#e8f4f8")
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Shelf(Base):
    __tablename__ = "shelves"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shelf_code = Column(String, unique=True)
    zone_id = Column(Integer, ForeignKey("library_zones.id"))
    zone_code = Column(String)
    floor = Column(String)
    shelf_index = Column(Integer)
    layer_count = Column(Integer)
    side_rule = Column(String)
    shelf_type = Column(String)
    counted_in_72_formal_shelves = Column(Boolean, default=False)
    pos_x = Column(Float, default=0)
    pos_y = Column(Float, default=0)
    width = Column(Float, default=60)
    height = Column(Float, default=40)
    rotation = Column(Float, default=0)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ShelfPosition(Base):
    __tablename__ = "shelf_positions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    position_code = Column(String, unique=True)
    shelf_id = Column(Integer, ForeignKey("shelves.id"))
    layer_no = Column(Integer)
    side = Column(String)
    capacity_estimate = Column(Integer)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String, unique=True)
    setting_value = Column(String)
    value_type = Column(String)
    scope = Column(String)
    description = Column(Text)
    is_active = Column(Boolean, default=False)
    updated_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class DailyOperationMetric(Base):
    __tablename__ = "daily_operation_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_date = Column(Date)
    metric_key = Column(String)
    metric_value = Column(String)
    metric_unit = Column(String)
    source_table = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_code = Column(String, unique=True)
    snapshot_date = Column(Date)
    module = Column(String)
    payload_json = Column(Text)
    generated_by = Column(String)
    created_at = Column(DateTime, default=now)


class DataImportBatch(Base):
    __tablename__ = "data_import_batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String, unique=True)
    source_name = Column(String)
    source_version = Column(String)
    file_name = Column(String)
    row_count = Column(Integer)
    status = Column(String)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_by_admin_id = Column(Integer)
    note = Column(Text)


class DataImportError(Base):
    __tablename__ = "data_import_errors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("data_import_batches.id"))
    file_name = Column(String)
    row_no = Column(Integer)
    source_key = Column(String)
    error_type = Column(String)
    error_message = Column(Text)
    raw_json = Column(Text)
    created_at = Column(DateTime, default=now)


class BookCategory(Base):
    __tablename__ = "book_categories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_code = Column(String)
    category_name = Column(String)
    subcategory_examples = Column(String)
    book_title_count = Column(Integer)
    copy_count = Column(Integer)
    primary_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    primary_zone_code = Column(String)
    clc_hint = Column(String)
    sort_order = Column(Integer)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class BookSubcategory(Base):
    __tablename__ = "book_subcategories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    subcategory_code = Column(String, unique=True)
    subcategory_name = Column(String)
    category_id = Column(Integer, ForeignKey("book_categories.id"))
    category_code = Column(String)
    category_name = Column(String)
    allocated_book_title_count = Column(Integer)
    sort_order = Column(Integer)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_book_id = Column(Integer)
    book_code = Column(String, unique=True)
    category_id = Column(Integer, ForeignKey("book_categories.id"))
    category_code = Column(String)
    category_name = Column(String)
    subcategory_id = Column(Integer, ForeignKey("book_subcategories.id"))
    subcategory_code = Column(String)
    subcategory_name = Column(String)
    clc_hint = Column(String)
    title = Column(String)
    author = Column(String)
    publisher = Column(String)
    publish_year = Column(Integer)
    isbn = Column(String)
    language = Column(String)
    edition = Column(String)
    pages = Column(Integer)
    price_yuan = Column(Float)
    copy_count_snapshot = Column(String)
    primary_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    primary_zone_code = Column(String)
    recommended_reader = Column(String)
    keywords = Column(String)
    introduction = Column(Text)
    circulation_type = Column(String)
    data_note = Column(String)
    clc_code = Column(String)
    call_number = Column(String)
    isbn_status = Column(String)
    bibliographic_status = Column(String)
    book_source_class = Column(String)
    cover_url = Column(String)
    cover_source = Column(String)
    cover_status = Column(String)
    cover_updated_at = Column(DateTime)
    status = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class BookSubjectTag(Base):
    __tablename__ = "book_subject_tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String, unique=True)
    tag_type = Column(String)
    normalized_name = Column(String)
    created_at = Column(DateTime, default=now)


class BookSubjectRelation(Base):
    __tablename__ = "book_subject_relations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"))
    tag_id = Column(Integer, ForeignKey("book_subject_tags.id"))
    weight = Column(String)
    source = Column(String)
    created_at = Column(DateTime, default=now)


class BookCopy(Base):
    __tablename__ = "book_copies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_copy_id = Column(Integer)
    copy_code = Column(String, unique=True)
    source_book_id = Column(Integer)
    book_id = Column(Integer, ForeignKey("books.id"))
    copy_no = Column(Integer)
    barcode = Column(String, unique=True)
    category_code = Column(String)
    subcategory_code = Column(String)
    collection_type = Column(String)
    can_borrow_outside_library = Column(Boolean, default=False)
    status_code = Column(String)
    status_name = Column(String)
    copy_status = Column(String)
    current_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    current_zone_code = Column(String)
    current_shelf_id = Column(Integer, ForeignKey("shelves.id"))
    shelf_code = Column(String)
    current_position_id = Column(Integer, ForeignKey("shelf_positions.id"))
    shelf_position = Column(String)
    home_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    home_zone_code = Column(String)
    home_shelf_id = Column(Integer, ForeignKey("shelves.id"))
    home_shelf_code = Column(String)
    home_position_id = Column(Integer, ForeignKey("shelf_positions.id"))
    home_shelf_position = Column(String)
    acquisition_date = Column(Date)
    acquisition_source = Column(String)
    condition_level = Column(String)
    asset_price_yuan = Column(Float)
    remark = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class BookCirculationStats(Base):
    __tablename__ = "book_circulation_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"))
    source_book_id = Column(Integer)
    title_snapshot = Column(String)
    total_copies = Column(Integer)
    available_copies = Column(Integer)
    active_loans = Column(Integer)
    reservations_waiting = Column(Integer)
    borrow_90d = Column(Integer)
    reserve_90d = Column(Integer)
    borrow_365d = Column(Integer)
    days_since_last_borrow = Column(Integer)
    circulation_type = Column(String)
    last_borrow_date = Column(Date)
    stat_date = Column(Date)
    computed_at = Column(DateTime)


class CopyStatusEvent(Base):
    __tablename__ = "copy_status_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id"))
    old_status = Column(String)
    new_status = Column(String)
    reason = Column(String)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    actor_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    created_at = Column(DateTime, default=now)


class CopyLocationEvent(Base):
    __tablename__ = "copy_location_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    copy_id = Column(Integer, ForeignKey("book_copies.id"))
    from_position_id = Column(Integer, ForeignKey("shelf_positions.id"))
    to_position_id = Column(Integer, ForeignKey("shelf_positions.id"))
    from_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    to_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    reason = Column(String)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    actor_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    created_at = Column(DateTime, default=now)


class SearchEvent(Base):
    __tablename__ = "search_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String)
    normalized_keyword = Column(String)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    session_id = Column(Integer)
    result_count = Column(Integer)
    clicked_book_id = Column(Integer, ForeignKey("books.id"))
    source_app = Column(String)
    created_at = Column(DateTime, default=now)


class ReaderAccount(Base):
    __tablename__ = "reader_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_reader_id = Column(Integer)
    reader_code = Column(String, unique=True)
    reader_type_code = Column(String)
    reader_type_name = Column(String)
    name = Column(String)
    phone_masked = Column(String)
    phone_hash = Column(String)
    email = Column(String)
    avatar_url = Column(String)
    status = Column(String)
    credit_score = Column(String)
    registered_at = Column(DateTime)
    active_90d = Column(String)
    current_borrow_count = Column(Integer)
    borrow_suspended_until = Column(String)
    remark = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ReaderCredential(Base):
    __tablename__ = "reader_credentials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    login_name = Column(String)
    phone_hash = Column(String)
    email = Column(String)
    password_hash = Column(String)
    status = Column(String)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ReaderLoginEvent(Base):
    __tablename__ = "reader_login_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    login_name = Column(String)
    event_type = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    result = Column(String)
    failure_reason = Column(String)
    created_at = Column(DateTime, default=now)


class ReaderVerificationCode(Base):
    __tablename__ = "reader_verification_codes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    account = Column(String)
    purpose = Column(String)
    code_hash = Column(String)
    expire_at = Column(DateTime)
    consumed_at = Column(DateTime)
    request_ip = Column(String)
    created_at = Column(DateTime, default=now)


class ReaderStatusEvent(Base):
    __tablename__ = "reader_status_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    old_status = Column(String)
    new_status = Column(String)
    reason = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    created_at = Column(DateTime, default=now)


class ReaderCreditEvent(Base):
    __tablename__ = "reader_credit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    delta = Column(String)
    old_score = Column(String)
    new_score = Column(String)
    reason = Column(String)
    related_loan_id = Column(Integer, ForeignKey("loans.id"))
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    created_at = Column(DateTime, default=now)


class ReaderStats(Base):
    __tablename__ = "reader_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    active_loans = Column(String)
    overdue_count = Column(Integer)
    total_borrow_count = Column(Integer)
    total_reservation_count = Column(Integer)
    last_borrowed_at = Column(DateTime)
    computed_at = Column(DateTime)


class ReaderNotificationSetting(Base):
    __tablename__ = "reader_notification_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    borrow_due_enabled = Column(Boolean, default=False)
    reservation_arrival_enabled = Column(Boolean, default=False)
    system_notice_enabled = Column(Boolean, default=False)
    email_enabled = Column(Boolean, default=False)
    sms_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ReaderPreference(Base):
    __tablename__ = "reader_preferences"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"), unique=True)
    favorite_category_codes = Column(Text)  # JSON array of category codes
    recommendation_source = Column(String, default="both")  # "popular" | "preference" | "both"
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class CirculationRule(Base):
    __tablename__ = "circulation_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String, unique=True)
    reader_type_code = Column(String)
    reader_type_name = Column(String)
    circulation_type = Column(String)
    max_borrow_count = Column(Integer)
    borrow_days = Column(Integer)
    max_renewals = Column(Integer)
    reservation_limit = Column(Integer)
    is_active = Column(Boolean, default=False)
    effective_from = Column(Date)
    effective_to = Column(Date)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class CirculationPolicy(Base):
    __tablename__ = "circulation_policies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hot_borrow_90d_threshold = Column(String)
    hot_reserve_90d_threshold = Column(String)
    cold_borrow_365d_threshold = Column(String)
    cold_days_since_last_borrow_threshold = Column(String)
    reservation_hold_days = Column(Integer)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_loan_id = Column(Integer)
    loan_code = Column(String, unique=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    source_reader_id = Column(Integer)
    copy_id = Column(Integer, ForeignKey("book_copies.id"))
    source_copy_id = Column(Integer)
    book_id = Column(Integer, ForeignKey("books.id"))
    source_book_id = Column(Integer)
    borrowed_at = Column(DateTime)
    due_at = Column(DateTime)
    returned_at = Column(DateTime)
    status = Column(String)
    renewal_count = Column(Integer)
    overdue_days_snapshot = Column(Integer)
    handled_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    handled_by_code = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class LoanEvent(Base):
    __tablename__ = "loan_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id"))
    event_type = Column(String)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    event_time = Column(String)
    detail = Column(Text)
    old_due_at = Column(DateTime)
    new_due_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_reservation_id = Column(Integer)
    reservation_code = Column(String, unique=True)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    source_reader_id = Column(Integer)
    book_id = Column(Integer, ForeignKey("books.id"))
    source_book_id = Column(Integer)
    fulfilled_copy_id = Column(Integer, ForeignKey("book_copies.id"))
    source_copy_id = Column(Integer)
    status = Column(String)
    requested_at = Column(DateTime)
    reserved_until = Column(String)
    pickup_zone_id = Column(Integer, ForeignKey("library_zones.id"))
    pickup_zone_code = Column(String)
    pickup_position_id = Column(Integer, ForeignKey("shelf_positions.id"))
    pickup_shelf_position = Column(String)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_by_code = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ReservationEvent(Base):
    __tablename__ = "reservation_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"))
    event_type = Column(String)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    event_time = Column(String)
    detail = Column(Text)
    created_at = Column(DateTime, default=now)


class CirculationServiceRequest(Base):
    __tablename__ = "circulation_service_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('borrow', 'reservation', 'renew', 'return')",
            name="ck_circulation_service_requests_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'pending', 'ready', 'completed', 'cancelled', 'expired', 'failed', 'waiting_human')",
            name="ck_circulation_service_requests_status",
        ),
        Index("ix_circulation_service_requests_code", "request_code"),
        Index("ix_circulation_service_requests_voucher", "voucher_code"),
        Index("ix_circulation_service_requests_reader_status", "reader_id", "status"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String, unique=True)
    voucher_code = Column(String, unique=True)
    request_type = Column(String)
    status = Column(String)
    source_type = Column(String)
    source_actor_type = Column(String)
    source_actor_id = Column(String)
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    reader_code = Column(String)
    book_id = Column(Integer, ForeignKey("books.id"))
    book_code = Column(String)
    copy_id = Column(Integer, ForeignKey("book_copies.id"))
    copy_code = Column(String)
    loan_id = Column(Integer, ForeignKey("loans.id"))
    loan_code = Column(String)
    reservation_id = Column(Integer, ForeignKey("reservations.id"))
    reservation_code = Column(String)
    task_code = Column(String)
    task_id = Column(Integer, ForeignKey("work_tasks.id"))
    ai_plan_json = Column(Text)
    ai_trace_json = Column(Text)
    request_payload_json = Column(Text)
    result_json = Column(Text)
    failure_reason = Column(Text)
    expires_at = Column(DateTime)
    completed_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    handled_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    handled_by_code = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class OverdueCase(Base):
    __tablename__ = "overdue_cases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id"))
    reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    copy_id = Column(Integer, ForeignKey("book_copies.id"))
    overdue_start_at = Column(DateTime)
    overdue_days = Column(Integer)
    penalty_score = Column(Integer)
    status = Column(String)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_admin_id = Column(Integer)
    admin_code = Column(String)
    name = Column(String)
    email = Column(String)
    password_hash = Column(String)
    status = Column(String)
    is_super_admin = Column(Boolean, default=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AdminRole(Base):
    __tablename__ = "admin_roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_code = Column(String, unique=True)
    name = Column(String)
    description = Column(Text)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AdminPermission(Base):
    __tablename__ = "admin_permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    permission_code = Column(String, unique=True)
    name = Column(String)
    module = Column(String)
    description = Column(Text)
    risk_level = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AdminUserRole(Base):
    __tablename__ = "admin_user_roles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id"))
    role_id = Column(Integer, ForeignKey("admin_roles.id"))
    assigned_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_at = Column(DateTime, default=now)


class AdminRolePermission(Base):
    __tablename__ = "admin_role_permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(Integer, ForeignKey("admin_roles.id"))
    permission_id = Column(Integer, ForeignKey("admin_permissions.id"))
    created_at = Column(DateTime, default=now)


class AdminLoginEvent(Base):
    __tablename__ = "admin_login_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id"))
    admin_code = Column(String)
    event_type = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    result = Column(String)
    failure_reason = Column(String)
    created_at = Column(DateTime, default=now)


class WorkTask(Base):
    __tablename__ = "work_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'ai_processing', 'waiting_human', 'admin_processing', 'resolved', 'cancelled')",
            name="ck_work_tasks_status",
        ),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_task_id = Column(Integer)
    task_code = Column(String, unique=True)
    title = Column(String)
    description = Column(Text)
    task_type = Column(String)
    task_group = Column(String)
    priority = Column(String)
    status = Column(String)
    source_type = Column(String)
    ai_default_executor = Column(Boolean, default=False)
    assigned_to_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    claimed_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    claimed_by_code = Column(String)
    resolved_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    resolved_by_code = Column(String)
    related_entity_type = Column(String)
    related_entity_id = Column(String)
    sla_due_at = Column(DateTime)
    claimed_at = Column(DateTime)
    resolved_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    resolution = Column(String)
    requires_human_confirmation = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)
    handler_type = Column(String)
    claim_status = Column(String)
    ai_run_id = Column(Integer)
    ai_started_at = Column(DateTime)
    ai_finished_at = Column(DateTime)
    ai_error = Column(String)
    ai_confidence = Column(Float)
    ai_result = Column(String)
    takeover_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    takeover_by_code = Column(String)
    takeover_at = Column(DateTime)
    takeover_reason = Column(String)
    last_actor_type = Column(String)
    last_actor_id = Column(String)
    last_transition = Column(String)
    last_transition_at = Column(DateTime)
    risk_warning_code = Column(String)
    queue_name = Column(String, default="default")
    priority_score = Column(Integer, default=0)
    risk_level = Column(String, default="low")
    urgency_reason = Column(Text)
    source_payload_json = Column(Text)
    execution_context_json = Column(Text)
    ai_plan_json = Column(Text)
    ai_trace_json = Column(Text)
    lease_owner = Column(String)
    lease_expires_at = Column(DateTime)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    next_attempt_at = Column(DateTime)
    interrupted_at = Column(DateTime)
    interrupt_reason = Column(Text)


class WorkTaskEvent(Base):
    __tablename__ = "work_task_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("work_tasks.id"))
    event_type = Column(String)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    detail_json = Column(Text)
    created_at = Column(DateTime, default=now)


class AITaskCheckpoint(Base):
    __tablename__ = "ai_task_checkpoints"
    id = Column(Integer, primary_key=True, autoincrement=True)
    checkpoint_code = Column(String, unique=True)
    task_id = Column(Integer, ForeignKey("work_tasks.id"))
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    worker_id = Column(String)
    node_name = Column(String)
    status = Column(String)
    state_json = Column(Text)
    resume_token = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIExecutionLedger(Base):
    __tablename__ = "ai_execution_ledger"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_code = Column(String, unique=True)
    task_id = Column(Integer, ForeignKey("work_tasks.id"))
    task_code = Column(String)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    sop_id = Column(String)
    phase = Column(String)
    tool_name = Column(String)
    idempotency_key = Column(String, unique=True)
    target_type = Column(String)
    target_id = Column(String)
    status = Column(String)
    reason = Column(Text)
    request_json = Column(Text)
    result_json = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ReviewItem(Base):
    __tablename__ = "review_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_code = Column(String, unique=True)
    review_type = Column(String)
    title = Column(String)
    description = Column(Text)
    status = Column(String)
    risk_level = Column(String)
    source_type = Column(String)
    requested_by_actor_type = Column(String)
    requested_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    requested_by_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    reviewed_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    payload_json = Column(Text)
    decision_reason = Column(Text)
    created_at = Column(DateTime, default=now)
    reviewed_at = Column(DateTime)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AICapability(Base):
    __tablename__ = "ai_capabilities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_name = Column(String)
    display_name = Column(String)
    permission_level = Column(String)
    risk_level = Column(String)
    is_write = Column(Boolean, default=False)
    writes_db = Column(Boolean, default=False)
    requires_super_authorization = Column(Boolean, default=False)
    input_schema_json = Column(Text)
    output_schema_json = Column(Text)
    is_enabled = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIRule(Base):
    __tablename__ = "ai_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String, unique=True)
    rule_name = Column(String)
    rule_type = Column(String)
    module = Column(String)
    target_reader_type = Column(String)
    target_circulation_type = Column(String)
    priority = Column(Integer)
    risk_level = Column(String)
    status = Column(String)
    is_enabled = Column(Boolean, default=False)
    current_version_id = Column(Integer, ForeignKey("ai_rule_versions.id"))
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIRuleVersion(Base):
    __tablename__ = "ai_rule_versions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("ai_rules.id"))
    version_no = Column(Integer)
    rule_config_json = Column(Text)
    trigger_condition_json = Column(Text)
    action_json = Column(Text)
    effective_from = Column(Date)
    effective_to = Column(Date)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_at = Column(DateTime, default=now)


class AIRuleExecutionLog(Base):
    __tablename__ = "ai_rule_execution_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, ForeignKey("ai_rules.id"))
    rule_version_id = Column(Integer, ForeignKey("ai_rule_versions.id"))
    related_entity_type = Column(String)
    related_entity_id = Column(Integer)
    trigger_result = Column(String)
    action_result = Column(String)
    actor_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    created_at = Column(DateTime, default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_code = Column(String, unique=True)
    trigger_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_type = Column(String)
    actor_code = Column(String)
    tool_name = Column(String)
    status = Column(String)
    input_json = Column(Text)
    output_json = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    step_name = Column(String)
    status = Column(String)
    detail_json = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIApprovalRequest(Base):
    __tablename__ = "ai_approval_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_code = Column(String, unique=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id"))
    capability_id = Column(Integer, ForeignKey("ai_capabilities.id"))
    requested_action = Column(String)
    payload_json = Column(Text)
    status = Column(String)
    requested_by_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    reviewed_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    reviewed_at = Column(DateTime)
    decision_reason = Column(Text)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_code = Column(String, unique=True)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_type = Column(String)
    actor_code = Column(String)
    title = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"))
    role = Column(String)
    content = Column(Text)
    agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    token_usage_id = Column(Integer, ForeignKey("ai_token_usage.id"))
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AITokenUsage(Base):
    __tablename__ = "ai_token_usage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String)
    model = Column(String)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    cost_estimate = Column(Float)
    related_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    related_conversation_id = Column(Integer, ForeignKey("ai_conversations.id"))
    created_at = Column(DateTime, default=now)


class AIMemoryItem(Base):
    __tablename__ = "ai_memory_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_code = Column(String, unique=True)
    scope = Column(String)
    key = Column(String)
    value_json = Column(Text)
    importance = Column(Integer)
    last_used_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class AIObservation(Base):
    __tablename__ = "ai_observations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    observation_code = Column(String, unique=True)
    source_type = Column(String)
    source_entity_type = Column(String)
    source_entity_id = Column(Integer)
    payload_json = Column(Text)
    status = Column(String)
    created_at = Column(DateTime, default=now)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    template_code = Column(String, unique=True)
    title_template = Column(String)
    content_template = Column(String)
    notification_type = Column(String)
    channel = Column(String)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class NotificationBatch(Base):
    __tablename__ = "notification_batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_code = Column(String, unique=True)
    template_id = Column(Integer, ForeignKey("notification_templates.id"))
    title = Column(String)
    channel = Column(String)
    status = Column(String)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    created_by_code = Column(String)
    target_count = Column(Integer)
    sent_count = Column(Integer)
    failed_count = Column(Integer)
    send_at = Column(DateTime)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class NotificationMessage(Base):
    """通知主体 —— 一条消息可以被投递给多个接收人。"""
    __tablename__ = "notification_messages"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('draft', 'queued', 'sending', 'completed', 'cancelled', 'failed')",
            name="ck_notification_messages_lifecycle_status",
        ),
        Index("ix_notification_messages_type", "notification_type"),
        Index("ix_notification_messages_lifecycle", "lifecycle_status"),
        Index("ix_notification_messages_scheduled", "scheduled_at"),
        Index("ix_notification_messages_created", "created_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_code = Column(String, unique=True)
    title = Column(String)
    content = Column(Text)
    notification_type = Column(String)
    source_type = Column(String)
    source_task_code = Column(String, nullable=True)
    related_entity_type = Column(String, nullable=True)
    related_entity_id = Column(String, nullable=True)
    target_scope_json = Column(Text)
    lifecycle_status = Column(String, default="draft")
    scheduled_at = Column(DateTime, nullable=True)
    created_by_type = Column(String)
    created_by_code = Column(String)
    idempotency_key = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class NotificationDelivery(Base):
    """投递记录 —— 一条消息到达一个接收人的记录，包含投递状态和阅读状态。"""
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('queued', 'sent', 'failed', 'skipped')",
            name="ck_notification_deliveries_delivery_status",
        ),
        CheckConstraint(
            "read_status IN ('unread', 'read')",
            name="ck_notification_deliveries_read_status",
        ),
        CheckConstraint(
            "recipient_type IN ('reader', 'admin')",
            name="ck_notification_deliveries_recipient_type",
        ),
        Index("ix_notification_deliveries_message", "message_id"),
        Index("ix_notification_deliveries_recipient", "recipient_type", "recipient_id"),
        Index("ix_notification_deliveries_delivery_status", "delivery_status"),
        Index("ix_notification_deliveries_read_status", "read_status"),
        Index("ix_notification_deliveries_idempotency", "idempotency_key"),
        Index("ix_notification_deliveries_archived", "archived_at"),
        Index("ix_notification_deliveries_reader_sent", "recipient_type", "recipient_id", "delivery_status", "archived_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_code = Column(String, unique=True)
    message_id = Column(Integer, ForeignKey("notification_messages.id"))
    recipient_type = Column(String)
    recipient_id = Column(Integer)
    channel = Column(String, default="in_app")
    delivery_status = Column(String, default="queued")
    read_status = Column(String, default="unread")
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    failed_reason = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Notification(Base):
    """旧通知表 —— 保留用于迁移兼容，新业务逻辑不再依赖此表。"""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_code = Column(String, unique=True)
    batch_id = Column(Integer, ForeignKey("notification_batches.id"))
    template_id = Column(Integer, ForeignKey("notification_templates.id"))
    recipient_reader_id = Column(Integer, ForeignKey("reader_accounts.id"))
    recipient_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    title = Column(String)
    content = Column(Text)
    notification_type = Column(String)
    channel = Column(String)
    status = Column(String)
    related_entity_type = Column(String)
    related_entity_id = Column(Integer)
    send_at = Column(DateTime)
    sent_at = Column(DateTime)
    read_at = Column(DateTime)
    failed_reason = Column(String)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class RiskWarning(Base):
    __tablename__ = "risk_warnings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_risk_id = Column(Integer)
    warning_code = Column(String, unique=True)
    warning_type = Column(String)
    severity = Column(String)
    module = Column(String)
    title = Column(String)
    description = Column(Text)
    status = Column(String)
    source_type = Column(String)
    related_entity_type = Column(String)
    related_entity_id = Column(Integer)
    suggested_action = Column(Text)
    created_task_id = Column(Integer, ForeignKey("work_tasks.id"))
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)
    resolved_at = Column(DateTime)


class RiskEvent(Base):
    __tablename__ = "risk_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    warning_id = Column(Integer, ForeignKey("risk_warnings.id"))
    event_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    detail = Column(Text)
    created_at = Column(DateTime, default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_code = Column(String, unique=True)
    actor_type = Column(String)
    actor_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_code = Column(String)
    actor_agent_run_id = Column(Integer, ForeignKey("agent_runs.id"))
    action = Column(String)
    target_entity_type = Column(String)
    target_entity_id = Column(Integer)
    result = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    request_id = Column(Integer)
    detail_json = Column(Text)
    created_at = Column(DateTime, default=now)


class ActionSnapshot(Base):
    __tablename__ = "action_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_code = Column(String, unique=True)
    audit_event_id = Column(Integer, ForeignKey("audit_events.id"))
    action_type = Column(String)
    target_entity_type = Column(String)
    target_entity_id = Column(Integer)
    before_json = Column(Text)
    after_json = Column(Text)
    can_rollback = Column(Boolean, default=False)
    rolled_back = Column(Boolean, default=False)
    rolled_back_by_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    rolled_back_at = Column(DateTime)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class ExportJob(Base):
    __tablename__ = "export_jobs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    export_code = Column(String, unique=True)
    export_type = Column(String)
    template_name = Column(String)
    requester_admin_id = Column(Integer, ForeignKey("admin_users.id"))
    status = Column(String)
    filter_json = Column(Text)
    file_path = Column(String)
    file_hash = Column(String)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=now)


# Relationships used by the existing service layer.
LibraryZone.shelves = relationship("Shelf", back_populates="zone")
Shelf.zone = relationship("LibraryZone", back_populates="shelves")
Shelf.positions = relationship("ShelfPosition", back_populates="shelf")
ShelfPosition.shelf = relationship("Shelf", back_populates="positions")
BookCategory.subcategories = relationship("BookSubcategory", back_populates="category")
BookSubcategory.category = relationship("BookCategory", back_populates="subcategories")
Book.category = relationship("BookCategory")
Book.subcategory = relationship("BookSubcategory")
Book.copies = relationship("BookCopy", back_populates="book")
BookCopy.book = relationship("Book", back_populates="copies")
BookCopy.shelf_position = relationship("ShelfPosition", foreign_keys=[BookCopy.current_position_id])
Loan.reader = relationship("ReaderAccount")
Loan.book = relationship("Book")
Loan.copy = relationship("BookCopy")
Reservation.reader = relationship("ReaderAccount")
Reservation.book = relationship("Book")
Reservation.copy = relationship("BookCopy", foreign_keys=[Reservation.fulfilled_copy_id])
OverdueCase.loan = relationship("Loan")
OverdueCase.reader = relationship("ReaderAccount")
OverdueCase.copy = relationship("BookCopy")
NotificationMessage.deliveries = relationship("NotificationDelivery", back_populates="message")
NotificationDelivery.message = relationship("NotificationMessage", back_populates="deliveries")
Notification.batch = relationship("NotificationBatch")
Notification.reader = relationship("ReaderAccount", foreign_keys=[Notification.recipient_reader_id])
Notification.admin = relationship("AdminUser", foreign_keys=[Notification.recipient_admin_id])

COPY_STATUSES = {"available", "borrowed", "reserved", "maintenance", "unavailable", "lost", "withdrawn"}
CIRCULATION_TYPES = {"hot", "normal", "cold"}

Index("ix_books_category_status", Book.category_id, Book.status)
Index("ix_books_title_author_code", Book.title, Book.author, Book.book_code)
Index("ix_book_copies_book_status", BookCopy.book_id, BookCopy.copy_status)
Index("ix_book_copies_position_status", BookCopy.current_position_id, BookCopy.copy_status)
Index("ix_loans_reader_status", Loan.reader_id, Loan.status)
Index("ix_loans_book_status", Loan.book_id, Loan.status)
Index("ix_loans_copy_status", Loan.copy_id, Loan.status)
Index("ix_reservations_reader_status", Reservation.reader_id, Reservation.status)
Index("ix_reservations_book_status", Reservation.book_id, Reservation.status)
Index("ix_work_tasks_status_group", WorkTask.status, WorkTask.task_group)
Index("ix_work_tasks_claimed_status", WorkTask.claimed_by_admin_id, WorkTask.status)
Index("ix_work_tasks_queue_lease", WorkTask.queue_name, WorkTask.status, WorkTask.lease_expires_at)
Index("ix_work_tasks_priority_score", WorkTask.status, WorkTask.priority_score)
Index("ix_ai_execution_ledger_task", AIExecutionLedger.task_code, AIExecutionLedger.phase, AIExecutionLedger.status)
Index("ix_ai_execution_ledger_target", AIExecutionLedger.target_type, AIExecutionLedger.target_id, AIExecutionLedger.tool_name)
Index("ix_notification_messages_type_lifecycle", NotificationMessage.notification_type, NotificationMessage.lifecycle_status)
Index("ix_notification_deliveries_msg_recipient", NotificationDelivery.message_id, NotificationDelivery.recipient_type, NotificationDelivery.recipient_id)
Index("ix_notifications_reader_status", Notification.recipient_reader_id, Notification.status)
Index("ix_notifications_admin_status", Notification.recipient_admin_id, Notification.status)
Index("ix_audit_events_action_created", AuditEvent.action, AuditEvent.created_at)
Index("ix_risk_warnings_status_severity", RiskWarning.status, RiskWarning.severity)

__all__ = [
    "Base", "LibraryProfile", "LibraryZone", "Shelf", "ShelfPosition", "SystemSetting", "DailyOperationMetric",
    "AnalyticsSnapshot", "DataImportBatch", "DataImportError", "BookCategory", "BookSubcategory", "Book",
    "BookSubjectTag", "BookSubjectRelation", "BookCopy", "BookCirculationStats", "CopyStatusEvent", "CopyLocationEvent",
    "SearchEvent", "ReaderAccount", "ReaderCredential", "ReaderLoginEvent", "ReaderVerificationCode", "ReaderStatusEvent",
    "ReaderCreditEvent", "ReaderStats", "ReaderNotificationSetting", "ReaderPreference", "CirculationRule", "CirculationPolicy", "Loan",
    "LoanEvent", "Reservation", "ReservationEvent", "CirculationServiceRequest", "OverdueCase", "AdminUser", "AdminRole", "AdminPermission",
    "AdminUserRole", "AdminRolePermission", "AdminLoginEvent", "WorkTask", "WorkTaskEvent", "AITaskCheckpoint", "AIExecutionLedger", "ReviewItem", "AICapability",
    "AIRule", "AIRuleVersion", "AIRuleExecutionLog", "AgentRun", "AgentStep",
    "AIApprovalRequest", "AIConversation", "AIChatMessage", "AITokenUsage", "AIMemoryItem", "AIObservation",
    "NotificationTemplate", "NotificationBatch", "NotificationMessage", "NotificationDelivery", "Notification", "RiskWarning", "RiskEvent", "AuditEvent",
    "ActionSnapshot", "ExportJob",
    "COPY_STATUSES", "CIRCULATION_TYPES",
]


