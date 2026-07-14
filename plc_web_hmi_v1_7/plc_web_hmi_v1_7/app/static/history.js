"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const { LineChart, formatValue, sensorConfig } = window.HMICharts;

  let queryRows = [];
  let querySensors = [];
  let queryMeta = null;
  let currentPage = 1;

  function queriedPoints(sensor) {
    return queryRows
      .filter(
        (row) =>
          row[sensor] !== null && row[sensor] !== undefined,
      )
      .map((row) => ({
        timestamp: Number(row.timestamp),
        value: Number(row[sensor]),
      }));
  }

  function selectedDomain() {
    if (!queryMeta) return null;

    return {
      start: Number(queryMeta.start_timestamp),
      end: Number(queryMeta.end_timestamp),
    };
  }

  const charts = {
    temperature: new LineChart(
      document.getElementById("historyTemperatureChart"),
      "temperature",
      () => queriedPoints("temperature"),
      selectedDomain,
      "所选时间范围暂无温度数据",
      { showMiddleTime: false },
    ),
    humidity: new LineChart(
      document.getElementById("historyHumidityChart"),
      "humidity",
      () => queriedPoints("humidity"),
      selectedDomain,
      "所选时间范围暂无湿度数据",
      { showMiddleTime: false },
    ),
    co2: new LineChart(
      document.getElementById("historyCo2Chart"),
      "co2",
      () => queriedPoints("co2"),
      selectedDomain,
      "所选时间范围暂无 CO₂ 数据",
      { showMiddleTime: false },
    ),
    light: new LineChart(
      document.getElementById("historyLightChart"),
      "light",
      () => queriedPoints("light"),
      selectedDomain,
      "所选时间范围暂无灯组数据",
      { showMiddleTime: false },
    ),
  };

  function drawCharts() {
    Object.values(charts).forEach((chart) => chart.draw());
  }

  function toDatetimeLocal(date) {
    const pad = (number) => String(number).padStart(2, "0");

    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-` +
      `${pad(date.getDate())}T${pad(date.getHours())}:` +
      `${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    );
  }

  function setHistoryRange(hours) {
    const end = new Date();
    const start = new Date(end.getTime() - hours * 3600000);

    document.getElementById("historyStart").value =
      toDatetimeLocal(start);
    document.getElementById("historyEnd").value =
      toDatetimeLocal(end);

    document.querySelectorAll("[data-range-hours]").forEach((button) => {
      button.classList.toggle(
        "active",
        Number(button.dataset.rangeHours) === hours,
      );
    });
  }

  function selectedSensors() {
    return [
      ...document.querySelectorAll(
        'input[name="historySensor"]:checked',
      ),
    ].map((input) => input.value);
  }

  function intervalSeconds() {
    return (
      Number(document.getElementById("historyIntervalValue").value) *
      Number(document.getElementById("historyIntervalUnit").value)
    );
  }

  function requestPayload(exportMode = false) {
    const startText = document.getElementById("historyStart").value;
    const endText = document.getElementById("historyEnd").value;
    const sensors = selectedSensors();
    const interval = intervalSeconds();

    if (!startText || !endText) {
      throw new Error("请选择开始和结束时间");
    }

    const start = new Date(startText);
    const end = new Date(endText);

    if (
      Number.isNaN(start.getTime()) ||
      Number.isNaN(end.getTime())
    ) {
      throw new Error("时间格式无效");
    }
    if (end <= start) {
      throw new Error("结束时间必须晚于开始时间");
    }
    if (!sensors.length) {
      throw new Error("至少选择一个检测参数");
    }
    if (interval < 1 || interval > 86400) {
      throw new Error("采样周期必须在 1 秒～24 小时之间");
    }

    return {
      start_timestamp: start.getTime() / 1000,
      end_timestamp: end.getTime() / 1000,
      interval_seconds: interval,
      sensors,
      limit: exportMode ? 200000 : 5000,
    };
  }

  async function loadMeta() {
    try {
      const meta = await window.HMI.apiRequest("/api/history/meta");
      const size = (
        Number(meta.database_size_bytes || 0) /
        1024 /
        1024
      ).toFixed(2);

      document.getElementById("historyMeta").textContent =
        meta.raw_count
          ? `已归档 ${Number(meta.raw_count).toLocaleString(
              "zh-CN",
            )} 条 · ${meta.min_time_text?.replace(
              "T",
              " ",
            )} 至 ${meta.max_time_text?.replace(
              "T",
              " ",
            )} · ${size} MB · 保留 ${meta.retention_days} 天`
          : `历史数据库已就绪，当前尚无记录 · 保留 ${meta.retention_days} 天`;
    } catch (error) {
      document.getElementById(
        "historyMeta",
      ).textContent = `归档信息读取失败：${error.message}`;
    }
  }

  function formatDuration(seconds) {
    if (seconds % 3600 === 0) {
      return `${seconds / 3600} 小时`;
    }
    if (seconds % 60 === 0) {
      return `${seconds / 60} 分钟`;
    }
    return `${seconds} 秒`;
  }

  function renderSummary() {
    const cards = [
      `
        <article class="history-summary-card">
          <span>返回记录</span>
          <strong>${queryMeta.returned_count.toLocaleString(
            "zh-CN",
          )}</strong>
          <small>原始 ${queryMeta.raw_count.toLocaleString(
            "zh-CN",
          )} 条</small>
        </article>
      `,
    ];

    querySensors.forEach((sensor) => {
      const statistics = queryMeta.statistics?.[sensor];
      const config = sensorConfig[sensor];

      if (!statistics) return;

      if (sensor === "light") {
        cards.push(`
          <article class="history-summary-card">
            <span>${config.label}</span>
            <strong>${(statistics.on_ratio * 100).toFixed(1)}% ON</strong>
            <small>开启 ${statistics.on_count} 条 · 关闭 ${statistics.off_count} 条</small>
          </article>
        `);
      } else {
        cards.push(`
          <article class="history-summary-card">
            <span>${config.label}平均值</span>
            <strong>${formatValue(sensor, statistics.avg)} ${
              config.unit
            }</strong>
            <small>最小 ${formatValue(
              sensor,
              statistics.min,
            )} · 最大 ${formatValue(sensor, statistics.max)}</small>
          </article>
        `);
      }
    });

    document.getElementById("historySummary").innerHTML =
      cards.join("");
  }

  function renderTable() {
    const pageSize = Number(
      document.getElementById("historyPageSize").value,
    );
    const totalPages = Math.max(
      1,
      Math.ceil(queryRows.length / pageSize),
    );

    currentPage = Math.min(
      Math.max(1, currentPage),
      totalPages,
    );

    const startIndex = (currentPage - 1) * pageSize;
    const rows = queryRows.slice(
      startIndex,
      startIndex + pageSize,
    );

    document.getElementById("historyTableHead").innerHTML = `
      <tr>
        <th>检测时间</th>
        ${querySensors
          .map(
            (sensor) => `
              <th>
                ${sensorConfig[sensor].label}${
                  sensorConfig[sensor].unit
                    ? ` (${sensorConfig[sensor].unit})`
                    : ""
                }
              </th>
            `,
          )
          .join("")}
      </tr>
    `;

    document.getElementById("historyTableBody").innerHTML =
      rows.length
        ? rows
            .map(
              (row) => `
                <tr>
                  <td>${window.HMI.escapeHtml(
                    row.time_text.replace("T", " "),
                  )}</td>
                  ${querySensors
                    .map(
                      (sensor) =>
                        `<td>${formatValue(
                          sensor,
                          row[sensor],
                        )}</td>`,
                    )
                    .join("")}
                </tr>
              `,
            )
            .join("")
        : `
          <tr>
            <td class="empty-cell" colspan="${
              querySensors.length + 1
            }">所选时间段暂无数据</td>
          </tr>
        `;

    document.getElementById(
      "historyPageInfo",
    ).textContent = `第 ${
      queryRows.length ? currentPage : 0
    } / ${
      queryRows.length ? totalPages : 0
    } 页 · 共 ${queryRows.length} 条`;

    document.getElementById("historyPrevBtn").disabled =
      currentPage <= 1;
    document.getElementById("historyNextBtn").disabled =
      currentPage >= totalPages;
  }

  function renderResult() {
    document.getElementById(
      "historyResultNote",
    ).textContent =
      `${queryMeta.start_time_text.replace(
        "T",
        " ",
      )} 至 ${queryMeta.end_time_text.replace(
        "T",
        " ",
      )} · 原始 ${queryMeta.raw_count.toLocaleString(
        "zh-CN",
      )} 条 · 采样后 ${queryMeta.sampled_count.toLocaleString(
        "zh-CN",
      )} 条 · 周期 ${formatDuration(
        queryMeta.interval_seconds,
      )}${queryMeta.truncated ? " · 页面最多显示 5000 条" : ""}`;

    document.querySelectorAll(".history-chart-card").forEach((card) => {
      card.classList.toggle(
        "is-hidden",
        !querySensors.includes(card.dataset.historySensor),
      );
    });

    renderSummary();
    renderTable();

    // Wait until hidden/visible state has settled before measuring canvas.
    requestAnimationFrame(() => {
      drawCharts();
    });
  }

  async function queryHistory() {
    const payload = requestPayload(false);
    const button = document.getElementById("historyQueryBtn");
    const message = document.getElementById("historyActionMessage");

    button.disabled = true;
    button.textContent = "查询中…";
    message.className = "action-message";
    message.textContent = "正在读取历史数据库并生成曲线…";

    try {
      const result = await window.HMI.apiRequest(
        "/api/history/query",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );

      queryRows = result.rows;
      querySensors = result.sensors;
      queryMeta = result;
      currentPage = 1;
      renderResult();

      message.className = result.returned_count
        ? "action-message success"
        : "action-message warning";
      message.textContent = result.returned_count
        ? `查询成功：返回 ${result.returned_count} 条采样记录，曲线横轴已固定为所选完整时间范围。`
        : "查询成功，但所选时间段尚无检测数据。";

      window.HMI.showToast(
        result.returned_count
          ? `已读取 ${result.returned_count} 条采样记录`
          : "所选时间段暂无数据",
        !result.returned_count,
      );
    } catch (error) {
      message.className = "action-message error";
      message.textContent = `查询失败：${error.message}`;
      window.HMI.showToast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = "查询并绘图";
    }
  }

  function filenameFromDisposition(disposition) {
    if (!disposition) return null;

    const utf8Match = disposition.match(
      /filename\*=UTF-8''([^;]+)/i,
    );
    if (utf8Match) return decodeURIComponent(utf8Match[1]);

    const regularMatch = disposition.match(/filename="?([^"]+)"?/i);
    return regularMatch ? regularMatch[1] : null;
  }

  async function exportHistory() {
    const button = document.getElementById("historyExportBtn");
    const message = document.getElementById("historyActionMessage");

    button.disabled = true;
    button.textContent = "生成中…";
    message.className = "action-message";
    message.textContent = "正在生成 CSV 文件…";

    try {
      const payload = requestPayload(true);
      const response = await window.HMI.apiRequest(
        "/api/history/export",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );

      const blob = await response.blob();
      const filename =
        filenameFromDisposition(
          response.headers.get("content-disposition"),
        ) || "检测数据.csv";
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      setTimeout(() => URL.revokeObjectURL(url), 1000);

      const rows = response.headers.get("x-export-rows");
      message.className = "action-message success";
      message.textContent = `导出成功：${filename}${
        rows ? `，共 ${rows} 条记录` : ""
      }。`;
      window.HMI.showToast("CSV 文件已开始下载");
    } catch (error) {
      message.className = "action-message error";
      message.textContent = `导出失败：${error.message}`;
      window.HMI.showToast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = "下载 CSV";
    }
  }

  document.querySelectorAll("[data-range-hours]").forEach((button) => {
    button.addEventListener("click", () => {
      setHistoryRange(Number(button.dataset.rangeHours));
    });
  });

  document.getElementById("historyForm").addEventListener(
    "submit",
    async (event) => {
      event.preventDefault();
      await queryHistory();
    },
  );

  document.getElementById("historyExportBtn").addEventListener(
    "click",
    exportHistory,
  );

  document.getElementById("historyPageSize").addEventListener(
    "change",
    () => {
      currentPage = 1;
      renderTable();
    },
  );

  document.getElementById("historyPrevBtn").addEventListener(
    "click",
    () => {
      currentPage -= 1;
      renderTable();
    },
  );

  document.getElementById("historyNextBtn").addEventListener(
    "click",
    () => {
      currentPage += 1;
      renderTable();
    },
  );

  setHistoryRange(1);
  loadMeta();
});
