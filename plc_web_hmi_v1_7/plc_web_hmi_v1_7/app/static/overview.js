"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const { formatValue, sensorConfig } = window.HMICharts;

  const cardMeta = {
    temperature: { icon: "🌡", soft: "#fff0ef" },
    humidity: { icon: "💧", soft: "#eaf5ff" },
    co2: { icon: "◌", soft: "#eaf9f1" },
    light: { icon: "☀", soft: "#fff8e7" },
  };

  document.getElementById("sensorCards").innerHTML = Object.entries(
    sensorConfig,
  )
    .map(([sensor, config]) => {
      const meta = cardMeta[sensor];
      return `
        <article class="sensor-card overview-sensor-card"
          style="--card-color:${config.color};--card-soft:${meta.soft};--card-glow:${config.color}">
          <div class="sensor-top">
            <span class="sensor-label">${config.label}</span>
            <span class="sensor-icon">${meta.icon}</span>
          </div>
          <div class="sensor-value">
            <strong id="${sensor}Value">--</strong>
            <span>${config.unit}</span>
          </div>
          <div class="sensor-footer compact-footer">
            <span>目标：<b id="${sensor}Target">--</b> ${config.unit}</span>
            <span id="${sensor}State" class="sensor-state off">--</span>
          </div>
        </article>
      `;
    })
    .join("");

  function renderState(state) {
    Object.keys(sensorConfig).forEach((sensor) => {
      const value = state.measurements?.[sensor];
      const target = state.targets?.[sensor];

      document.getElementById(`${sensor}Value`).textContent =
        formatValue(sensor, value);
      document.getElementById(`${sensor}Target`).textContent =
        formatValue(sensor, target);

      const stateElement = document.getElementById(`${sensor}State`);
      if (sensor === "light") {
        const running = Boolean(value);
        stateElement.textContent = running ? "运行" : "停止";
        stateElement.classList.toggle("off", !running);
      } else {
        stateElement.textContent = state.connected ? "在线" : "离线";
        stateElement.classList.toggle("off", !state.connected);
      }
    });

    const runLabels = state.run_status_labels || {};
    document.getElementById("overviewRunStatus").innerHTML =
      Object.entries(state.run_status || {})
        .map(
          ([name, running]) => `
            <div class="status-item compact-status-item">
              <span class="status-lamp ${running ? "on" : ""}"></span>
              <span>${window.HMI.escapeHtml(
                runLabels[name] || name,
              )}</span>
              <b>${running ? "运行" : "停止"}</b>
            </div>
          `,
        )
        .join("");

    const alarmLabels = state.alarm_labels || {};
    const activeCount = Number(state.active_alarm_count || 0);

    document.getElementById(
      "overviewAlarmCount",
    ).textContent = `${activeCount} 项异常`;
    document.getElementById(
      "overviewAlarmCount",
    ).classList.toggle("active", activeCount > 0);

    document.getElementById("overviewAlarmSignals").innerHTML =
      Object.entries(state.alarms || {})
        .map(
          ([name, alarm]) => `
            <div class="alarm-signal compact-alarm-signal ${
              alarm.active ? "active" : ""
            }">
              <span>${window.HMI.escapeHtml(
                alarmLabels[name] || name,
              )}</span>
              <b>${alarm.active ? "异常" : "正常"}</b>
            </div>
          `,
        )
        .join("");

    const message = document.getElementById("overviewAlarmMessage");
    message.className = `overview-alarm-message ${
      activeCount ? "active" : "normal"
    }`;
    message.textContent = activeCount
      ? `检测到 ${activeCount} 项异常，请检查设备状态并及时处理。`
      : "当前四项报警信号正常";
  }

  window.HMI.subscribe(renderState);
});
