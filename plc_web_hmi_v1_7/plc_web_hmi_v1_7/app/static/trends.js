"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const { LineChart } = window.HMICharts;
  const data = {
    temperature: [],
    humidity: [],
    co2: [],
    light: [],
  };

  let domain = {
    start: Date.now() / 1000 - 900,
    end: Date.now() / 1000,
  };
  let loading = false;
  let lastLiveTimestamp = 0;

  const charts = Object.fromEntries(
    Object.keys(data).map((sensor) => [
      sensor,
      new LineChart(
        document.getElementById(`${sensor}Chart`),
        sensor,
        () => data[sensor],
        () => domain,
        "该时间范围暂无检测数据",
      ),
    ]),
  );

  function drawCharts() {
    Object.values(charts).forEach((chart) => chart.draw());
  }

  function selectedRange() {
    return Number(document.getElementById("timeRange").value);
  }

  async function loadRecentHistory() {
    if (loading) return;

    loading = true;
    const button = document.getElementById("refreshRealtimeBtn");
    const note = document.getElementById("realtimeChartNote");
    const rangeSeconds = selectedRange();

    button.disabled = true;
    button.textContent = "读取中…";
    note.className = "result-strip";
    note.textContent = "正在从历史数据库读取曲线…";

    try {
      const result = await window.HMI.apiRequest(
        `/api/history/recent?range_seconds=${rangeSeconds}&max_points=1200`,
      );

      Object.keys(data).forEach((sensor) => {
        data[sensor] = result.rows
          .filter(
            (row) =>
              row[sensor] !== null && row[sensor] !== undefined,
          )
          .map((row) => ({
            timestamp: Number(row.timestamp),
            value: Number(row[sensor]),
          }));
      });

      domain = {
        start: Number(result.start_timestamp),
        end: Number(result.end_timestamp),
      };
      lastLiveTimestamp = Math.max(
        0,
        ...result.rows.map((row) => Number(row.timestamp)),
      );

      note.textContent = result.returned_count
        ? `显示 ${result.returned_count} 个采样点 · 自适应采样周期 ${result.interval_seconds} 秒`
        : "当前时间范围尚无已归档数据；新数据到达后会自动绘制。";
      note.className = result.returned_count
        ? "result-strip success"
        : "result-strip warning";

      drawCharts();
    } catch (error) {
      note.textContent = `曲线读取失败：${error.message}`;
      note.className = "result-strip error";
      window.HMI.showToast(error.message, true);
    } finally {
      loading = false;
      button.disabled = false;
      button.textContent = "刷新曲线";
    }
  }

  function appendLiveState(state) {
    if (
      !state.timestamp ||
      state.timestamp <= lastLiveTimestamp ||
      !state.measurements
    ) {
      return;
    }

    const timestamp = Number(state.timestamp);
    const rangeSeconds = selectedRange();
    const cutoff = timestamp - rangeSeconds;

    Object.keys(data).forEach((sensor) => {
      const value = state.measurements[sensor];
      if (value === undefined || value === null) return;

      data[sensor].push({
        timestamp,
        value: Number(value),
      });
      data[sensor] = data[sensor].filter(
        (point) => point.timestamp >= cutoff,
      );
    });

    lastLiveTimestamp = timestamp;
    domain = {
      start: timestamp - rangeSeconds,
      end: timestamp,
    };
    drawCharts();
  }

  document.getElementById("timeRange").addEventListener(
    "change",
    loadRecentHistory,
  );
  document.getElementById("refreshRealtimeBtn").addEventListener(
    "click",
    loadRecentHistory,
  );

  window.HMI.subscribe(appendLiveState);
  loadRecentHistory();
  setInterval(loadRecentHistory, 60000);
});
