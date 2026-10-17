from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from bookflow_core.core.time import now, today
from bookflow_core.models import DailyOperationMetric, LibraryProfile, SystemSetting
from bookflow_core.services.common import write_audit


def _get_or_create_profile(db: Session) -> LibraryProfile:
    """Fetch the first LibraryProfile row or create one if none exists."""
    profile = db.scalar(select(LibraryProfile).order_by(LibraryProfile.id))
    if not profile:
        profile = LibraryProfile(library_code="MAIN", library_name="")
        db.add(profile)
        db.flush()
    return profile


def update_library_profile(
    db: Session,
    *,
    library_name: str | None = None,
    library_type: str | None = None,
    service_population: str | None = None,
    building_area_sqm: float | None = None,
    open_floors: str | None = None,
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> LibraryProfile:
    """Update the library profile (basic info fields). Only non-None fields are applied."""
    try:
        profile = _get_or_create_profile(db)
        before = {
            "library_name": profile.library_name,
            "library_type": profile.library_type,
            "service_population": profile.service_population,
            "building_area_sqm": profile.building_area_sqm,
            "open_floors": profile.open_floors,
        }

        if library_name is not None:
            profile.library_name = library_name
        if library_type is not None:
            profile.library_type = library_type
        if service_population is not None:
            profile.service_population = service_population
        if building_area_sqm is not None:
            profile.building_area_sqm = building_area_sqm
        if open_floors is not None:
            profile.open_floors = open_floors

        profile.updated_at = now()
        after = {
            "library_name": profile.library_name,
            "library_type": profile.library_type,
            "service_population": profile.service_population,
            "building_area_sqm": profile.building_area_sqm,
            "open_floors": profile.open_floors,
        }

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="update_library_profile",
            target_table="library_profiles",
            target_id=str(profile.id),
            detail={"before": before, "after": after},
        )

        if commit:
            db.commit()
            db.refresh(profile)
        return profile
    except Exception:
        if commit:
            db.rollback()
        raise


def update_library_space_config(
    db: Session,
    *,
    zone_count: int | None = None,
    shelf_count: int | None = None,
    reservation_shelf_count: int | None = None,
    turnover_shelf_count: int | None = None,
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> LibraryProfile:
    """Update library space configuration counts.

    ``shelf_count`` is stored directly on the LibraryProfile row (consistent with
    the dashboard query).  ``zone_count``, ``reservation_shelf_count`` and
    ``turnover_shelf_count`` are written as ``DailyOperationMetric`` rows so that
    the existing ``_metric_value`` reader picks them up.
    """
    try:
        profile = _get_or_create_profile(db)
        metric_date = today()
        before = {
            "zone_count": _metric_read(db, "zone_count"),
            "shelf_count": profile.shelf_count,
            "reservation_shelf_count": _metric_read(db, "reservation_shelf_count"),
            "turnover_shelf_count": _metric_read(db, "turnover_shelf_count"),
        }

        date_str = str(metric_date)
        _upsert_metric(db, "zone_count", zone_count, date_str)
        _upsert_metric(db, "reservation_shelf_count", reservation_shelf_count, date_str)
        _upsert_metric(db, "turnover_shelf_count", turnover_shelf_count, date_str)

        if shelf_count is not None:
            profile.shelf_count = shelf_count

        profile.updated_at = now()
        after = {
            "zone_count": _metric_read(db, "zone_count"),
            "shelf_count": profile.shelf_count,
            "reservation_shelf_count": _metric_read(db, "reservation_shelf_count"),
            "turnover_shelf_count": _metric_read(db, "turnover_shelf_count"),
        }

        write_audit(
            db,
            actor_type=actor_type,
            actor_id=actor_id,
            action="update_library_space_config",
            target_table="library_profiles",
            target_id=str(profile.id),
            detail={"before": before, "after": after},
        )

        if commit:
            db.commit()
            db.refresh(profile)
        return profile
    except Exception:
        if commit:
            db.rollback()
        raise


def _metric_read(db: Session, key: str) -> int:
    """Read the latest value for a metric key from the daily table (for audit)."""
    from bookflow_core.services.statistics_service import operation_metric_value

    return operation_metric_value(db, key, 0)


def _upsert_metric(
    db: Session,
    key: str,
    value: int | None,
    metric_date: str,
) -> None:
    """Write (or update) a metric value into the daily_operation_metrics table."""
    if value is None:
        return
    row = db.scalar(
        select(DailyOperationMetric).where(
            DailyOperationMetric.metric_key == key,
            DailyOperationMetric.metric_date == metric_date,
        )
    )
    if row:
        row.metric_value = str(value)
        row.updated_at = now()
    else:
        row = DailyOperationMetric(
            metric_date=metric_date,
            metric_key=key,
            metric_value=str(value),
            metric_unit="count",
            created_at=now(),
            updated_at=now(),
        )
        db.add(row)


def batch_update_system_settings(
    db: Session,
    *,
    settings: dict[str, str],
    actor_type: str = "admin",
    actor_id: str = "admin",
    commit: bool = True,
) -> list[dict]:
    """Batch-upsert multiple SystemSetting rows in a single transaction."""
    from bookflow_core.services.rule_service import update_system_setting

    results: list[dict] = []
    try:
        for key, value in settings.items():
            row = update_system_setting(
                db,
                key,
                value=value,
                actor_type=actor_type,
                actor_id=actor_id,
                commit=False,
            )
            results.append({
                "key": row.setting_key,
                "value": row.setting_value,
                "value_type": row.value_type,
            })
        if commit:
            db.commit()
        return results
    except Exception:
        if commit:
            db.rollback()
        raise
