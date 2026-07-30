from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GpuProcess(BaseModel):
    pid: int
    name: str | None = None
    command: str | None = None
    used_memory_mb: float | None = None


class GpuInfo(BaseModel):
    index: int
    uuid: str | None = None
    name: str | None = None
    gpu_usage_percent: float | None = None
    memory_controller_usage_percent: float | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    memory_free_mb: float | None = None
    memory_usage_percent: float | None = None
    temperature_celsius: float | None = None
    power_usage_watts: float | None = None
    power_limit_watts: float | None = None
    fan_speed_percent: float | None = None
    graphics_clock_mhz: int | None = None
    memory_clock_mhz: int | None = None
    driver_version: str | None = None
    processes: list[GpuProcess] = Field(default_factory=list)


class HealthResponse(BaseModel):
    state: Literal["success"]
    message: str


class GpuListResponse(BaseModel):
    state: Literal["success", "unavailable"]
    timestamp: datetime
    message: str | None = None
    data: list[GpuInfo]


class GpuResponse(BaseModel):
    state: Literal["success"]
    timestamp: datetime
    data: GpuInfo


class ProcessListResponse(BaseModel):
    state: Literal["success"]
    timestamp: datetime
    data: list[GpuProcess]
