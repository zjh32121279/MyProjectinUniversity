from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE_DB = BACKEND / "data" / "bookflow.db"


def _run_backend_script(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    db_path = tmp_path / "bookflow_ai_catalog_quality.db"
    shutil.copy2(SOURCE_DB, db_path)
    env = os.environ.copy()
    env["BOOKFLOW_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["PYTHONPATH"] = str(BACKEND) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-B", "-c", textwrap.dedent(script)],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )


def test_ai_catalog_search_handles_series_genre_and_near_miss_queries(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.ai_tools.catalog import ai_search_books
        from bookflow_core.core.database import ensure_schema, get_session

        ensure_schema()
        with get_session() as db:
            series = ai_search_books(db, {"keyword": "我记得三体还有后两部吧，怎么只有一本？", "limit": 5}, actor_id="pytest")
            series_titles = [item["title"] for item in series["items"]]
            assert series["series_base"] == "三体"
            assert series["series_continuation"] is True
            assert "三体Ⅱ：黑暗森林" in series_titles, series_titles
            assert "三体Ⅲ：死神永生" in series_titles, series_titles
            assert "三体" not in series_titles[:2], series_titles

            genre = ai_search_books(db, {"keyword": "馆内有多少科幻相关书籍？", "limit": 10}, actor_id="pytest")
            genre_titles = {item["title"] for item in genre["items"]}
            assert "三体" in genre_titles, genre_titles
            assert "活着" in genre_titles, genre_titles
            alive = next(item for item in genre["items"] if item["title"] == "活着")
            assert alive["metadata_only_match"] is True
            assert alive["notes"], alive
            assert "科幻" in genre["query_terms"], genre["query_terms"]

            local_history = ai_search_books(db, {"keyword": "有没有乡土志之类的", "limit": 5}, actor_id="pytest")
            local_titles = [item["title"] for item in local_history["items"]]
            assert "北京志" in local_titles, local_titles
            assert any(term in local_history["query_terms"] for term in ["地方志", "方志", "地方文献"]), local_history["query_terms"]

            empty = ai_search_books(db, {"keyword": "完全不存在的火星种植手册", "limit": 5}, actor_id="pytest")
            assert empty["items"] == []
            assert empty["empty_suggestions"], empty
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ai_tool_schema_descriptions_are_planner_readable(tmp_path: Path) -> None:
    result = _run_backend_script(
        tmp_path,
        """
        from bookflow_core.ai.tools.schema_builder import tool_schemas_for_llm
        from bookflow_core.core.database import ensure_schema, get_session

        ensure_schema()
        with get_session() as db:
            tools = {item["tool_name"]: item for item in tool_schemas_for_llm(db)}
            search = tools["ai_search_books"]
            assert "natural-language" in search["description"]
            assert "genre" in search["description"]
            assert not search["description"].startswith("Built-in BookFlow AI tool")
            assert "ai_get_loans" in tools
            assert "borrowing records" in tools["ai_get_loans"]["description"]
        """,
    )
    assert result.returncode == 0, result.stdout + result.stderr
