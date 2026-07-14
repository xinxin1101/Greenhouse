from __future__ import annotations

from contextlib import contextmanager
import re
import threading
import time
from datetime import datetime
from typing import Any, Iterable, Iterator

import pymysql
from pymysql.connections import Connection as MySqlConnection

from .config import AppConfig


SENSOR_COLUMNS = {
    "temperature": "temperature",
    "humidity": "humidity",
    "co2": "co2",
    "light": "light_on",
}


class HistoryStore:
    """MySQL 环境数据与报警事件归档。

    PLC 原始轮询值按 poll_interval_seconds 持久化；查询时再按用户指定的
    采样周期，从每个时间桶中选取最早的一条真实记录，不对数值做平均。
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.retention_days = config.history_retention_days
        self.table_name = self._validate_identifier(config.mysql_table)
        self.alarm_table_name = self._validate_identifier(
            config.mysql_alarm_table
        )
        self._lock = threading.RLock()
        self._mysql_write_connection: MySqlConnection | None = None
        self._initialize_mysql_store()
        self._last_cleanup = 0.0
        self.cleanup()

    def _initialize_mysql_store(self) -> None:
        measurement_sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.table_name}` (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                plc_id VARCHAR(64) NOT NULL DEFAULT 'greenhouse-plc-01',
                temperature DOUBLE NULL,
                humidity DOUBLE NULL,
                co2 DOUBLE NULL,
                light_on TINYINT(1) NULL,
                record_time DATETIME(3) NOT NULL,
                INDEX idx_greenhouse_record_time (record_time),
                INDEX idx_greenhouse_plc_time (plc_id, record_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """
        alarm_sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.alarm_table_name}` (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                plc_id VARCHAR(64) NOT NULL,
                alarm_code VARCHAR(64) NOT NULL,
                alarm_name VARCHAR(128) NOT NULL,
                message VARCHAR(255) NOT NULL,
                active TINYINT(1) NOT NULL DEFAULT 1,
                acknowledged TINYINT(1) NOT NULL DEFAULT 0,
                started_at DATETIME(3) NOT NULL,
                cleared_at DATETIME(3) NULL,
                INDEX idx_greenhouse_alarm_active (active),
                INDEX idx_greenhouse_alarm_started (started_at),
                INDEX idx_greenhouse_alarm_plc_started (plc_id, started_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """
        with self._mysql_read_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(measurement_sql)
                cursor.execute(alarm_sql)
            connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._mysql_write_connection is not None:
                self._mysql_write_connection.close()
                self._mysql_write_connection = None

    def record(self, timestamp: float, measurements: dict[str, Any]) -> None:
        values = (
            self.config.plc_id,
            self._number_or_none(measurements.get("temperature")),
            self._number_or_none(measurements.get("humidity")),
            self._number_or_none(measurements.get("co2")),
            self._boolean_int_or_none(measurements.get("light")),
            datetime.fromtimestamp(float(timestamp)),
        )
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO `{self.table_name}`
                        (plc_id, temperature, humidity, co2, light_on, record_time)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        values,
                    )
                connection.commit()
            except Exception:
                self._reset_mysql_write_connection()
                raise

        if time.monotonic() - self._last_cleanup > 21600:
            self.cleanup()

    @staticmethod
    def _number_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _boolean_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        return 1 if bool(value) else 0

    def cleanup(self) -> int:
        cutoff_datetime = datetime.fromtimestamp(
            time.time() - self.retention_days * 86400
        )
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM `{self.table_name}` WHERE record_time < %s",
                        (cutoff_datetime,),
                    )
                    deleted_measurements = int(cursor.rowcount or 0)
                connection.commit()
            except Exception:
                self._reset_mysql_write_connection()
                raise
            # 已解决异常按同样保留周期清理；未解决异常永不自动删除。
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        DELETE FROM `{self.alarm_table_name}`
                        WHERE active = 0
                          AND cleared_at IS NOT NULL
                          AND cleared_at < %s
                        """,
                        (cutoff_datetime,),
                    )
                connection.commit()
            except Exception:
                self._reset_mysql_write_connection()
                raise
            self._last_cleanup = time.monotonic()
            return deleted_measurements

    def record_alarm_start(
        self,
        *,
        name: str,
        label: str,
        timestamp: float,
        message: str,
    ) -> dict[str, Any]:
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO `{self.alarm_table_name}`
                        (plc_id, alarm_code, alarm_name, message, active, acknowledged, started_at)
                        VALUES (%s, %s, %s, %s, 1, 0, %s)
                        """,
                        (
                            self.config.plc_id,
                            name,
                            label,
                            message,
                            datetime.fromtimestamp(float(timestamp)),
                        ),
                    )
                    event_id = int(cursor.lastrowid)
                connection.commit()
            except Exception:
                self._reset_mysql_write_connection()
                raise

        return {
            "id": event_id,
            "name": name,
            "label": label,
            "time": self._time_text(timestamp),
            "started_timestamp": float(timestamp),
            "active": True,
            "acknowledged": False,
            "message": message,
            "cleared_at": None,
            "cleared_timestamp": None,
        }

    def resolve_alarm(
        self,
        event_id: int,
        cleared_timestamp: float,
    ) -> None:
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE `{self.alarm_table_name}`
                        SET active = 0,
                            cleared_at = %s
                        WHERE id = %s
                        """,
                        (
                            datetime.fromtimestamp(float(cleared_timestamp)),
                            int(event_id),
                        ),
                    )
                connection.commit()
            except Exception:
                self._reset_mysql_write_connection()
                raise

    def acknowledge_active_alarms(self) -> int:
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE `{self.alarm_table_name}`
                        SET acknowledged = 1
                        WHERE plc_id = %s AND active = 1
                        """,
                        (self.config.plc_id,),
                    )
                    updated = cursor.rowcount
                connection.commit()
                return updated
            except Exception:
                self._reset_mysql_write_connection()
                raise

    def acknowledge_unacknowledged_alarms(self, plc_ids: list[str]) -> int:
        normalized_ids = list(dict.fromkeys(plc_id.strip() for plc_id in plc_ids if plc_id.strip()))
        if not normalized_ids:
            raise ValueError("至少需要提供一个 PLC 标识")

        placeholders = ", ".join(["%s"] * len(normalized_ids))
        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE `{self.alarm_table_name}`
                        SET acknowledged = 1
                        WHERE plc_id IN ({placeholders}) AND acknowledged = 0
                        """,
                        normalized_ids,
                    )
                    updated = cursor.rowcount
                connection.commit()
                return updated
            except Exception:
                self._reset_mysql_write_connection()
                raise

    def acknowledge_alarm_event(self, event_id: int, plc_id: str) -> bool:
        normalized_plc_id = plc_id.strip()
        if not normalized_plc_id:
            raise ValueError("PLC 标识不能为空")

        with self._lock:
            try:
                connection = self._get_mysql_write_connection()
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE `{self.alarm_table_name}`
                        SET acknowledged = 1
                        WHERE id = %s AND plc_id = %s AND acknowledged = 0
                        """,
                        (event_id, normalized_plc_id),
                    )
                    updated = cursor.rowcount
                connection.commit()
                return updated > 0
            except Exception:
                self._reset_mysql_write_connection()
                raise

    def alarm_log(self, limit: int = 500) -> list[dict[str, Any]]:
        if not 1 <= limit <= 5000:
            raise ValueError("异常日志条数必须在 1～5000 之间")

        with self._mysql_read_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT id,
                           alarm_code AS name,
                           alarm_name AS label,
                           UNIX_TIMESTAMP(started_at) AS started_timestamp,
                           message,
                           active,
                           acknowledged,
                           UNIX_TIMESTAMP(cleared_at) AS cleared_timestamp
                    FROM `{self.alarm_table_name}`
                    WHERE plc_id = %s
                    ORDER BY started_at DESC, id DESC
                    LIMIT %s
                    """,
                    (self.config.plc_id, int(limit)),
                )
                rows = cursor.fetchall()

        return [
            {
                "id": int(row["id"]),
                "name": row["name"],
                "label": row["label"],
                "time": self._time_text(row["started_timestamp"]),
                "started_timestamp": float(row["started_timestamp"]),
                "active": bool(row["active"]),
                "acknowledged": bool(row["acknowledged"]),
                "message": row["message"],
                "cleared_at": self._time_text(row["cleared_timestamp"]),
                "cleared_timestamp": (
                    float(row["cleared_timestamp"])
                    if row["cleared_timestamp"] is not None
                    else None
                ),
            }
            for row in rows
        ]

    def meta(self) -> dict[str, Any]:
        with self._mysql_read_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS count,
                           UNIX_TIMESTAMP(MIN(record_time)) AS min_timestamp,
                           UNIX_TIMESTAMP(MAX(record_time)) AS max_timestamp
                    FROM `{self.table_name}`
                    """
                )
                row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT COALESCE(data_length, 0) + COALESCE(index_length, 0)
                           AS storage_bytes
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    """,
                    (self.config.mysql_database, self.table_name),
                )
                size_row = cursor.fetchone()

        min_timestamp = row["min_timestamp"]
        max_timestamp = row["max_timestamp"]
        return {
            "raw_count": int(row["count"] or 0),
            "min_timestamp": min_timestamp,
            "max_timestamp": max_timestamp,
            "min_time_text": self._time_text(min_timestamp),
            "max_time_text": self._time_text(max_timestamp),
            "retention_days": self.retention_days,
            "database_size_bytes": int((size_row or {}).get("storage_bytes") or 0),
        }

    def query(
        self,
        start_timestamp: float,
        end_timestamp: float,
        interval_seconds: float,
        sensors: Iterable[str],
        limit: int = 5000,
    ) -> dict[str, Any]:
        selected = self._validate_query(
            start_timestamp,
            end_timestamp,
            interval_seconds,
            sensors,
            limit,
        )
        columns = [SENSOR_COLUMNS[name] for name in selected]
        column_sql = ", ".join(f"`{column}`" for column in columns)
        start_datetime = datetime.fromtimestamp(start_timestamp)
        end_datetime = datetime.fromtimestamp(end_timestamp)

        with self._mysql_read_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM `{self.table_name}`
                    WHERE record_time BETWEEN %s AND %s
                    """,
                    (start_datetime, end_datetime),
                )
                raw_count = int(cursor.fetchone()["count"] or 0)
                cursor.execute(
                    f"""
                    SELECT COUNT(DISTINCT FLOOR(
                        (UNIX_TIMESTAMP(record_time) - %s) / %s
                    )) AS count
                    FROM `{self.table_name}`
                    WHERE record_time BETWEEN %s AND %s
                    """,
                    (
                        start_timestamp,
                        interval_seconds,
                        start_datetime,
                        end_datetime,
                    ),
                )
                sampled_count = int(cursor.fetchone()["count"] or 0)

                query_sql = f"""
                    WITH ranked AS (
                        SELECT UNIX_TIMESTAMP(record_time) AS timestamp,
                               {column_sql},
                               ROW_NUMBER() OVER (
                                   PARTITION BY FLOOR(
                                       (UNIX_TIMESTAMP(record_time) - %s) / %s
                                   )
                                   ORDER BY record_time ASC
                               ) AS sample_rank
                        FROM `{self.table_name}`
                        WHERE record_time BETWEEN %s AND %s
                    )
                    SELECT timestamp, {column_sql}
                    FROM ranked
                    WHERE sample_rank = 1
                    ORDER BY timestamp ASC
                    LIMIT %s
                """
                cursor.execute(
                    query_sql,
                    (
                        start_timestamp,
                        interval_seconds,
                        start_datetime,
                        end_datetime,
                        limit + 1,
                    ),
                )
                rows = cursor.fetchall()

        truncated = len(rows) > limit
        rows = rows[:limit]
        result_rows: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {
                "timestamp": float(row["timestamp"]),
                "time_text": self._time_text(row["timestamp"]),
            }
            for sensor in selected:
                value = row[SENSOR_COLUMNS[sensor]]
                if sensor == "light" and value is not None:
                    value = int(value)
                item[sensor] = value
            result_rows.append(item)

        return {
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "start_time_text": self._time_text(start_timestamp),
            "end_time_text": self._time_text(end_timestamp),
            "interval_seconds": interval_seconds,
            "sensors": selected,
            "raw_count": int(raw_count or 0),
            "sampled_count": int(sampled_count or 0),
            "returned_count": len(result_rows),
            "truncated": truncated,
            "rows": result_rows,
            "statistics": self._statistics(result_rows, selected),
        }

    def _validate_query(
        self,
        start_timestamp: float,
        end_timestamp: float,
        interval_seconds: float,
        sensors: Iterable[str],
        limit: int,
    ) -> list[str]:
        if end_timestamp <= start_timestamp:
            raise ValueError("结束时间必须晚于开始时间")
        if not 1 <= interval_seconds <= 86400:
            raise ValueError("采样周期必须在 1 秒～24 小时之间")
        if not 1 <= limit <= 200000:
            raise ValueError("返回行数限制无效")

        selected: list[str] = []
        for sensor in sensors:
            name = str(sensor).strip()
            if not name:
                continue
            if name not in SENSOR_COLUMNS:
                raise ValueError(f"未知检测参数：{name}")
            if name not in selected:
                selected.append(name)
        if not selected:
            raise ValueError("至少选择一个检测参数")
        return selected

    @staticmethod
    def _statistics(rows: list[dict[str, Any]], sensors: list[str]) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for sensor in sensors:
            values = [
                float(row[sensor])
                for row in rows
                if row.get(sensor) is not None
            ]
            if not values:
                stats[sensor] = None
                continue
            if sensor == "light":
                on_count = sum(1 for value in values if value >= 0.5)
                stats[sensor] = {
                    "on_count": on_count,
                    "off_count": len(values) - on_count,
                    "on_ratio": on_count / len(values),
                }
            else:
                stats[sensor] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        return stats

    def _open_mysql_connection(self) -> MySqlConnection:
        return pymysql.connect(
            host=self.config.mysql_host,
            port=self.config.mysql_port,
            user=self.config.mysql_username,
            password=self.config.mysql_password,
            database=self.config.mysql_database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=8,
            read_timeout=15,
            write_timeout=15,
            autocommit=False,
        )

    def _get_mysql_write_connection(self) -> MySqlConnection:
        if self._mysql_write_connection is None:
            self._mysql_write_connection = self._open_mysql_connection()
        else:
            self._mysql_write_connection.ping(reconnect=True)
        return self._mysql_write_connection

    def _reset_mysql_write_connection(self) -> None:
        if self._mysql_write_connection is not None:
            try:
                self._mysql_write_connection.close()
            finally:
                self._mysql_write_connection = None

    @contextmanager
    def _mysql_read_connection(self) -> Iterator[MySqlConnection]:
        connection = self._open_mysql_connection()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _validate_identifier(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("mysql_table 只能包含字母、数字和下划线，且不能以数字开头")
        return value

    @staticmethod
    def _time_text(timestamp: float | None) -> str | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(float(timestamp)).isoformat(timespec="seconds")
