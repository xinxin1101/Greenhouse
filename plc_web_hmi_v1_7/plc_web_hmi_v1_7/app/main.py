from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .models import (
    AlarmAcknowledgementRequest,
    AlarmBulkAcknowledgementRequest,
    ControlRequest,
    CurveRequest,
    FanRequest,
    HistoryQueryRequest,
    TargetUpdate,
)
from .service import PLCService


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

config = load_config()
service = PLCService(config)
logger = logging.getLogger("plc_hmi.api")


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        disconnected: list[WebSocket] = []

        for websocket in self.connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


manager = ConnectionManager()


def html_page(filename: str) -> FileResponse:
    return FileResponse(
        STATIC_DIR / filename,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-HMI-Version": "1.7.0",
        },
    )


async def broadcaster() -> None:
    while True:
        await manager.broadcast(service.snapshot(include_history=False))
        await asyncio.sleep(1.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.start()
    broadcast_task = asyncio.create_task(broadcaster())

    yield

    broadcast_task.cancel()
    await asyncio.gather(broadcast_task, return_exceptions=True)
    service.stop()


app = FastAPI(
    title="S7-200 SMART 环境控制平台",
    version="1.7.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Actual separate pages
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/overview", status_code=307)


@app.get("/overview", include_in_schema=False)
async def overview_page() -> FileResponse:
    return html_page("overview.html")


@app.get("/trends", include_in_schema=False)
async def trends_page() -> FileResponse:
    return html_page("trends.html")


@app.get("/control", include_in_schema=False)
async def control_page() -> FileResponse:
    return html_page("control.html")


@app.get("/status", include_in_schema=False)
async def legacy_status_page() -> RedirectResponse:
    # v1.5 起不再保留独立“运行与报警”页面。
    return RedirectResponse(url="/overview", status_code=307)


@app.get("/history", include_in_schema=False)
async def history_page() -> FileResponse:
    return html_page("history.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# State and PLC commands
# ---------------------------------------------------------------------------

@app.get("/api/version")
async def get_version() -> dict:
    return {
        "version": "1.7.0",
        "pages": ["/overview", "/trends", "/control", "/history"],
        "status_page_removed": True,
    }


@app.get("/api/state")
async def get_state() -> dict:
    return service.snapshot(include_history=False)


async def run_command(action: str, payload: dict | None = None) -> dict:
    command_payload = payload or {}

    try:
        return await asyncio.to_thread(
            service.submit,
            action,
            command_payload,
        )
    except ValueError as exc:
        logger.warning(
            "API 命令参数或状态无效：action=%s payload=%s error=%s",
            action,
            command_payload,
            exc,
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (TimeoutError, RuntimeError) as exc:
        logger.warning(
            "API 命令失败：action=%s payload=%s error=%s",
            action,
            command_payload,
            exc,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/targets")
async def set_targets(request: TargetUpdate) -> dict:
    return await run_command(
        "set_targets",
        request.model_dump(exclude_none=True),
    )


@app.post("/api/control")
async def set_control(request: ControlRequest) -> dict:
    return await run_command("set_control", request.model_dump())


@app.post("/api/fan")
async def set_fan(request: FanRequest) -> dict:
    return await run_command("set_fan", request.model_dump())


@app.post("/api/curves")
async def start_curve(request: CurveRequest) -> dict:
    return await run_command("start_curve", request.model_dump())


@app.get("/api/curves/{sensor}/trace")
async def get_curve_trace(
    sensor: str,
    max_points: int = Query(1200, ge=100, le=5000),
) -> dict:
    try:
        return await asyncio.to_thread(
            service.curve_trace,
            sensor,
            max_points,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/curves/{sensor}")
async def cancel_curve(sensor: str) -> dict:
    if sensor not in {"temperature", "humidity", "co2"}:
        raise HTTPException(status_code=404, detail="未知曲线参数")
    return await run_command("cancel_curve", {"sensor": sensor})


@app.get("/api/alarms/log")
async def get_alarm_log(
    limit: int = Query(500, ge=1, le=5000),
) -> dict:
    try:
        return await asyncio.to_thread(service.alarm_log, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/alarms/ack")
async def acknowledge_alarms() -> dict:
    return await run_command("ack_alarms")


@app.post("/api/alarms/ack-all")
async def acknowledge_all_alarms(request: AlarmBulkAcknowledgementRequest) -> dict:
    return await run_command("ack_all_alarms", request.model_dump())


@app.post("/api/alarms/{event_id}/ack")
async def acknowledge_alarm_event(event_id: int, request: AlarmAcknowledgementRequest) -> dict:
    return await run_command(
        "ack_alarm_event",
        {"event_id": event_id, **request.model_dump()},
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.get("/api/history/meta")
async def history_meta() -> dict:
    return await asyncio.to_thread(service.history_meta)


@app.post("/api/history/query")
async def query_history(request: HistoryQueryRequest) -> dict:
    try:
        return await asyncio.to_thread(
            service.query_history,
            request.start_timestamp,
            request.end_timestamp,
            request.interval_seconds,
            request.sensors,
            request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/history/recent")
async def recent_history(
    range_seconds: int = Query(900, ge=60, le=86400),
    max_points: int = Query(1200, ge=100, le=5000),
) -> dict:
    """
    Realtime overview supports 1 minute to 1 day.
    Data is loaded from SQLite and adaptively sampled to avoid sending tens
    of thousands of points to the browser.
    """
    end_timestamp = time.time()
    start_timestamp = end_timestamp - range_seconds
    interval_seconds = max(1, math.ceil(range_seconds / max_points))

    try:
        result = await asyncio.to_thread(
            service.query_history,
            start_timestamp,
            end_timestamp,
            interval_seconds,
            ["temperature", "humidity", "co2", "light"],
            max_points + 10,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result["requested_range_seconds"] = range_seconds
    return result


def format_export_value(sensor: str, value):
    if value is None:
        return ""
    if sensor == "light":
        return int(value)
    if sensor in {"temperature", "humidity"}:
        return f"{float(value):.2f}"
    if sensor == "co2":
        return f"{float(value):.1f}"
    return value


def create_csv_response(result: dict, selected: list[str]) -> Response:
    labels = {
        "temperature": "温度(℃)",
        "humidity": "湿度(%RH)",
        "co2": "CO₂(ppm)",
        "light": "灯组状态(0关1开)",
    }

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["检测时间", *[labels[name] for name in selected]])

    for row in result["rows"]:
        writer.writerow(
            [
                row["time_text"].replace("T", " "),
                *[
                    format_export_value(name, row.get(name))
                    for name in selected
                ],
            ]
        )

    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    start_name = datetime.fromtimestamp(
        result["start_timestamp"]
    ).strftime("%Y%m%d_%H%M%S")
    end_name = datetime.fromtimestamp(
        result["end_timestamp"]
    ).strftime("%Y%m%d_%H%M%S")
    interval = result["interval_seconds"]
    filename = f"检测数据_{start_name}_{end_name}_{interval:g}s.csv"

    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            ),
            "X-Export-Rows": str(result["returned_count"]),
        },
    )


@app.post("/api/history/export")
async def export_history(request: HistoryQueryRequest) -> Response:
    # Export supports much more data than on-screen preview.
    export_limit = min(max(request.limit, 1), 200000)

    try:
        result = await asyncio.to_thread(
            service.query_history,
            request.start_timestamp,
            request.end_timestamp,
            request.interval_seconds,
            request.sensors,
            export_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result["truncated"]:
        raise HTTPException(
            status_code=413,
            detail="导出数据超过 20 万行，请缩短时间范围或增大采样周期",
        )

    if not result["rows"]:
        raise HTTPException(
            status_code=404,
            detail="所选时间段暂无检测数据，未生成文件",
        )

    return create_csv_response(result, request.sensors)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)

    try:
        await websocket.send_json(service.snapshot(include_history=False))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)
