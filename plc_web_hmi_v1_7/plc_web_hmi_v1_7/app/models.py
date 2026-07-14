from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


SensorName = Literal["temperature", "humidity", "co2", "light"]


class TargetUpdate(BaseModel):
    temperature: float | None = Field(default=None, ge=-20, le=60)
    humidity: float | None = Field(default=None, ge=0, le=100)
    co2: float | None = Field(default=None, ge=0, le=10000)
    light: bool | None = None

    @model_validator(mode="after")
    def at_least_one_value(self):
        if all(
            value is None
            for value in (
                self.temperature,
                self.humidity,
                self.co2,
                self.light,
            )
        ):
            raise ValueError("至少提供一个目标值")
        return self


class ControlRequest(BaseModel):
    device: Literal["system", "compressor", "uv", "co2"]
    state: bool


class FanRequest(BaseModel):
    state: bool


class AlarmAcknowledgementRequest(BaseModel):
    plc_id: str = Field(min_length=1, max_length=64)


class AlarmBulkAcknowledgementRequest(BaseModel):
    plc_ids: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_plc_ids(self):
        self.plc_ids = list(dict.fromkeys(item.strip() for item in self.plc_ids if item.strip()))
        if not self.plc_ids:
            raise ValueError("至少需要提供一个 PLC 标识")
        return self


class CurveRequest(BaseModel):
    sensor: Literal["temperature", "humidity", "co2"]
    start_value: float
    end_value: float
    duration_seconds: float = Field(ge=5, le=86400)
    interval_seconds: float = Field(default=10, ge=1, le=3600)
    shape: Literal["linear", "smooth", "step"] = "linear"

    @model_validator(mode="after")
    def validate_interval(self):
        if self.interval_seconds > self.duration_seconds:
            raise ValueError("写入周期不能大于曲线持续时间")

        limits = {
            "temperature": (-20, 60),
            "humidity": (0, 100),
            "co2": (0, 10000),
        }
        low, high = limits[self.sensor]

        if not low <= self.start_value <= high:
            raise ValueError(f"起始值必须在 {low}～{high} 之间")
        if not low <= self.end_value <= high:
            raise ValueError(f"结束值必须在 {low}～{high} 之间")
        return self


class HistoryQueryRequest(BaseModel):
    start_timestamp: float
    end_timestamp: float
    interval_seconds: float = Field(default=10, ge=1, le=86400)
    sensors: list[SensorName] = Field(
        default_factory=lambda: [
            "temperature",
            "humidity",
            "co2",
            "light",
        ]
    )
    limit: int = Field(default=5000, ge=1, le=200000)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_timestamp <= self.start_timestamp:
            raise ValueError("结束时间必须晚于开始时间")
        if not self.sensors:
            raise ValueError("至少选择一个检测参数")

        # 去重并保持用户选择顺序。
        self.sensors = list(dict.fromkeys(self.sensors))
        return self
