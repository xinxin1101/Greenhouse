from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"


@dataclass(frozen=True)
class AppConfig:
    # mode: str = "plc"
    # plc_ip: str = "192.168.2.1"
    mode: str = "simulation"
    plc_ip: str = "greenhouse-plc-sim"
    plc_port: int = 102
    poll_interval_seconds: float = 1.0
    reconnect_interval_seconds: float = 3.0
    history_points: int = 3600
    history_retention_days: int = 30
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "sensor"
    mysql_username: str = "root"
    mysql_password: str = ""
    mysql_table: str = "greenhouse_plc_data"
    mysql_alarm_table: str = "greenhouse_alarm_events"
    plc_id: str = "greenhouse-plc-01"
    host: str = "127.0.0.1"
    web_port: int = 8000
    open_browser: bool = True


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()

    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    password_override = os.getenv("GREENHOUSE_MYSQL_PASSWORD")
    if password_override is not None:
        data["mysql_password"] = password_override
    config = AppConfig(**data)

    if config.mode not in {"plc", "simulation"}:
        raise ValueError("config.json 中 mode 只能是 plc 或 simulation")
    if config.poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds 必须大于 0")
    if config.reconnect_interval_seconds <= 0:
        raise ValueError("reconnect_interval_seconds 必须大于 0")
    if config.history_points < 60:
        raise ValueError("history_points 不应小于 60")
    if config.history_retention_days < 1:
        raise ValueError("history_retention_days 不应小于 1")
    if not 1 <= config.mysql_port <= 65535:
        raise ValueError("mysql_port 必须是有效端口")
    if not config.mysql_database.strip():
        raise ValueError("mysql_database 不能为空")
    if not config.mysql_username.strip():
        raise ValueError("mysql_username 不能为空")
    if not config.mysql_table.strip():
        raise ValueError("mysql_table 不能为空")
    if not config.mysql_alarm_table.strip():
        raise ValueError("mysql_alarm_table 不能为空")
    if not config.plc_id.strip():
        raise ValueError("plc_id 不能为空")

    return config
