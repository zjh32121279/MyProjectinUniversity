from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsMetric(BaseModel):
    key: str = Field(description="Stable English metric key.")
    label: str = Field(description="Chinese display label.")
    value: int | float = 0
    unit: str = ""
    percentage: float | None = Field(default=None, description="Ratio in 0-1 form when applicable.")
    source: str = Field(default="real_time", description="real_time or daily_snapshot.")


class AnalyticsSeries(BaseModel):
    name: str
    label: str = ""
    data: list[int | float] = Field(default_factory=list)


class AnalyticsChart(BaseModel):
    labels: list[str] = Field(default_factory=list)
    series: list[AnalyticsSeries] = Field(default_factory=list)


class AnalyticsBucket(BaseModel):
    key: str = ""
    name: str
    label: str = ""
    count: int = 0
    percentage: float = 0


class AnalyticsPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    business_date: str = Field(default="", description="Unified business date used by the backend.")
    system_date: str = Field(default="", description="Actual server date.")
    metrics: list[AnalyticsMetric] = Field(default_factory=list)
