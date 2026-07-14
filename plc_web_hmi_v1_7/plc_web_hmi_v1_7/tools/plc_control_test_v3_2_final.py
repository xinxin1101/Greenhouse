from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Final

import snap7
from snap7.client import Client
from snap7.error import check_error
from snap7.type import Parameter


# ============================================================
# 1. PLC 连接配置
# ============================================================

PLC_IP: Final[str] = "192.168.2.1"
PLC_PORT: Final[int] = 102
V_DB: Final[int] = 1

TSAP_CANDIDATES: Final[tuple[tuple[int, int], ...]] = (
    (0x1000, 0x0200),
    (0x1000, 0x0201),
    (0x1000, 0x0300),
    (0x1000, 0x0301),
    (0x1000, 0x1000),
    (0x1000, 0x2000),
)


# ============================================================
# 2. 实时测量值、设定值及停机等待时间
# ============================================================

ACTUAL_TEMPERATURE_ADDR: Final[int] = 0       # VD0, REAL
# 以下三个“设定值”点位用于监控反馈，由 PLC 程序计算/刷新，不作为上位机写入口。
SET_TEMPERATURE_ADDR: Final[int] = 32         # VD32, REAL，只读反馈
ACTUAL_HUMIDITY_ADDR: Final[int] = 260        # VD260, REAL
SET_HUMIDITY_ADDR: Final[int] = 148           # VD148, REAL，只读反馈
ACTUAL_CO2_ADDR: Final[int] = 240             # VD240, REAL
SET_CO2_ADDR: Final[int] = 1012               # VD1012, REAL，只读反馈

HIGH_TEMP_PROTECT_ADDR: Final[int] = 400       # VD400, REAL
LOW_TEMP_PROTECT_ADDR: Final[int] = 404        # VD404, REAL


# ============================================================
# 3. 运行状态，只读
# ============================================================

# 格式：名称 -> (区域, 字节地址, 位)
# M = 标志位，Q = 输出状态
RUN_STATUS_POINTS: Final[dict[str, tuple[str, int, int]]] = {
    "electric_heating": ("M", 1, 5),   # M1.5 电加热
    "compressor": ("Q", 0, 1),         # Q0.1 压机
    "circulation_fan": ("Q", 0, 3),    # Q0.3 风机
    "humidification": ("Q", 0, 4),     # Q0.4 加湿
    "dehumidification": ("M", 27, 0),  # M27.0 除湿
    "fresh_air": ("Q", 0, 6),          # Q0.6 新风
    "lighting": ("Q", 0, 7),           # Q0.7 照明
    "uv": ("Q", 1, 0),                 # Q1.0 紫外
    "lamp_group": ("Q", 1, 1),         # Q1.1 灯组
    "co2": ("Q", 0, 2),                # Q0.2 CO₂
}

RUN_STATUS_LABELS: Final[dict[str, str]] = {
    "electric_heating": "电加热",
    "compressor": "压机",
    "circulation_fan": "循环风机",
    "humidification": "加湿",
    "dehumidification": "除湿",
    "fresh_air": "新风",
    "lighting": "照明",
    "uv": "紫外",
    "lamp_group": "灯组",
    "co2": "CO₂",
}


# ============================================================
# 4. 报警输入，只读
# ============================================================

ALARM_POINTS: Final[dict[str, tuple[int, int]]] = {
    "overload": (0, 0),        # I0.0 过载
    "high_pressure": (0, 1),   # I0.1 压缩机高压
    "low_pressure": (0, 2),    # I0.2 压缩机低压
    "high_temperature": (0, 3),# I0.3 高温
}

ALARM_LABELS: Final[dict[str, str]] = {
    "overload": "过载",
    "high_pressure": "压缩机高压",
    "low_pressure": "压缩机低压",
    "high_temperature": "高温",
}


# ============================================================
# 5. 控制位，0=关，1=开
# ============================================================

# system：除压机、紫外、CO₂以外设备的总控制
# compressor、uv、co2：三个独立控制开关
CONTROL_POINTS: Final[dict[str, tuple[str, int, int]]] = {
    "system": ("M", 3, 6),       # M3.6 关机/系统控制
    "compressor": ("V", 10, 3),  # V10.3 压机
    "uv": ("M", 3, 2),           # M3.2 紫外
    "co2": ("M", 28, 1),         # M28.1 CO₂控制
}

CONTROL_LABELS: Final[dict[str, str]] = {
    "system": "系统总控制（不含压机、紫外、CO₂）",
    "compressor": "压机独立控制",
    "uv": "紫外独立控制",
    "co2": "CO₂独立控制",
}


# ============================================================
# 6. 环境分段控制
# ============================================================

TEMP_ADDRS: Final[tuple[int, ...]] = (
    264, 272, 280, 288, 296, 304, 312, 320
)
HUMIDITY_ADDRS: Final[tuple[int, ...]] = (
    268, 276, 284, 292, 300, 308, 316, 324
)
CO2_ADDRS: Final[tuple[int, ...]] = (
    600, 604, 608, 612, 616, 620, 624, 628
)

ENV_LIGHT_M_BYTE: Final[int] = 14  # M14.0～M14.7

ENV_START_HOUR_ADDRS: Final[tuple[int, ...]] = tuple(
    4100 + 2 * i for i in range(8)
)
ENV_START_MINUTE_ADDRS: Final[tuple[int, ...]] = tuple(
    4500 + 2 * i for i in range(8)
)
ENV_END_HOUR_ADDRS: Final[tuple[int, ...]] = tuple(
    4102 + 2 * i for i in range(8)
)
ENV_END_MINUTE_ADDRS: Final[tuple[int, ...]] = tuple(
    4502 + 2 * i for i in range(8)
)

SELECTED_SEGMENT_ADDR: Final[int] = 4800  # VB4800，1～8


# ============================================================
# 7. 新风分段控制
# ============================================================

FAN_M_BYTE: Final[int] = 4  # M4.0～M4.7

FAN_START_HOUR_ADDRS: Final[tuple[int, ...]] = (
    5102, 5106, 5110, 5114, 5118, 5122, 5126, 5130
)
FAN_START_MINUTE_ADDRS: Final[tuple[int, ...]] = (
    5500, 5504, 5508, 5512, 5516, 5520, 5524, 5528
)
FAN_END_HOUR_ADDRS: Final[tuple[int, ...]] = (
    5104, 5108, 5112, 5116, 5120, 5124, 5128, 5132
)
FAN_END_MINUTE_ADDRS: Final[tuple[int, ...]] = (
    5502, 5506, 5510, 5514, 5518, 5522, 5526, 5530
)


# ============================================================
# 8. 连接
# ============================================================

def safe_disconnect(client: Client | None) -> None:
    if client is None:
        return

    try:
        client.disconnect()
    except Exception:
        pass

    try:
        client.destroy()
    except Exception:
        pass


def connect_with_tsap(local_tsap: int, remote_tsap: int) -> Client:
    client = Client()

    try:
        client.set_param(Parameter.RemotePort, PLC_PORT)
        client.set_connection_params(
            PLC_IP,
            local_tsap,
            remote_tsap,
        )

        result = client._lib.Cli_Connect(client._s7_client)
        check_error(result, context="client")

        if not client.get_connected():
            raise ConnectionError("Snap7 未进入已连接状态")

        return client

    except Exception:
        safe_disconnect(client)
        raise


def connect_plc() -> tuple[Client, int, int]:
    print("=" * 82)
    print(f"正在连接 PLC：{PLC_IP}:{PLC_PORT}")
    print(f"Python：{sys.executable}")
    print(f"python-snap7：{snap7.__version__}")

    last_error: Exception | None = None

    for index, (local_tsap, remote_tsap) in enumerate(
        TSAP_CANDIDATES,
        start=1,
    ):
        print(
            f"[{index}/{len(TSAP_CANDIDATES)}] "
            f"Local=0x{local_tsap:04X}, "
            f"Remote=0x{remote_tsap:04X}"
        )

        try:
            client = connect_with_tsap(local_tsap, remote_tsap)
            print("S7 连接成功")
            return client, local_tsap, remote_tsap
        except Exception as exc:
            last_error = exc
            print(f"连接失败：{exc}")
            time.sleep(0.8)

    raise ConnectionError(
        f"全部 TSAP 连接失败，最后错误：{last_error}"
    )


# ============================================================
# 9. 基础读写
# ============================================================

def read_real(client: Client, address: int) -> float:
    data = bytes(client.db_read(V_DB, address, 4))
    if len(data) != 4:
        raise RuntimeError(f"VD{address} 读取长度不是 4 字节")
    return struct.unpack(">f", data)[0]


def write_real(client: Client, address: int, value: float) -> float:
    expected = float(value)
    client.db_write(
        V_DB,
        address,
        bytearray(struct.pack(">f", expected)),
    )

    time.sleep(0.08)
    actual = read_real(client, address)
    tolerance = max(1e-5, abs(expected) * 1e-6)

    if abs(actual - expected) > tolerance:
        raise RuntimeError(
            f"VD{address} 写入校验失败："
            f"目标={expected}，回读={actual}"
        )

    return actual


def read_word(client: Client, address: int) -> int:
    data = bytes(client.db_read(V_DB, address, 2))
    if len(data) != 2:
        raise RuntimeError(f"VW{address} 读取长度不是 2 字节")
    return struct.unpack(">H", data)[0]


def write_word(client: Client, address: int, value: int) -> int:
    if not 0 <= value <= 65535:
        raise ValueError("WORD 必须在 0～65535 之间")

    client.db_write(
        V_DB,
        address,
        bytearray(struct.pack(">H", value)),
    )

    time.sleep(0.08)
    actual = read_word(client, address)

    if actual != value:
        raise RuntimeError(
            f"VW{address} 写入校验失败："
            f"目标={value}，回读={actual}"
        )

    return actual


def read_byte(client: Client, address: int) -> int:
    data = bytes(client.db_read(V_DB, address, 1))
    if len(data) != 1:
        raise RuntimeError(f"VB{address} 读取长度不是 1 字节")
    return data[0]


def write_byte(client: Client, address: int, value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError("BYTE 必须在 0～255 之间")

    client.db_write(V_DB, address, bytearray([value]))
    time.sleep(0.08)
    actual = read_byte(client, address)

    if actual != value:
        raise RuntimeError(
            f"VB{address} 写入校验失败："
            f"目标={value}，回读={actual}"
        )

    return actual


def read_m_byte(client: Client, byte_address: int) -> int:
    data = bytes(client.mb_read(byte_address, 1))
    if len(data) != 1:
        raise RuntimeError(f"MB{byte_address} 读取长度不是 1 字节")
    return data[0]


def write_m_byte(client: Client, byte_address: int, value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError("M 字节必须在 0～255 之间")

    client.mb_write(byte_address, 1, bytearray([value]))
    time.sleep(0.08)
    actual = read_m_byte(client, byte_address)

    if actual != value:
        raise RuntimeError(
            f"MB{byte_address} 写入校验失败："
            f"目标=0x{value:02X}，回读=0x{actual:02X}"
        )

    return actual


def read_m_bit(client: Client, byte_address: int, bit: int) -> bool:
    return bool(read_m_byte(client, byte_address) & (1 << bit))


def write_m_bit(
    client: Client,
    byte_address: int,
    bit: int,
    value: bool,
) -> bool:
    data = client.mb_read(byte_address, 1)
    current = data[0]

    if value:
        data[0] = current | (1 << bit)
    else:
        data[0] = current & ~(1 << bit)

    client.mb_write(byte_address, 1, data)
    time.sleep(0.08)
    actual = read_m_bit(client, byte_address, bit)

    if actual != value:
        raise RuntimeError(
            f"M{byte_address}.{bit} 写入校验失败："
            f"目标={int(value)}，回读={int(actual)}"
        )

    return actual


def read_v_bit(client: Client, byte_address: int, bit: int) -> bool:
    value = read_byte(client, byte_address)
    return bool(value & (1 << bit))


def write_v_bit(
    client: Client,
    byte_address: int,
    bit: int,
    value: bool,
) -> bool:
    current = read_byte(client, byte_address)

    if value:
        updated = current | (1 << bit)
    else:
        updated = current & ~(1 << bit)

    write_byte(client, byte_address, updated)
    actual = read_v_bit(client, byte_address, bit)

    if actual != value:
        raise RuntimeError(
            f"V{byte_address}.{bit} 写入校验失败："
            f"目标={int(value)}，回读={int(actual)}"
        )

    return actual


def read_output_byte(client: Client, byte_address: int) -> int:
    data = bytes(client.ab_read(byte_address, 1))
    if len(data) != 1:
        raise RuntimeError(f"QB{byte_address} 读取长度不是 1 字节")
    return data[0]


def read_output_bit(client: Client, byte_address: int, bit: int) -> bool:
    return bool(read_output_byte(client, byte_address) & (1 << bit))


def read_input_byte(client: Client, byte_address: int) -> int:
    data = bytes(client.eb_read(byte_address, 1))
    if len(data) != 1:
        raise RuntimeError(f"IB{byte_address} 读取长度不是 1 字节")
    return data[0]


def read_input_bit(client: Client, byte_address: int, bit: int) -> bool:
    return bool(read_input_byte(client, byte_address) & (1 << bit))


def read_named_bit(
    client: Client,
    area: str,
    byte_address: int,
    bit: int,
) -> bool:
    if area == "M":
        return read_m_bit(client, byte_address, bit)
    if area == "V":
        return read_v_bit(client, byte_address, bit)
    if area == "Q":
        return read_output_bit(client, byte_address, bit)
    if area == "I":
        return read_input_bit(client, byte_address, bit)

    raise ValueError(f"未知区域：{area}")


def write_control_bit(
    client: Client,
    area: str,
    byte_address: int,
    bit: int,
    value: bool,
) -> bool:
    if area == "M":
        return write_m_bit(client, byte_address, bit, value)
    if area == "V":
        return write_v_bit(client, byte_address, bit, value)

    raise ValueError(
        "控制命令仅允许写 M 或 V 点位，不允许直接写 Q/I"
    )


# ============================================================
# 10. 快照
# ============================================================

def collect_monitor_snapshot(client: Client) -> dict:
    run_status = {}
    for name, (area, byte_address, bit) in RUN_STATUS_POINTS.items():
        run_status[name] = read_named_bit(
            client, area, byte_address, bit
        )

    alarms = {}
    for name, (byte_address, bit) in ALARM_POINTS.items():
        alarms[name] = read_input_bit(client, byte_address, bit)

    controls = {}
    for name, (area, byte_address, bit) in CONTROL_POINTS.items():
        controls[name] = read_named_bit(
            client, area, byte_address, bit
        )

    return {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "measurements": {
            "actual_temperature": read_real(
                client, ACTUAL_TEMPERATURE_ADDR
            ),
            "set_temperature": read_real(
                client, SET_TEMPERATURE_ADDR
            ),
            "actual_humidity": read_real(
                client, ACTUAL_HUMIDITY_ADDR
            ),
            "set_humidity": read_real(
                client, SET_HUMIDITY_ADDR
            ),
            "actual_co2": read_real(
                client, ACTUAL_CO2_ADDR
            ),
            "set_co2": read_real(
                client, SET_CO2_ADDR
            ),
            "high_temp_protection": read_real(
                client, HIGH_TEMP_PROTECT_ADDR
            ),
            "low_temp_protection": read_real(
                client, LOW_TEMP_PROTECT_ADDR
            ),
        },
        "run_status": run_status,
        "alarms": alarms,
        "controls": controls,
    }


def collect_schedule_snapshot(client: Client) -> dict:
    environment_segments = []
    for index in range(8):
        environment_segments.append(
            {
                "segment": index + 1,
                "temperature": read_real(client, TEMP_ADDRS[index]),
                "humidity": read_real(client, HUMIDITY_ADDRS[index]),
                "co2": read_real(client, CO2_ADDRS[index]),
                "light": read_m_bit(
                    client, ENV_LIGHT_M_BYTE, index
                ),
                "start_hour": read_word(
                    client, ENV_START_HOUR_ADDRS[index]
                ),
                "start_minute": read_word(
                    client, ENV_START_MINUTE_ADDRS[index]
                ),
                "end_hour": read_word(
                    client, ENV_END_HOUR_ADDRS[index]
                ),
                "end_minute": read_word(
                    client, ENV_END_MINUTE_ADDRS[index]
                ),
            }
        )

    fan_segments = []
    for index in range(8):
        fan_segments.append(
            {
                "segment": index + 1,
                "enabled": read_m_bit(client, FAN_M_BYTE, index),
                "start_hour": read_word(
                    client, FAN_START_HOUR_ADDRS[index]
                ),
                "start_minute": read_word(
                    client, FAN_START_MINUTE_ADDRS[index]
                ),
                "end_hour": read_word(
                    client, FAN_END_HOUR_ADDRS[index]
                ),
                "end_minute": read_word(
                    client, FAN_END_MINUTE_ADDRS[index]
                ),
            }
        )

    return {
        "selected_segment": read_byte(
            client, SELECTED_SEGMENT_ADDR
        ),
        "environment_segments": environment_segments,
        "fan_segments": fan_segments,
    }


def save_backup(snapshot: dict, prefix: str) -> Path:
    path = Path.cwd() / (
        f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"写入前备份：{path}")
    return path


def print_monitor(snapshot: dict) -> None:
    values = snapshot["measurements"]

    print("\n" + "=" * 82)
    print("实时测量与设定")
    print("-" * 82)
    print(
        f"温度：实际 {values['actual_temperature']:.3f} ℃，"
        f"设定 {values['set_temperature']:.3f} ℃"
    )
    print(
        f"湿度：实际 {values['actual_humidity']:.3f} %RH，"
        f"设定 {values['set_humidity']:.3f} %RH"
    )
    print(
        f"CO₂：实际 {values['actual_co2']:.3f} ppm，"
        f"设定 {values['set_co2']:.3f} ppm"
    )
    print(
        f"温度保护：低温 {values['low_temp_protection']:.3f} ℃，"
        f"高温 {values['high_temp_protection']:.3f} ℃"
    )

    print("\n运行状态（只读）")
    print("-" * 82)
    for name, state in snapshot["run_status"].items():
        print(
            f"{RUN_STATUS_LABELS[name]:<12}："
            f"{'运行' if state else '停止'}"
        )

    print("\n报警输入（只读，1=正常，0=异常）")
    print("-" * 82)
    for name, state in snapshot["alarms"].items():
        print(
            f"{ALARM_LABELS[name]:<12}："
            f"{'正常' if state else '报警'}"
        )

    print("\n控制位（0=关，1=开）")
    print("-" * 82)
    for name, state in snapshot["controls"].items():
        print(
            f"{CONTROL_LABELS[name]:<28}："
            f"{'ON' if state else 'OFF'}"
        )


def require_apply(args: argparse.Namespace) -> None:
    if not args.apply:
        raise RuntimeError(
            "当前是预览模式，没有写入 PLC。"
            "确认安全后追加 --apply。"
        )
    if not args.yes_i_understand:
        raise RuntimeError(
            "还需要追加 --yes-i-understand。"
        )


# ============================================================
# 11. 命令
# ============================================================

def command_monitor(client: Client, args: argparse.Namespace) -> None:
    snapshot = collect_monitor_snapshot(client)
    print_monitor(snapshot)

    if args.json:
        Path(args.json).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n已保存：{Path(args.json).resolve()}")


def command_watch(client: Client, args: argparse.Namespace) -> None:
    print("开始实时监控，按 Ctrl+C 退出。")

    while True:
        snapshot = collect_monitor_snapshot(client)
        values = snapshot["measurements"]
        active_alarms = [
            ALARM_LABELS[name]
            for name, state in snapshot["alarms"].items()
            if not state
        ]

        print(
            f"[{snapshot['captured_at']}] "
            f"T={values['actual_temperature']:.2f}℃ "
            f"H={values['actual_humidity']:.2f}%RH "
            f"CO₂={values['actual_co2']:.1f}ppm "
            f"报警={','.join(active_alarms) if active_alarms else '无'}"
        )
        time.sleep(args.interval)



def command_setpoints(client: Client, args: argparse.Namespace) -> None:
    """
    修改当前温度、湿度和 CO₂ 目标。

    VD32、VD148、VD1012 是 PLC 计算后的设定值反馈，只读。
    压缩机停机保护时间由 PLC 内部固定为 180 秒，
    上位机不读取、不显示、不修改该参数。

    上位机实际写入环境第 1 段：
      温度 -> VD264
      湿度 -> VD268
      CO₂  -> VD600
    并确保：
      第 1 段时间为 00:00～00:00（全天有效）
      VB4800 = 1
    """
    before = {
        "monitor": collect_monitor_snapshot(client),
        "schedule": collect_schedule_snapshot(client),
    }
    print_monitor(before["monitor"])

    changes = {
        "temperature": args.temperature,
        "humidity": args.humidity,
        "co2": args.co2,
    }

    if all(value is None for value in changes.values()):
        raise ValueError("至少提供一个要修改的参数")

    print("\n准备修改：")
    if args.temperature is not None:
        print(
            f"  温度目标：VD{TEMP_ADDRS[0]} = {args.temperature} "
            f"（VD{SET_TEMPERATURE_ADDR} 仅作为反馈读取）"
        )
    if args.humidity is not None:
        print(
            f"  湿度目标：VD{HUMIDITY_ADDRS[0]} = {args.humidity} "
            f"（VD{SET_HUMIDITY_ADDR} 仅作为反馈读取）"
        )
    if args.co2 is not None:
        print(
            f"  CO₂目标：VD{CO2_ADDRS[0]} = {args.co2} "
            f"（VD{SET_CO2_ADDR} 仅作为反馈读取）"
        )

    require_apply(args)
    save_backup(before, "plc_setpoints_backup")

    # 先准备第 1 段，再写目标参数，最后选择第 1 段。
    write_word(client, ENV_START_HOUR_ADDRS[0], 0)
    write_word(client, ENV_START_MINUTE_ADDRS[0], 0)
    write_word(client, ENV_END_HOUR_ADDRS[0], 0)
    write_word(client, ENV_END_MINUTE_ADDRS[0], 0)

    if args.temperature is not None:
        actual = write_real(
            client,
            TEMP_ADDRS[0],
            args.temperature,
        )
        print(f"VD{TEMP_ADDRS[0]} 温度目标回读：{actual}")

    if args.humidity is not None:
        actual = write_real(
            client,
            HUMIDITY_ADDRS[0],
            args.humidity,
        )
        print(f"VD{HUMIDITY_ADDRS[0]} 湿度目标回读：{actual}")

    if args.co2 is not None:
        actual = write_real(
            client,
            CO2_ADDRS[0],
            args.co2,
        )
        print(f"VD{CO2_ADDRS[0]} CO₂目标回读：{actual}")

    selected = write_byte(
        client,
        SELECTED_SEGMENT_ADDR,
        1,
    )
    print(f"VB{SELECTED_SEGMENT_ADDR} 所选段号回读：{selected}")

    # 给 PLC 一个扫描和内部计算更新时间，再读取反馈点位。
    time.sleep(0.5)
    feedback = collect_monitor_snapshot(client)["measurements"]

    print("\nPLC 设定值反馈（只读监控点位）：")
    print(
        f"  VD{SET_TEMPERATURE_ADDR} 温度设定反馈："
        f"{feedback['set_temperature']:.3f} ℃"
    )
    print(
        f"  VD{SET_HUMIDITY_ADDR} 湿度设定反馈："
        f"{feedback['set_humidity']:.3f} %RH"
    )
    print(
        f"  VD{SET_CO2_ADDR} CO₂设定反馈："
        f"{feedback['set_co2']:.3f} ppm"
    )


def command_control(client: Client, args: argparse.Namespace) -> None:
    area, byte_address, bit = CONTROL_POINTS[args.device]
    target = args.state == "on"
    current = read_named_bit(
        client, area, byte_address, bit
    )

    print(
        f"控制对象：{CONTROL_LABELS[args.device]}\n"
        f"点位：{area}{byte_address}.{bit}\n"
        f"当前：{'ON' if current else 'OFF'}\n"
        f"目标：{args.state.upper()}"
    )

    require_apply(args)
    before = collect_monitor_snapshot(client)
    save_backup(before, f"plc_control_{args.device}_backup")

    actual = write_control_bit(
        client,
        area,
        byte_address,
        bit,
        target,
    )

    print(f"回读：{'ON' if actual else 'OFF'}")


def command_prepare_env1(client: Client, args: argparse.Namespace) -> None:
    before = {
        "monitor": collect_monitor_snapshot(client),
        "schedule": collect_schedule_snapshot(client),
    }

    print("准备把环境第 1 段设置为全天有效：")
    print("  开始 00:00，结束 00:00")
    print("  VB4800 = 1")

    require_apply(args)
    save_backup(before, "plc_prepare_env1_backup")

    write_word(client, ENV_START_HOUR_ADDRS[0], 0)
    write_word(client, ENV_START_MINUTE_ADDRS[0], 0)
    write_word(client, ENV_END_HOUR_ADDRS[0], 0)
    write_word(client, ENV_END_MINUTE_ADDRS[0], 0)
    write_byte(client, SELECTED_SEGMENT_ADDR, 1)

    print("环境第 1 段初始化完成")


def command_prepare_fan(client: Client, args: argparse.Namespace) -> None:
    before = {
        "monitor": collect_monitor_snapshot(client),
        "schedule": collect_schedule_snapshot(client),
    }

    print("准备初始化新风：")
    print("  第 1 段 00:00～00:00（全天有效）")
    print("  M4.0～M4.7 全部 OFF")

    require_apply(args)
    save_backup(before, "plc_prepare_fan_backup")

    write_m_byte(client, FAN_M_BYTE, 0)
    write_word(client, FAN_START_HOUR_ADDRS[0], 0)
    write_word(client, FAN_START_MINUTE_ADDRS[0], 0)
    write_word(client, FAN_END_HOUR_ADDRS[0], 0)
    write_word(client, FAN_END_MINUTE_ADDRS[0], 0)

    print("新风初始化完成")


def command_fan(client: Client, args: argparse.Namespace) -> None:
    target = args.state == "on"
    current = read_m_bit(client, FAN_M_BYTE, 0)

    print(
        f"新风 M4.0：当前 {'ON' if current else 'OFF'}，"
        f"目标 {args.state.upper()}"
    )

    require_apply(args)
    save_backup(
        collect_schedule_snapshot(client),
        "plc_fan_backup",
    )

    actual = write_m_bit(
        client, FAN_M_BYTE, 0, target
    )
    print(f"M4.0 回读：{'ON' if actual else 'OFF'}")


def curve_value(
    shape: str,
    start: float,
    end: float,
    progress: float,
) -> float:
    progress = min(1.0, max(0.0, progress))

    if shape == "smooth":
        progress = (
            1.0 - math.cos(math.pi * progress)
        ) / 2.0
    elif shape == "step":
        progress = 0.0 if progress < 0.5 else 1.0

    return start + (end - start) * progress


def command_curve(client: Client, args: argparse.Namespace) -> None:
    curves: dict[str, tuple[float, float, int]] = {}

    if args.temperature:
        curves["temperature"] = (
            args.temperature[0],
            args.temperature[1],
            TEMP_ADDRS[0],
        )
    if args.humidity:
        curves["humidity"] = (
            args.humidity[0],
            args.humidity[1],
            HUMIDITY_ADDRS[0],
        )
    if args.co2:
        curves["co2"] = (
            args.co2[0],
            args.co2[1],
            CO2_ADDRS[0],
        )

    if not curves:
        raise ValueError(
            "至少提供 --temperature、--humidity 或 --co2"
        )

    if args.duration <= 0 or args.interval <= 0:
        raise ValueError("duration 和 interval 必须大于 0")
    if args.interval > args.duration:
        raise ValueError("interval 不能大于 duration")

    steps = math.ceil(args.duration / args.interval)

    print(
        f"曲线：{args.shape}，持续 {args.duration}s，"
        f"周期 {args.interval}s，写入 {steps + 1} 次"
    )

    for step in range(steps + 1):
        elapsed = min(args.duration, step * args.interval)
        progress = elapsed / args.duration
        preview = {
            name: round(
                curve_value(shape=args.shape, start=start, end=end, progress=progress),
                4,
            )
            for name, (start, end, _) in curves.items()
        }
        print(f"{elapsed:>7.1f}s：{preview}")

    require_apply(args)

    before = {
        "monitor": collect_monitor_snapshot(client),
        "schedule": collect_schedule_snapshot(client),
    }
    save_backup(before, "plc_curve_backup")

    write_word(client, ENV_START_HOUR_ADDRS[0], 0)
    write_word(client, ENV_START_MINUTE_ADDRS[0], 0)
    write_word(client, ENV_END_HOUR_ADDRS[0], 0)
    write_word(client, ENV_END_MINUTE_ADDRS[0], 0)
    write_byte(client, SELECTED_SEGMENT_ADDR, 1)

    started = time.monotonic()

    for step in range(steps + 1):
        elapsed = min(args.duration, step * args.interval)

        while True:
            remaining = started + elapsed - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.2, remaining))

        progress = elapsed / args.duration
        written = {}

        for name, (start, end, address) in curves.items():
            value = curve_value(
                args.shape, start, end, progress
            )
            written[name] = write_real(
                client, address, value
            )

        print(f"[{elapsed:>7.1f}s] {written}")

    print("曲线执行完成")


# ============================================================
# 12. CLI
# ============================================================

def add_write_confirmation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正写 PLC；不加时仅预览",
    )
    parser.add_argument(
        "--yes-i-understand",
        action="store_true",
        help="确认写入可能影响设备运行",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="S7-200 SMART 综合点位测试工具 v3.2 Final"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    monitor = sub.add_parser(
        "monitor",
        help="读取一次实时值、状态、报警和控制位",
    )
    monitor.add_argument("--json")

    watch = sub.add_parser(
        "watch",
        help="循环读取实时值与报警",
    )
    watch.add_argument(
        "--interval",
        type=float,
        default=2.0,
    )

    setpoints = sub.add_parser(
        "setpoints",
        help="通过环境第1段设置温度、湿度和CO₂",
    )
    setpoints.add_argument("--temperature", type=float)
    setpoints.add_argument("--humidity", type=float)
    setpoints.add_argument("--co2", type=float)
    add_write_confirmation(setpoints)

    control = sub.add_parser(
        "control",
        help="控制系统总开关、压机、紫外或CO₂",
    )
    control.add_argument(
        "device",
        choices=tuple(CONTROL_POINTS.keys()),
    )
    control.add_argument(
        "state",
        choices=["on", "off"],
    )
    add_write_confirmation(control)

    prepare_env = sub.add_parser(
        "prepare-env1",
        help="环境第1段设置为全天有效并选择第1段",
    )
    add_write_confirmation(prepare_env)

    prepare_fan = sub.add_parser(
        "prepare-fan",
        help="新风第1段设为全天有效，其他段关闭",
    )
    add_write_confirmation(prepare_fan)

    fan = sub.add_parser(
        "fan",
        help="通过 M4.0 开关新风",
    )
    fan.add_argument("state", choices=["on", "off"])
    add_write_confirmation(fan)

    curve = sub.add_parser(
        "curve",
        help="按曲线修改环境第1段温湿度/CO₂",
    )
    curve.add_argument(
        "--temperature",
        nargs=2,
        type=float,
        metavar=("START", "END"),
    )
    curve.add_argument(
        "--humidity",
        nargs=2,
        type=float,
        metavar=("START", "END"),
    )
    curve.add_argument(
        "--co2",
        nargs=2,
        type=float,
        metavar=("START", "END"),
    )
    curve.add_argument(
        "--duration",
        type=float,
        default=60.0,
    )
    curve.add_argument(
        "--interval",
        type=float,
        default=10.0,
    )
    curve.add_argument(
        "--shape",
        choices=["linear", "smooth", "step"],
        default="linear",
    )
    add_write_confirmation(curve)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    client: Client | None = None

    try:
        client, local_tsap, remote_tsap = connect_plc()
        print(
            f"有效 TSAP：Local=0x{local_tsap:04X}, "
            f"Remote=0x{remote_tsap:04X}"
        )

        if args.command == "monitor":
            command_monitor(client, args)
        elif args.command == "watch":
            command_watch(client, args)
        elif args.command == "setpoints":
            command_setpoints(client, args)
        elif args.command == "control":
            command_control(client, args)
        elif args.command == "prepare-env1":
            command_prepare_env1(client, args)
        elif args.command == "prepare-fan":
            command_prepare_fan(client, args)
        elif args.command == "fan":
            command_fan(client, args)
        elif args.command == "curve":
            command_curve(client, args)

        return 0

    except KeyboardInterrupt:
        print("\n用户终止")
        return 130
    except Exception as exc:
        print("\n" + "=" * 82)
        print("执行失败")
        print(f"错误类型：{type(exc).__name__}")
        print(f"错误内容：{exc}")
        return 1
    finally:
        safe_disconnect(client)
        print("PLC 连接已关闭")


if __name__ == "__main__":
    raise SystemExit(main())
