from __future__ import annotations

import copy
import logging
import math
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import AppConfig
from .history_store import HistoryStore
from .plc_controller import BaseController, ControllerError, create_controller


logger = logging.getLogger("plc_hmi.service")


SENSOR_META: dict[str, dict[str, Any]] = {
    "temperature": {
        "label": "温度",
        "unit": "℃",
        "decimals": 2,
        "min": -20.0,
        "max": 60.0,
    },
    "humidity": {
        "label": "湿度",
        "unit": "%RH",
        "decimals": 2,
        "min": 0.0,
        "max": 100.0,
    },
    "co2": {
        "label": "CO₂",
        "unit": "ppm",
        "decimals": 1,
        "min": 0.0,
        "max": 10000.0,
    },
    "light": {
        "label": "灯组状态",
        "unit": "",
        "decimals": 0,
        "min": 0.0,
        "max": 1.0,
        "boolean": True,
    },
}

RUN_STATUS_LABELS = {
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

CONTROL_LABELS = {
    "system": "系统总控制",
    "compressor": "压机",
    "uv": "紫外",
    "co2": "CO₂",
    "fresh_air": "新风",
    "lamp": "灯组",
}

ALARM_LABELS = {
    "overload": "过载",
    "high_pressure": "压缩机高压",
    "low_pressure": "压缩机低压",
    "high_temperature": "高温",
}


@dataclass
class ServiceCommand:
    action: str
    payload: dict[str, Any]
    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Exception | None = None


@dataclass
class CurvePlan:
    sensor: str
    start_value: float
    end_value: float
    duration_seconds: float
    interval_seconds: float
    shape: str
    started_monotonic: float
    started_timestamp: float
    started_at: str
    next_write_monotonic: float
    last_written: float | None = None
    status: str = "running"
    finished_timestamp: float | None = None

    @property
    def end_timestamp(self) -> float:
        return self.started_timestamp + self.duration_seconds

    def progress(self, now: float) -> float:
        return min(
            1.0,
            max(
                0.0,
                (now - self.started_monotonic) / self.duration_seconds,
            ),
        )

    def value_at(self, now: float) -> float:
        progress = self.progress(now)
        if self.shape == "smooth":
            progress = (1.0 - math.cos(math.pi * progress)) / 2.0
        elif self.shape == "step":
            progress = 0.0 if progress < 0.5 else 1.0
        return self.start_value + (
            self.end_value - self.start_value
        ) * progress

    def as_dict(self, now: float) -> dict[str, Any]:
        progress = self.progress(now)
        return {
            "sensor": self.sensor,
            "start_value": self.start_value,
            "end_value": self.end_value,
            "duration_seconds": self.duration_seconds,
            "interval_seconds": self.interval_seconds,
            "shape": self.shape,
            "started_at": self.started_at,
            "start_timestamp": self.started_timestamp,
            "end_timestamp": self.end_timestamp,
            "status": self.status,
            "finished_timestamp": self.finished_timestamp,
            "progress": progress,
            "current_target": self.value_at(now),
            "last_written": self.last_written,
            "remaining_seconds": max(
                0.0,
                self.duration_seconds * (1.0 - progress),
            ),
        }


class PLCService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.controller: BaseController = create_controller(config)
        self.history_store = HistoryStore(config)
        self.command_queue: queue.Queue[ServiceCommand] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state_lock = threading.RLock()

        self.history: dict[str, deque[dict[str, float]]] = {
            name: deque(maxlen=config.history_points)
            for name in SENSOR_META
        }
        persisted_alarm_events = self.history_store.alarm_log(limit=200)
        self.alarm_events: deque[dict[str, Any]] = deque(
            persisted_alarm_events,
            maxlen=200,
        )
        self.alarm_acknowledged: set[str] = {
            event["name"]
            for event in persisted_alarm_events
            if event.get("active") and event.get("acknowledged")
        }
        self.previous_alarm_active: dict[str, bool] = {
            name: False for name in ALARM_LABELS
        }
        self.alarm_sequence = max(
            (int(event["id"]) for event in persisted_alarm_events),
            default=0,
        )
        self.curves: dict[str, CurvePlan] = {}
        # 每个参数保留最近一次预设曲线。即使曲线执行完成或取消，
        # 页面仍然可以继续显示预设曲线，并查询对应的实际检测曲线。
        self.curve_records: dict[str, CurvePlan] = {}

        self.latest_state: dict[str, Any] = {
            "connected": False,
            "mode": config.mode,
            "plc_ip": config.plc_ip,
            "connection_error": None,
            "timestamp": time.time(),
            "time_text": datetime.now().isoformat(timespec="seconds"),
            "measurements": {},
            "targets": {},
            "feedback": {},
            "protection": {
                "compressor_restart_delay_seconds": 180,
            },
            "run_status": {},
            "controls": {},
            "alarms": {},
        }

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._worker,
            name="plc-service",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=4.0)
        self.controller.disconnect()
        self.history_store.close()

    def submit(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 12.0,
    ) -> Any:
        command = ServiceCommand(action=action, payload=payload or {})
        self.command_queue.put(command)

        if not command.event.wait(timeout=timeout):
            raise TimeoutError("PLC 命令等待超时，请检查连接状态")
        if command.error is not None:
            raise command.error
        return command.result

    def snapshot(self, include_history: bool = False) -> dict[str, Any]:
        with self.state_lock:
            result = copy.deepcopy(self.latest_state)
            now = time.monotonic()
            result["curves"] = {
                sensor: plan.as_dict(now)
                for sensor, plan in self.curves.items()
            }
            result["curve_traces"] = {
                sensor: plan.as_dict(now)
                for sensor, plan in self.curve_records.items()
            }
            result["sensor_meta"] = copy.deepcopy(SENSOR_META)
            result["run_status_labels"] = copy.deepcopy(RUN_STATUS_LABELS)
            result["control_labels"] = copy.deepcopy(CONTROL_LABELS)
            result["alarm_labels"] = copy.deepcopy(ALARM_LABELS)
            result["alarm_events"] = list(self.alarm_events)
            result["active_alarm_count"] = sum(
                1
                for alarm in result.get("alarms", {}).values()
                if alarm.get("active")
            )
            result["unacknowledged_alarm_count"] = sum(
                1
                for name, alarm in result.get("alarms", {}).items()
                if alarm.get("active") and name not in self.alarm_acknowledged
            )
            controls = result.get("controls", {})
            system_on = bool(controls.get("system"))
            uv_on = bool(controls.get("uv"))
            result["interlocks"] = {
                "system": {
                    "blocked": uv_on and not system_on,
                    "reason": (
                        "紫外已开启，系统总控制被互锁。请先关闭紫外。"
                        if uv_on and not system_on
                        else None
                    ),
                },
                "uv": {
                    "blocked": system_on and not uv_on,
                    "reason": (
                        "系统总控制已开启，紫外被互锁。请先关闭系统总控制。"
                        if system_on and not uv_on
                        else None
                    ),
                },
            }
            result["light_measurement_note"] = (
                "当前点位表未提供光照强度（lx）地址，页面暂以灯组运行状态显示。"
            )
            if include_history:
                result["history"] = {
                    name: list(points)
                    for name, points in self.history.items()
                }
            return result

    def alarm_log(self, limit: int = 500) -> dict[str, Any]:
        events = self.history_store.alarm_log(limit=limit)
        return {
            "count": len(events),
            "active_count": sum(1 for event in events if event.get("active")),
            "events": events,
        }

    def history_meta(self) -> dict[str, Any]:
        return self.history_store.meta()

    def query_history(
        self,
        start_timestamp: float,
        end_timestamp: float,
        interval_seconds: float,
        sensors: list[str],
        limit: int = 5000,
    ) -> dict[str, Any]:
        return self.history_store.query(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            interval_seconds=interval_seconds,
            sensors=sensors,
            limit=limit,
        )

    def curve_trace(
        self,
        sensor: str,
        max_points: int = 1200,
    ) -> dict[str, Any]:
        if sensor not in {"temperature", "humidity", "co2"}:
            raise ValueError("曲线仅支持温度、湿度和 CO₂")
        if not 100 <= max_points <= 5000:
            raise ValueError("曲线点数限制必须在 100～5000 之间")

        with self.state_lock:
            plan = copy.deepcopy(self.curve_records.get(sensor))

        if plan is None:
            return {
                "plan": None,
                "actual": {
                    "start_timestamp": None,
                    "end_timestamp": None,
                    "interval_seconds": None,
                    "sensors": [sensor],
                    "raw_count": 0,
                    "sampled_count": 0,
                    "returned_count": 0,
                    "truncated": False,
                    "rows": [],
                    "statistics": {sensor: None},
                },
            }

        query_end = min(time.time(), plan.end_timestamp)
        if query_end <= plan.started_timestamp:
            rows = {
                "start_timestamp": plan.started_timestamp,
                "end_timestamp": query_end,
                "interval_seconds": 1,
                "sensors": [sensor],
                "raw_count": 0,
                "sampled_count": 0,
                "returned_count": 0,
                "truncated": False,
                "rows": [],
                "statistics": {sensor: None},
            }
        else:
            interval_seconds = max(
                1,
                math.ceil(plan.duration_seconds / max_points),
            )
            rows = self.history_store.query(
                start_timestamp=plan.started_timestamp,
                end_timestamp=query_end,
                interval_seconds=interval_seconds,
                sensors=[sensor],
                limit=max_points,
            )

        return {
            "plan": plan.as_dict(time.monotonic()),
            "actual": rows,
        }

    def _set_connection_state(self, connected: bool, error: str | None = None) -> None:
        with self.state_lock:
            self.latest_state["connected"] = connected
            self.latest_state["connection_error"] = error
            self.latest_state["timestamp"] = time.time()
            self.latest_state["time_text"] = datetime.now().isoformat(timespec="seconds")

    def _worker(self) -> None:
        connected = False
        next_poll = 0.0
        next_reconnect = 0.0

        while not self.stop_event.is_set():
            now = time.monotonic()

            if not connected:
                if now < next_reconnect:
                    self._fail_waiting_commands_if_needed()
                    self.stop_event.wait(min(0.2, next_reconnect - now))
                    continue

                try:
                    self.controller.connect()
                    connected = True
                    next_poll = 0.0
                    self._set_connection_state(True, None)
                except Exception as exc:
                    connected = False
                    self._set_connection_state(False, str(exc))
                    next_reconnect = now + self.config.reconnect_interval_seconds
                    self._fail_waiting_commands_if_needed()
                    continue

            try:
                self._process_commands()
                self._apply_curves()

                now = time.monotonic()
                if now >= next_poll:
                    raw = self.controller.poll()
                    self._update_state(raw)
                    next_poll = now + self.config.poll_interval_seconds

                self.stop_event.wait(0.05)

            except Exception as exc:
                connected = False
                self.controller.disconnect()
                self._set_connection_state(False, str(exc))
                next_reconnect = time.monotonic() + self.config.reconnect_interval_seconds

        self._cancel_waiting_commands("服务已停止")

    def _fail_waiting_commands_if_needed(self) -> None:
        # 连接中断时不让写命令长期悬挂。只保留纯本地报警确认命令。
        pending: list[ServiceCommand] = []
        while True:
            try:
                command = self.command_queue.get_nowait()
            except queue.Empty:
                break

            if command.action in {"ack_alarms", "ack_all_alarms", "ack_alarm_event"}:
                try:
                    command.result = self._execute_command(command.action, command.payload)
                except Exception as exc:
                    command.error = exc
                command.event.set()
            else:
                command.error = ControllerError(
                    self.latest_state.get("connection_error") or "PLC 未连接"
                )
                command.event.set()

    def _cancel_waiting_commands(self, message: str) -> None:
        while True:
            try:
                command = self.command_queue.get_nowait()
            except queue.Empty:
                break
            command.error = RuntimeError(message)
            command.event.set()

    def _process_commands(self) -> None:
        for _ in range(30):
            try:
                command = self.command_queue.get_nowait()
            except queue.Empty:
                return

            try:
                command.result = self._execute_command(
                    command.action,
                    command.payload,
                )
            except Exception as exc:
                command.error = exc
                logger.warning(
                    "PLC 命令执行失败：action=%s payload=%s error=%s",
                    command.action,
                    command.payload,
                    exc,
                )
            finally:
                command.event.set()

    def _execute_command(self, action: str, payload: dict[str, Any]) -> Any:
        if action == "set_targets":
            values = dict(payload)
            numeric_sensors = {
                name for name in values
                if name in {"temperature", "humidity", "co2"}
            }
            self.controller.prepare_env1()
            self.controller.write_targets(values)
            with self.state_lock:
                for sensor in numeric_sensors:
                    plan = self.curves.pop(sensor, None)
                    if plan is not None:
                        plan.status = "manual_override"
                        plan.finished_timestamp = time.time()
            return {"ok": True, "message": "目标值已写入 PLC"}

        if action == "set_control":
            device = str(payload["device"])
            state = bool(payload["state"])

            with self.state_lock:
                controls = dict(self.latest_state.get("controls", {}))

            # 系统总控制与紫外是双向互锁：
            # 只禁止“开启”对方；当前已开启的一方必须仍可关闭。
            if state and device == "system" and bool(controls.get("uv")):
                raise ValueError(
                    "互锁保护：紫外当前已开启，无法启动系统总控制。"
                    "请先关闭紫外。"
                )

            if state and device == "uv" and bool(controls.get("system")):
                raise ValueError(
                    "互锁保护：系统总控制当前已开启，无法启动紫外。"
                    "请先关闭系统总控制。"
                )

            self.controller.write_control(device, state)

            # 立即更新命令位缓存，避免连续操作时等待下一次 PLC 轮询才生效。
            with self.state_lock:
                self.latest_state.setdefault("controls", {})[device] = state

            return {
                "ok": True,
                "message": f"{CONTROL_LABELS[device]}已{'开启' if state else '关闭'}",
            }

        if action == "set_fan":
            state = bool(payload["state"])
            self.controller.prepare_and_write_fan(state)
            return {"ok": True, "message": f"新风已{'开启' if state else '关闭'}"}

        if action == "start_curve":
            sensor = str(payload["sensor"])
            if sensor not in {"temperature", "humidity", "co2"}:
                raise ValueError("曲线仅支持温度、湿度和 CO₂")

            started_monotonic = time.monotonic()
            started_timestamp = time.time()
            plan = CurvePlan(
                sensor=sensor,
                start_value=float(payload["start_value"]),
                end_value=float(payload["end_value"]),
                duration_seconds=float(payload["duration_seconds"]),
                interval_seconds=float(payload["interval_seconds"]),
                shape=str(payload["shape"]),
                started_monotonic=started_monotonic,
                started_timestamp=started_timestamp,
                started_at=datetime.fromtimestamp(
                    started_timestamp
                ).isoformat(timespec="seconds"),
                next_write_monotonic=started_monotonic,
            )
            self.controller.prepare_env1()
            self.controller.write_targets({sensor: plan.start_value})
            plan.last_written = plan.start_value
            plan.next_write_monotonic = (
                time.monotonic() + plan.interval_seconds
            )
            with self.state_lock:
                previous = self.curves.pop(sensor, None)
                if previous is not None:
                    previous.status = "replaced"
                    previous.finished_timestamp = started_timestamp
                self.curves[sensor] = plan
                self.curve_records[sensor] = plan
            return {
                "ok": True,
                "message": f"{SENSOR_META[sensor]['label']}曲线已启动",
                "curve": plan.as_dict(time.monotonic()),
            }

        if action == "cancel_curve":
            sensor = str(payload["sensor"])
            with self.state_lock:
                plan = self.curves.pop(sensor, None)
                existed = plan is not None
                if plan is not None:
                    plan.status = "cancelled"
                    plan.finished_timestamp = time.time()
            return {
                "ok": True,
                "message": (
                    "曲线已取消，预设曲线仍保留用于对比"
                    if existed
                    else "该曲线当前未运行"
                ),
            }

        if action == "ack_alarms":
            updated = self.history_store.acknowledge_active_alarms()
            with self.state_lock:
                for name, alarm in self.latest_state.get("alarms", {}).items():
                    if alarm.get("active"):
                        self.alarm_acknowledged.add(name)
                for event in self.alarm_events:
                    if event.get("active"):
                        event["acknowledged"] = True

            return {"ok": True, "updated": updated, "message": "当前报警已确认"}

        if action == "ack_all_alarms":
            plc_ids = payload.get("plc_ids")
            if not isinstance(plc_ids, list):
                raise ValueError("确认范围缺少 PLC 标识")
            updated = self.history_store.acknowledge_unacknowledged_alarms(plc_ids)
            if updated == 0:
                raise ValueError("没有可确认的报警记录，请刷新页面后重试")
            with self.state_lock:
                for event in self.alarm_events:
                    if not event.get("acknowledged") and event.get("plc_id", self.config.plc_id) in plc_ids:
                        event["acknowledged"] = True
                        if event.get("active"):
                            self.alarm_acknowledged.add(event["name"])

            return {"ok": True, "updated": updated, "message": "所有未确认报警已确认"}

        if action == "ack_alarm_event":
            event_id = int(payload.get("event_id", 0))
            if event_id <= 0:
                raise ValueError("报警事件 ID 无效")
            plc_id = payload.get("plc_id")
            if not isinstance(plc_id, str):
                raise ValueError("确认范围缺少 PLC 标识")

            updated = self.history_store.acknowledge_alarm_event(event_id, plc_id)
            if not updated:
                raise ValueError("报警事件不存在、已确认，或不属于当前 PLC")

            with self.state_lock:
                for event in self.alarm_events:
                    if event.get("id") == event_id and event.get("plc_id", self.config.plc_id) == plc_id:
                        event["acknowledged"] = True
                        if event.get("active"):
                            self.alarm_acknowledged.add(event["name"])
                        break

            return {"ok": True, "updated": 1, "message": "报警记录已确认"}

        raise ValueError(f"未知命令：{action}")

    def _apply_curves(self) -> None:
        now = time.monotonic()
        updates: dict[str, float] = {}
        completed: list[str] = []

        with self.state_lock:
            plans = list(self.curves.items())

        for sensor, plan in plans:
            progress = plan.progress(now)
            due = now >= plan.next_write_monotonic or progress >= 1.0
            if not due:
                continue

            value = plan.value_at(now)
            if progress >= 1.0:
                value = plan.end_value
                completed.append(sensor)

            updates[sensor] = value
            plan.last_written = value
            plan.next_write_monotonic = now + plan.interval_seconds

        if updates:
            self.controller.write_targets(updates)

        if completed:
            with self.state_lock:
                for sensor in completed:
                    plan = self.curves.pop(sensor, None)
                    if plan is not None:
                        plan.status = "completed"
                        plan.finished_timestamp = plan.end_timestamp

    def _update_state(self, raw: dict[str, Any]) -> None:
        wall_time = time.time()
        time_text = datetime.now().isoformat(timespec="seconds")

        with self.state_lock:
            raw["timestamp"] = wall_time
            raw["time_text"] = time_text
            raw["connection_error"] = None

            for sensor, value in raw.get("measurements", {}).items():
                if sensor in self.history:
                    self.history[sensor].append(
                        {"timestamp": wall_time, "value": float(value)}
                    )

            alarms = raw.get("alarms", {})
            for name, alarm in alarms.items():
                active = bool(alarm.get("active"))
                previously_active = self.previous_alarm_active.get(name, False)

                active_event = next(
                    (
                        event
                        for event in self.alarm_events
                        if event.get("name") == name and event.get("active")
                    ),
                    None,
                )

                if active and not previously_active and active_event is None:
                    label = ALARM_LABELS.get(name, name)
                    message = f"{label}信号异常（输入为 0）"
                    self.alarm_acknowledged.discard(name)

                    try:
                        event = self.history_store.record_alarm_start(
                            name=name,
                            label=label,
                            timestamp=wall_time,
                            message=message,
                        )
                    except Exception as exc:
                        logger.warning("异常日志写入数据库失败：%s", exc)
                        self.alarm_sequence += 1
                        event = {
                            "id": self.alarm_sequence,
                            "name": name,
                            "label": label,
                            "time": time_text,
                            "started_timestamp": wall_time,
                            "active": True,
                            "acknowledged": False,
                            "message": message,
                            "cleared_at": None,
                            "cleared_timestamp": None,
                        }

                    self.alarm_sequence = max(
                        self.alarm_sequence,
                        int(event["id"]),
                    )
                    self.alarm_events.appendleft(event)
                    active_event = event

                # 即使服务重启后 previous=false，只要数据库里仍有未解决事件，
                # 当前信号恢复时也应立即补写恢复时间。
                if not active and active_event is not None:
                    self.alarm_acknowledged.discard(name)
                    active_event["active"] = False
                    active_event["cleared_at"] = time_text
                    active_event["cleared_timestamp"] = wall_time

                    try:
                        self.history_store.resolve_alarm(
                            int(active_event["id"]),
                            wall_time,
                        )
                    except Exception as exc:
                        logger.warning("异常恢复状态写入数据库失败：%s", exc)

                alarm["acknowledged"] = name in self.alarm_acknowledged
                self.previous_alarm_active[name] = active

            self.latest_state = raw

        try:
            self.history_store.record(
                wall_time,
                raw.get("measurements", {}),
            )
        except Exception as exc:
            logger.warning("检测数据写入历史数据库失败：%s", exc)
