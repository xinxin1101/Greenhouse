"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const {
    OverlayLineChart,
    formatValue,
    sensorConfig,
  } = window.HMICharts;
  const pendingControls = new Set();

  const definitions = {
    system: {
      label: "系统总控制",
      detail: "与紫外互锁；不含压机、紫外和 CO₂",
      runKey: null,
    },
    compressor: {
      label: "压机",
      detail: "独立控制；停机保护 180 秒",
      runKey: "compressor",
      dangerous: true,
    },
    uv: {
      label: "紫外",
      detail: "与系统总控制互锁",
      runKey: "uv",
      dangerous: true,
    },
    co2: {
      label: "CO₂",
      detail: "独立控制",
      runKey: "co2",
      dangerous: true,
    },
    fresh_air: {
      label: "新风",
      detail: "第 1 段全天有效",
      runKey: "fresh_air",
    },
    lamp: {
      label: "灯组",
      detail: "目标 M14.0，状态 Q1.1",
      runKey: "lamp_group",
    },
  };

  const trace = {
    sensor: "temperature",
    plan: null,
    actual: [],
    lastTimestamp: 0,
    loading: false,
  };

  const traceChart = new OverlayLineChart(
    document.getElementById("curveTraceChart"),
    () => trace.sensor,
    () => {
      if (!trace.plan) return [];

      return [
        {
          label: "预设曲线",
          color: "#1769e0",
          dash: [8, 6],
          width: 2.2,
          points: presetPoints(trace.plan),
        },
        {
          label: "实际检测曲线",
          color: sensorConfig[trace.sensor].color,
          width: 2,
          markLast: true,
          points: trace.actual,
        },
      ];
    },
    () =>
      trace.plan
        ? {
            start: trace.plan.start_timestamp,
            end: trace.plan.end_timestamp,
          }
        : null,
    "尚未设置该参数的预设曲线",
  );

  document.getElementById("controlGrid").innerHTML = Object.entries(
    definitions,
  )
    .map(
      ([device, definition]) => `
        <article class="control-card">
          <div class="control-copy">
            <strong>${definition.label}</strong>
            <span>${definition.detail}</span>
            <em id="${device}Interlock" class="interlock-note hidden"></em>
          </div>
          <div class="control-actions">
            <span id="${device}Run" class="run-pill">--</span>
            <button
              id="${device}Toggle"
              class="toggle"
              data-device="${device}"
              type="button"
              aria-label="切换${definition.label}">
            </button>
          </div>
        </article>
      `,
    )
    .join("");

  function presetValue(plan, progress) {
    let shaped = Math.min(1, Math.max(0, progress));

    if (plan.shape === "smooth") {
      shaped = (1 - Math.cos(Math.PI * shaped)) / 2;
    } else if (plan.shape === "step") {
      shaped = shaped < 0.5 ? 0 : 1;
    }

    return (
      Number(plan.start_value) +
      (Number(plan.end_value) - Number(plan.start_value)) * shaped
    );
  }

  function presetPoints(plan) {
    const count = 160;
    const points = [];

    for (let index = 0; index <= count; index += 1) {
      const progress = index / count;
      points.push({
        timestamp:
          Number(plan.start_timestamp) +
          Number(plan.duration_seconds) * progress,
        value: presetValue(plan, progress),
      });
    }

    return points;
  }

  function statusText(status) {
    const labels = {
      running: "执行中",
      completed: "已完成",
      cancelled: "已取消",
      manual_override: "已被手动目标值替代",
      replaced: "已被新曲线替代",
    };
    return labels[status] || status || "未知";
  }

  function formatPlanTime(timestamp) {
    return new Date(Number(timestamp) * 1000).toLocaleString("zh-CN");
  }

  function renderTraceMessage() {
    const message = document.getElementById("curveTraceMessage");

    if (!trace.plan) {
      message.className = "result-strip warning";
      message.textContent = `尚未设置${
        sensorConfig[trace.sensor].label
      }预设曲线`;
      traceChart.draw();
      return;
    }

    const actualCount = trace.actual.length;
    message.className = "result-strip success";
    message.textContent =
      `${sensorConfig[trace.sensor].label} · ` +
      `${statusText(trace.plan.status)} · ` +
      `${formatPlanTime(trace.plan.start_timestamp)} 至 ` +
      `${formatPlanTime(trace.plan.end_timestamp)} · ` +
      `预设 ${formatValue(trace.sensor, trace.plan.start_value)} → ` +
      `${formatValue(trace.sensor, trace.plan.end_value)} ` +
      `${sensorConfig[trace.sensor].unit} · ` +
      `实际采样 ${actualCount} 点`;
    traceChart.draw();
  }

  async function loadCurveTrace(sensor = trace.sensor) {
    if (trace.loading) return;

    trace.loading = true;
    trace.sensor = sensor;
    const button = document.getElementById("refreshCurveTraceBtn");
    button.disabled = true;
    button.textContent = "读取中…";

    try {
      const result = await window.HMI.apiRequest(
        `/api/curves/${sensor}/trace?max_points=1200`,
      );

      trace.plan = result.plan;
      trace.actual = (result.actual?.rows || [])
        .filter(
          (row) =>
            row[sensor] !== null && row[sensor] !== undefined,
        )
        .map((row) => ({
          timestamp: Number(row.timestamp),
          value: Number(row[sensor]),
        }));
      trace.lastTimestamp = trace.actual.length
        ? trace.actual.at(-1).timestamp
        : 0;
      renderTraceMessage();
    } catch (error) {
      const message = document.getElementById("curveTraceMessage");
      message.className = "result-strip error";
      message.textContent = `曲线对比读取失败：${error.message}`;
      window.HMI.showToast(error.message, true);
    } finally {
      trace.loading = false;
      button.disabled = false;
      button.textContent = "刷新实际曲线";
    }
  }

  function appendActualPoint(state) {
    if (
      !trace.plan ||
      !state.timestamp ||
      state.measurements?.[trace.sensor] === undefined
    ) {
      return;
    }

    const timestamp = Number(state.timestamp);
    if (
      timestamp <= trace.lastTimestamp ||
      timestamp < Number(trace.plan.start_timestamp) ||
      timestamp > Number(trace.plan.end_timestamp)
    ) {
      return;
    }

    trace.actual.push({
      timestamp,
      value: Number(state.measurements[trace.sensor]),
    });
    trace.lastTimestamp = timestamp;
    renderTraceMessage();
  }

  async function toggleDevice(device) {
    const state = window.HMI.getState();
    if (!state?.connected || pendingControls.has(device)) return;

    const definition = definitions[device];
    const current = Boolean(state.controls?.[device]);
    const target = !current;
    const button = document.getElementById(`${device}Toggle`);
    const interlock = state.interlocks?.[device];

    if (target && interlock?.blocked) {
      window.HMI.showToast(interlock.reason || "设备当前处于互锁状态", true);
      return;
    }

    let prompt = `确认${target ? "开启" : "关闭"}${definition.label}？`;

    if (device === "compressor" && target) {
      prompt += "\n压机可能受 PLC 内部 180 秒停机保护和报警联锁限制。";
    }
    if (definition.dangerous && target) {
      prompt += "\n请确认现场人员与设备安全。";
    }
    if (!confirm(prompt)) return;

    pendingControls.add(device);
    button.disabled = true;
    button.classList.add("pending");

    try {
      let result;

      if (device === "fresh_air") {
        result = await window.HMI.apiRequest("/api/fan", {
          method: "POST",
          body: JSON.stringify({ state: target }),
        });
      } else if (device === "lamp") {
        result = await window.HMI.apiRequest("/api/targets", {
          method: "POST",
          body: JSON.stringify({ light: target }),
        });
      } else {
        result = await window.HMI.apiRequest("/api/control", {
          method: "POST",
          body: JSON.stringify({ device, state: target }),
        });
      }

      window.HMI.showToast(result.message);
    } catch (error) {
      window.HMI.showToast(error.message, true);
    } finally {
      pendingControls.delete(device);
      button.disabled = false;
      button.classList.remove("pending");
    }
  }

  document.querySelectorAll(".toggle").forEach((button) => {
    button.addEventListener("click", () => {
      toggleDevice(button.dataset.device);
    });
  });

  function renderCurves(curves) {
    const container = document.getElementById("activeCurves");
    const entries = Object.entries(curves);

    if (!entries.length) {
      container.className = "active-curves empty";
      container.textContent = "当前没有执行中的曲线";
      return;
    }

    container.className = "active-curves";
    container.innerHTML = entries
      .map(
        ([sensor, plan]) => `
          <div class="curve-item">
            <div class="curve-item-top">
              <span>
                <b>${sensorConfig[sensor].label}</b>
                ${formatValue(sensor, plan.start_value)}
                →
                ${formatValue(sensor, plan.end_value)}
                ${sensorConfig[sensor].unit}
                · 剩余 ${Math.ceil(plan.remaining_seconds)}s
              </span>
              <button data-cancel-curve="${sensor}" type="button">取消</button>
            </div>
            <div class="progress-track">
              <span style="width:${Math.round(plan.progress * 100)}%"></span>
            </div>
          </div>
        `,
      )
      .join("");

    container
      .querySelectorAll("[data-cancel-curve]")
      .forEach((button) => {
        button.addEventListener("click", async () => {
          try {
            const result = await window.HMI.apiRequest(
              `/api/curves/${button.dataset.cancelCurve}`,
              { method: "DELETE" },
            );
            window.HMI.showToast(result.message);
            await loadCurveTrace(button.dataset.cancelCurve);
          } catch (error) {
            window.HMI.showToast(error.message, true);
          }
        });
      });
  }

  function renderState(state) {
    const targetMap = {
      targetTemperature: "temperature",
      targetHumidity: "humidity",
      targetCo2: "co2",
    };

    Object.entries(targetMap).forEach(([id, sensor]) => {
      const input = document.getElementById(id);
      if (
        document.activeElement !== input &&
        state.targets?.[sensor] !== undefined
      ) {
        input.value = state.targets[sensor];
      }
    });

    const light = document.getElementById("targetLight");
    if (
      document.activeElement !== light &&
      state.targets?.light !== undefined
    ) {
      light.value = String(Boolean(state.targets.light));
    }

    document.getElementById(
      "feedbackTemperature",
    ).textContent = `PLC 设定反馈：${formatValue(
      "temperature",
      state.feedback?.temperature,
    )} ℃`;
    document.getElementById(
      "feedbackHumidity",
    ).textContent = `PLC 设定反馈：${formatValue(
      "humidity",
      state.feedback?.humidity,
    )} %RH`;
    document.getElementById(
      "feedbackCo2",
    ).textContent = `PLC 设定反馈：${formatValue(
      "co2",
      state.feedback?.co2,
    )} ppm`;

    const curveSensor = document.getElementById("curveSensor").value;
    const curveStart = document.getElementById("curveStart");
    if (
      document.activeElement !== curveStart &&
      state.targets?.[curveSensor] !== undefined
    ) {
      curveStart.value = state.targets[curveSensor];
    }

    Object.entries(definitions).forEach(([device, definition]) => {
      const on = Boolean(state.controls?.[device]);
      const button = document.getElementById(`${device}Toggle`);
      const interlock = state.interlocks?.[device];
      const blocked = !on && Boolean(interlock?.blocked);

      button.classList.toggle("on", on);
      button.classList.toggle("interlocked", blocked);
      button.disabled =
        !state.connected ||
        pendingControls.has(device) ||
        blocked;
      button.title = blocked
        ? interlock.reason || "设备当前处于互锁状态"
        : "";

      const lockNote = document.getElementById(`${device}Interlock`);
      if (lockNote) {
        lockNote.classList.toggle("hidden", !blocked);
        lockNote.textContent = blocked
          ? interlock.reason || "当前处于互锁状态"
          : "";
      }

      const run = document.getElementById(`${device}Run`);
      const running = definition.runKey
        ? Boolean(state.run_status?.[definition.runKey])
        : on;
      run.textContent = blocked
        ? "互锁"
        : running
          ? "运行"
          : "停止";
      run.classList.toggle("running", running);
      run.classList.toggle("locked", blocked);
    });

    renderCurves(state.curves || {});

    const serverPlan = state.curve_traces?.[trace.sensor];
    if (
      serverPlan &&
      (!trace.plan ||
        Number(serverPlan.start_timestamp) !==
          Number(trace.plan.start_timestamp))
    ) {
      loadCurveTrace(trace.sensor);
    } else if (serverPlan && trace.plan) {
      trace.plan = serverPlan;
      appendActualPoint(state);
      renderTraceMessage();
    }
  }

  document.getElementById("targetForm").addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();

      if (
        !confirm(
          "确认把目标值写入环境第 1 段？第 1 段保持 00:00～00:00 全天有效。",
        )
      ) {
        return;
      }

      const payload = {
        temperature: Number(
          document.getElementById("targetTemperature").value,
        ),
        humidity: Number(
          document.getElementById("targetHumidity").value,
        ),
        co2: Number(document.getElementById("targetCo2").value),
        light: document.getElementById("targetLight").value === "true",
      };

      try {
        const result = await window.HMI.apiRequest("/api/targets", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        window.HMI.showToast(result.message);
      } catch (error) {
        window.HMI.showToast(error.message, true);
      }
    },
  );

  document.getElementById("curveSensor").addEventListener(
    "change",
    () => {
      const state = window.HMI.getState();
      if (!state) return;

      const sensor = document.getElementById("curveSensor").value;
      document.getElementById("curveStart").value =
        state.targets?.[sensor] ?? "";
    },
  );

  document.getElementById("curveForm").addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();

      const payload = {
        sensor: document.getElementById("curveSensor").value,
        start_value: Number(
          document.getElementById("curveStart").value,
        ),
        end_value: Number(
          document.getElementById("curveEnd").value,
        ),
        duration_seconds: Number(
          document.getElementById("curveDuration").value,
        ),
        interval_seconds: Number(
          document.getElementById("curveInterval").value,
        ),
        shape: document.getElementById("curveShape").value,
      };

      if (
        !confirm(
          `确认启动${sensorConfig[payload.sensor].label}曲线？后端每 ${payload.interval_seconds} 秒写一次 PLC。`,
        )
      ) {
        return;
      }

      try {
        const result = await window.HMI.apiRequest("/api/curves", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        document.getElementById("curveTraceSensor").value =
          payload.sensor;
        trace.sensor = payload.sensor;
        trace.plan = result.curve || null;
        trace.actual = [];
        trace.lastTimestamp = 0;
        renderTraceMessage();

        window.HMI.showToast(result.message);
        setTimeout(() => loadCurveTrace(payload.sensor), 700);
      } catch (error) {
        window.HMI.showToast(error.message, true);
      }
    },
  );

  document.getElementById("curveTraceSensor").addEventListener(
    "change",
    (event) => {
      trace.sensor = event.target.value;
      trace.plan = null;
      trace.actual = [];
      trace.lastTimestamp = 0;
      loadCurveTrace(trace.sensor);
    },
  );

  document.getElementById("refreshCurveTraceBtn").addEventListener(
    "click",
    () => loadCurveTrace(trace.sensor),
  );

  window.HMI.subscribe(renderState);
  loadCurveTrace("temperature");
  setInterval(() => loadCurveTrace(trace.sensor), 15000);
});
