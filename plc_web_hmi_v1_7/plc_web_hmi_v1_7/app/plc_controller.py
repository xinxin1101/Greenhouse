from __future__ import annotations

import math
import random
import struct
import time
from dataclasses import dataclass
from typing import Any, Final

from .config import AppConfig


# ============================================================================
# 已确认点位
# ============================================================================

V_DB: Final[int] = 1

ACTUAL_TEMPERATURE_ADDR: Final[int] = 0       # VD0, REAL
SET_TEMPERATURE_FEEDBACK_ADDR: Final[int] = 32
ACTUAL_HUMIDITY_ADDR: Final[int] = 260        # VD260, REAL
SET_HUMIDITY_FEEDBACK_ADDR: Final[int] = 148
ACTUAL_CO2_ADDR: Final[int] = 240             # VD240, REAL
SET_CO2_FEEDBACK_ADDR: Final[int] = 1012

HIGH_TEMP_PROTECT_ADDR: Final[int] = 400
LOW_TEMP_PROTECT_ADDR: Final[int] = 404

# 环境第 1 段作为网页控制入口
TEMP_TARGET_ADDR: Final[int] = 264
HUMIDITY_TARGET_ADDR: Final[int] = 268
CO2_TARGET_ADDR: Final[int] = 600
LIGHT_TARGET_M_BYTE: Final[int] = 14
LIGHT_TARGET_BIT: Final[int] = 0

ENV_START_HOUR_ADDR: Final[int] = 4100
ENV_START_MINUTE_ADDR: Final[int] = 4500
ENV_END_HOUR_ADDR: Final[int] = 4102
ENV_END_MINUTE_ADDR: Final[int] = 4502
SELECTED_SEGMENT_ADDR: Final[int] = 4800

# 新风第 1 段全天有效
FAN_M_BYTE: Final[int] = 4
FAN_BIT: Final[int] = 0
FAN_START_HOUR_ADDR: Final[int] = 5102
FAN_START_MINUTE_ADDR: Final[int] = 5500
FAN_END_HOUR_ADDR: Final[int] = 5104
FAN_END_MINUTE_ADDR: Final[int] = 5502

RUN_STATUS_POINTS: Final[dict[str, tuple[str, int, int]]] = {
    "electric_heating": ("M", 1, 5),
    "compressor": ("Q", 0, 1),
    "circulation_fan": ("Q", 0, 3),
    "humidification": ("Q", 0, 4),
    "dehumidification": ("M", 27, 0),
    "fresh_air": ("Q", 0, 6),
    "lighting": ("Q", 0, 7),
    "uv": ("Q", 1, 0),
    "lamp_group": ("Q", 1, 1),
    "co2": ("Q", 0, 2),
}

# 1=正常，0=异常
ALARM_POINTS: Final[dict[str, tuple[int, int]]] = {
    "overload": (0, 0),
    "high_pressure": (0, 1),
    "low_pressure": (0, 2),
    "high_temperature": (0, 3),
}

CONTROL_POINTS: Final[dict[str, tuple[str, int, int]]] = {
    "system": ("M", 3, 6),
    "compressor": ("V", 10, 3),
    "uv": ("M", 3, 2),
    "co2": ("M", 28, 1),
}

TSAP_CANDIDATES: Final[tuple[tuple[int, int], ...]] = (
    (0x1000, 0x0200),
    (0x1000, 0x0201),
    (0x1000, 0x0300),
    (0x1000, 0x0301),
    (0x1000, 0x1000),
    (0x1000, 0x2000),
)


class ControllerError(RuntimeError):
    pass


class BaseController:
    mode = "unknown"

    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def poll(self) -> dict[str, Any]:
        raise NotImplementedError

    def prepare_env1(self) -> None:
        raise NotImplementedError

    def write_targets(self, values: dict[str, float | bool]) -> None:
        raise NotImplementedError

    def write_control(self, device: str, state: bool) -> None:
        raise NotImplementedError

    def prepare_and_write_fan(self, state: bool) -> None:
        raise NotImplementedError


class RealPLCController(BaseController):
    mode = "plc"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = None
        self.local_tsap: int | None = None
        self.remote_tsap: int | None = None

    def connect(self) -> None:
        try:
            import snap7
            from snap7.client import Client
            from snap7.error import check_error
            from snap7.type import Parameter
        except ImportError as exc:
            raise ControllerError(
                "未安装 python-snap7。请在 s7200_plc 环境执行："
                "python -m pip install python-snap7==2.1.0"
            ) from exc

        self.disconnect()
        last_error: Exception | None = None

        for local_tsap, remote_tsap in TSAP_CANDIDATES:
            client = Client()
            try:
                client.set_param(Parameter.RemotePort, self.config.plc_port)
                client.set_connection_params(
                    self.config.plc_ip,
                    local_tsap,
                    remote_tsap,
                )
                result = client._lib.Cli_Connect(client._s7_client)
                check_error(result, context="client")

                if not client.get_connected():
                    raise ControllerError("Snap7 未进入已连接状态")

                self.client = client
                self.local_tsap = local_tsap
                self.remote_tsap = remote_tsap
                return
            except Exception as exc:
                last_error = exc
                try:
                    client.disconnect()
                except Exception:
                    pass
                try:
                    client.destroy()
                except Exception:
                    pass
                time.sleep(0.25)

        raise ControllerError(f"PLC S7 连接失败：{last_error}")

    def disconnect(self) -> None:
        if self.client is None:
            return
        try:
            self.client.disconnect()
        except Exception:
            pass
        try:
            self.client.destroy()
        except Exception:
            pass
        self.client = None
        self.local_tsap = None
        self.remote_tsap = None

    def _require_client(self):
        if self.client is None or not self.client.get_connected():
            raise ControllerError("PLC 当前未连接")
        return self.client

    def _read_real(self, address: int) -> float:
        client = self._require_client()
        data = bytes(client.db_read(V_DB, address, 4))
        if len(data) != 4:
            raise ControllerError(f"VD{address} 读取长度异常")
        return struct.unpack(">f", data)[0]

    def _write_real(self, address: int, value: float) -> None:
        client = self._require_client()
        expected = float(value)
        client.db_write(V_DB, address, bytearray(struct.pack(">f", expected)))
        time.sleep(0.05)
        actual = self._read_real(address)
        tolerance = max(1e-5, abs(expected) * 1e-6)
        if abs(actual - expected) > tolerance:
            raise ControllerError(
                f"VD{address} 写入校验失败：目标={expected}，回读={actual}"
            )

    def _read_word(self, address: int) -> int:
        client = self._require_client()
        data = bytes(client.db_read(V_DB, address, 2))
        if len(data) != 2:
            raise ControllerError(f"VW{address} 读取长度异常")
        return struct.unpack(">H", data)[0]

    def _write_word(self, address: int, value: int) -> None:
        client = self._require_client()
        client.db_write(V_DB, address, bytearray(struct.pack(">H", value)))
        time.sleep(0.03)
        if self._read_word(address) != value:
            raise ControllerError(f"VW{address} 写入校验失败")

    def _read_byte(self, address: int) -> int:
        client = self._require_client()
        data = bytes(client.db_read(V_DB, address, 1))
        if len(data) != 1:
            raise ControllerError(f"VB{address} 读取长度异常")
        return data[0]

    def _write_byte(self, address: int, value: int) -> None:
        client = self._require_client()
        client.db_write(V_DB, address, bytearray([value]))
        time.sleep(0.03)
        if self._read_byte(address) != value:
            raise ControllerError(f"VB{address} 写入校验失败")

    def _read_m_byte(self, address: int) -> int:
        client = self._require_client()
        data = bytes(client.mb_read(address, 1))
        if len(data) != 1:
            raise ControllerError(f"MB{address} 读取长度异常")
        return data[0]

    def _write_m_byte(self, address: int, value: int) -> None:
        client = self._require_client()
        client.mb_write(address, 1, bytearray([value]))
        time.sleep(0.03)
        if self._read_m_byte(address) != value:
            raise ControllerError(f"MB{address} 写入校验失败")

    def _read_m_bit(self, address: int, bit: int) -> bool:
        return bool(self._read_m_byte(address) & (1 << bit))

    def _write_m_bit(self, address: int, bit: int, state: bool) -> None:
        """
        采用“读整字节、改目标位、写整字节、仅回读目标位”的方式。

        不校验整个 MB 字节，因为 PLC 程序可能在写入后的几十毫秒内改变
        同一字节中的其他位。若校验整个字节，会把目标位已经成功写入的情况
        错误判断为失败。
        """
        client = self._require_client()
        last_actual: bool | None = None

        for attempt in range(1, 4):
            current = self._read_m_byte(address)
            updated = (
                current | (1 << bit)
                if state
                else current & ~(1 << bit)
            )

            client.mb_write(address, 1, bytearray([updated]))
            time.sleep(0.08)

            last_actual = self._read_m_bit(address, bit)
            if last_actual == state:
                return

            time.sleep(0.12 * attempt)

        raise ControllerError(
            f"M{address}.{bit} 写入校验失败："
            f"目标={int(state)}，回读={int(bool(last_actual))}"
        )

    def _read_v_bit(self, address: int, bit: int) -> bool:
        return bool(self._read_byte(address) & (1 << bit))

    def _write_v_bit(self, address: int, bit: int, state: bool) -> None:
        """
        V 位写入同样只校验目标位，并进行最多三次重试。
        """
        client = self._require_client()
        last_actual: bool | None = None

        for attempt in range(1, 4):
            current = self._read_byte(address)
            updated = (
                current | (1 << bit)
                if state
                else current & ~(1 << bit)
            )

            client.db_write(V_DB, address, bytearray([updated]))
            time.sleep(0.08)

            last_actual = self._read_v_bit(address, bit)
            if last_actual == state:
                return

            time.sleep(0.12 * attempt)

        raise ControllerError(
            f"V{address}.{bit} 写入校验失败："
            f"目标={int(state)}，回读={int(bool(last_actual))}"
        )

    def _read_output_bytes(self) -> bytes:
        client = self._require_client()
        data = bytes(client.ab_read(0, 2))
        if len(data) != 2:
            raise ControllerError("Q0～Q1 读取长度异常")
        return data

    def _read_input_byte(self) -> int:
        client = self._require_client()
        data = bytes(client.eb_read(0, 1))
        if len(data) != 1:
            raise ControllerError("I0 读取长度异常")
        return data[0]

    @staticmethod
    def _bit(value: int, bit: int) -> bool:
        return bool(value & (1 << bit))

    def poll(self) -> dict[str, Any]:
        outputs = self._read_output_bytes()
        input0 = self._read_input_byte()

        m1 = self._read_m_byte(1)
        m27 = self._read_m_byte(27)
        m3 = self._read_m_byte(3)
        m28 = self._read_m_byte(28)
        m14 = self._read_m_byte(14)
        m4 = self._read_m_byte(4)
        v10 = self._read_byte(10)

        run_status = {
            "electric_heating": self._bit(m1, 5),
            "compressor": self._bit(outputs[0], 1),
            "circulation_fan": self._bit(outputs[0], 3),
            "humidification": self._bit(outputs[0], 4),
            "dehumidification": self._bit(m27, 0),
            "fresh_air": self._bit(outputs[0], 6),
            "lighting": self._bit(outputs[0], 7),
            "uv": self._bit(outputs[1], 0),
            "lamp_group": self._bit(outputs[1], 1),
            "co2": self._bit(outputs[0], 2),
        }

        alarms = {
            name: {
                "raw": self._bit(input0, bit),
                "active": not self._bit(input0, bit),
            }
            for name, (_, bit) in ALARM_POINTS.items()
        }

        controls = {
            "system": self._bit(m3, 6),
            "compressor": self._bit(v10, 3),
            "uv": self._bit(m3, 2),
            "co2": self._bit(m28, 1),
            "fresh_air": self._bit(m4, 0),
            "lamp": self._bit(m14, 0),
        }

        return {
            "connected": True,
            "mode": self.mode,
            "plc_ip": self.config.plc_ip,
            "tsap": {
                "local": f"0x{self.local_tsap:04X}" if self.local_tsap is not None else None,
                "remote": f"0x{self.remote_tsap:04X}" if self.remote_tsap is not None else None,
            },
            "measurements": {
                "temperature": self._read_real(ACTUAL_TEMPERATURE_ADDR),
                "humidity": self._read_real(ACTUAL_HUMIDITY_ADDR),
                "co2": self._read_real(ACTUAL_CO2_ADDR),
                "light": 1.0 if run_status["lamp_group"] else 0.0,
            },
            "targets": {
                "temperature": self._read_real(TEMP_TARGET_ADDR),
                "humidity": self._read_real(HUMIDITY_TARGET_ADDR),
                "co2": self._read_real(CO2_TARGET_ADDR),
                "light": 1.0 if controls["lamp"] else 0.0,
            },
            "feedback": {
                "temperature": self._read_real(SET_TEMPERATURE_FEEDBACK_ADDR),
                "humidity": self._read_real(SET_HUMIDITY_FEEDBACK_ADDR),
                "co2": self._read_real(SET_CO2_FEEDBACK_ADDR),
            },
            "protection": {
                "high_temperature": self._read_real(HIGH_TEMP_PROTECT_ADDR),
                "low_temperature": self._read_real(LOW_TEMP_PROTECT_ADDR),
                "compressor_restart_delay_seconds": 180,
            },
            "run_status": run_status,
            "controls": controls,
            "alarms": alarms,
        }

    def prepare_env1(self) -> None:
        self._write_word(ENV_START_HOUR_ADDR, 0)
        self._write_word(ENV_START_MINUTE_ADDR, 0)
        self._write_word(ENV_END_HOUR_ADDR, 0)
        self._write_word(ENV_END_MINUTE_ADDR, 0)
        self._write_byte(SELECTED_SEGMENT_ADDR, 1)

    def write_targets(self, values: dict[str, float | bool]) -> None:
        if "temperature" in values:
            self._write_real(TEMP_TARGET_ADDR, float(values["temperature"]))
        if "humidity" in values:
            self._write_real(HUMIDITY_TARGET_ADDR, float(values["humidity"]))
        if "co2" in values:
            self._write_real(CO2_TARGET_ADDR, float(values["co2"]))
        if "light" in values:
            self._write_m_bit(LIGHT_TARGET_M_BYTE, LIGHT_TARGET_BIT, bool(values["light"]))

    def write_control(self, device: str, state: bool) -> None:
        if device not in CONTROL_POINTS:
            raise ControllerError(f"未知控制对象：{device}")
        area, address, bit = CONTROL_POINTS[device]
        if area == "M":
            self._write_m_bit(address, bit, state)
        elif area == "V":
            self._write_v_bit(address, bit, state)
        else:
            raise ControllerError("禁止直接写 Q/I 点位")

    def prepare_and_write_fan(self, state: bool) -> None:
        # 先清除第 2～8 段，保留第 1 段由后面设置。
        self._write_m_byte(FAN_M_BYTE, 0)
        self._write_word(FAN_START_HOUR_ADDR, 0)
        self._write_word(FAN_START_MINUTE_ADDR, 0)
        self._write_word(FAN_END_HOUR_ADDR, 0)
        self._write_word(FAN_END_MINUTE_ADDR, 0)
        self._write_m_bit(FAN_M_BYTE, FAN_BIT, state)


class SimulationController(BaseController):
    mode = "simulation"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.connected = False
        self.values = {
            "temperature": 26.2,
            "humidity": 80.0,
            "co2": 780.0,
            "light": 0.0,
        }
        self.targets = {
            "temperature": 25.0,
            "humidity": 60.0,
            "co2": 800.0,
            "light": 0.0,
        }
        self.controls = {
            "system": False,
            "compressor": False,
            "uv": False,
            "co2": True,
            "fresh_air": False,
            "lamp": False,
        }
        self.started_at = time.monotonic()

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def poll(self) -> dict[str, Any]:
        if not self.connected:
            raise ControllerError("模拟器未连接")

        for name in ("temperature", "humidity", "co2"):
            speed = {"temperature": 0.08, "humidity": 0.05, "co2": 0.07}[name]
            noise = {"temperature": 0.03, "humidity": 0.08, "co2": 1.8}[name]
            self.values[name] += (self.targets[name] - self.values[name]) * speed
            self.values[name] += random.gauss(0, noise)

        self.values["light"] = 1.0 if self.controls["lamp"] else 0.0

        elapsed = time.monotonic() - self.started_at
        alarm_active = {
            "overload": False,
            "high_pressure": False,
            "low_pressure": False,
            "high_temperature": self.values["temperature"] > 55,
        }

        run_status = {
            "electric_heating": self.controls["system"] and self.values["temperature"] < self.targets["temperature"],
            "compressor": self.controls["compressor"],
            "circulation_fan": self.controls["system"],
            "humidification": self.controls["system"] and self.values["humidity"] < self.targets["humidity"],
            "dehumidification": self.controls["system"] and self.values["humidity"] > self.targets["humidity"],
            "fresh_air": self.controls["fresh_air"],
            "lighting": self.controls["system"],
            "uv": self.controls["uv"],
            "lamp_group": self.controls["lamp"],
            "co2": self.controls["co2"],
        }

        return {
            "connected": True,
            "mode": self.mode,
            "plc_ip": self.config.plc_ip,
            "tsap": {"local": "SIM", "remote": "SIM"},
            "measurements": dict(self.values),
            "targets": dict(self.targets),
            "feedback": {
                "temperature": self.targets["temperature"],
                "humidity": self.targets["humidity"],
                "co2": self.targets["co2"],
            },
            "protection": {
                "high_temperature": 55.0,
                "low_temperature": -1.0,
                "compressor_restart_delay_seconds": 180,
            },
            "run_status": run_status,
            "controls": dict(self.controls),
            "alarms": {
                name: {"raw": not active, "active": active}
                for name, active in alarm_active.items()
            },
            "simulation_elapsed": elapsed,
        }

    def prepare_env1(self) -> None:
        return

    def write_targets(self, values: dict[str, float | bool]) -> None:
        for name, value in values.items():
            if name == "light":
                self.targets[name] = 1.0 if bool(value) else 0.0
                self.controls["lamp"] = bool(value)
            else:
                self.targets[name] = float(value)

    def write_control(self, device: str, state: bool) -> None:
        if device not in {"system", "compressor", "uv", "co2"}:
            raise ControllerError(f"未知控制对象：{device}")
        self.controls[device] = state

    def prepare_and_write_fan(self, state: bool) -> None:
        self.controls["fresh_air"] = state


def create_controller(config: AppConfig) -> BaseController:
    if config.mode == "simulation":
        return SimulationController(config)
    return RealPLCController(config)
