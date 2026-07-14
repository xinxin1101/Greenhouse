"use strict";

window.HMI = (() => {
  let socket = null;
  let reconnectTimer = null;
  let pingTimer = null;
  let latestState = null;
  let alarmUiReady = false;
  let alarmPopupOpen = false;
  let audioContext = null;
  const subscribers = new Set();

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatClock(timestamp) {
    if (!timestamp) return "--";
    return new Date(timestamp * 1000).toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function formatDateTime(timestamp) {
    if (!timestamp) return "--";
    return new Date(timestamp * 1000).toLocaleString("zh-CN");
  }

  function showToast(message, error = false) {
    const toast = document.getElementById("toast");
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast show ${error ? "error" : ""}`;

    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
      toast.className = "toast";
    }, 3800);
  }

  async function apiRequest(url, options = {}) {
    const headers = { ...(options.headers || {}) };

    if (options.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let message = `请求失败：${response.status}`;

      try {
        const payload = await response.json();
        message = payload.detail || message;
      } catch (_) {
        const text = await response.text().catch(() => "");
        if (text) message = text;
      }

      throw new Error(message);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return response;
  }

  function updateConnection(state) {
    const online = Boolean(state.connected);
    const dot = document.getElementById("connectionDot");
    const text = document.getElementById("connectionText");
    const detail = document.getElementById("connectionDetail");
    const lastUpdate = document.getElementById("lastUpdate");
    const mode = document.getElementById("modeBadge");
    const banner = document.getElementById("connectionBanner");

    if (dot) dot.className = `status-dot ${online ? "online" : "offline"}`;
    if (text) text.textContent = online ? "PLC 连接正常" : "PLC 连接已断开";
    if (detail) detail.textContent = `${state.plc_ip || "192.168.2.1"}:102`;
    if (lastUpdate) {
      lastUpdate.textContent = state.timestamp
        ? `最近更新：${formatClock(state.timestamp)}`
        : "尚未收到数据";
    }
    if (mode) {
      mode.textContent =
        state.mode === "simulation" ? "模拟模式" : "PLC 模式";
    }

    if (banner) {
      banner.classList.toggle("hidden", online);
      if (!online) {
        banner.textContent = `PLC 当前未连接：${
          state.connection_error || "正在自动重连"
        }`;
      }
    }
  }

  function ensureAlarmUi() {
    if (alarmUiReady) return;

    document.body.insertAdjacentHTML(
      "beforeend",
      `
      <div id="alarmPopupOverlay" class="modal-overlay hidden" role="dialog" aria-modal="true">
        <section class="modal-card alarm-popup-card">
          <div class="modal-header danger-header">
            <div>
              <span class="modal-kicker">NEW ALARM</span>
              <h3>检测到新的异常</h3>
            </div>
            <button id="alarmPopupClose" class="modal-close" type="button" aria-label="关闭">×</button>
          </div>
          <div id="alarmPopupContent" class="alarm-popup-content"></div>
          <div class="modal-actions">
            <button id="alarmPopupLogBtn" class="button secondary" type="button">查看异常日志</button>
            <button id="alarmPopupConfirmBtn" class="button danger-button" type="button">我知道了</button>
          </div>
        </section>
      </div>

      <div id="alarmLogOverlay" class="modal-overlay hidden" role="dialog" aria-modal="true">
        <section class="modal-card alarm-log-card">
          <div class="modal-header">
            <div>
              <span class="modal-kicker">ALARM LOG</span>
              <h3>异常日志</h3>
              <p>当前未解决的异常标红；已恢复的异常使用普通样式。</p>
            </div>
            <button id="alarmLogClose" class="modal-close" type="button" aria-label="关闭">×</button>
          </div>
          <div class="alarm-log-toolbar">
            <span id="alarmLogSummary">正在读取异常日志…</span>
            <button id="alarmLogRefresh" class="button compact-button secondary" type="button">刷新</button>
          </div>
          <div id="alarmLogList" class="alarm-log-list"></div>
        </section>
      </div>
      `,
    );

    const popupOverlay = document.getElementById("alarmPopupOverlay");
    const logOverlay = document.getElementById("alarmLogOverlay");

    function closePopup() {
      popupOverlay.classList.add("hidden");
      alarmPopupOpen = false;
    }

    function closeLog() {
      logOverlay.classList.add("hidden");
    }

    document.getElementById("alarmPopupClose").addEventListener(
      "click",
      closePopup,
    );
    document.getElementById("alarmPopupConfirmBtn").addEventListener(
      "click",
      closePopup,
    );
    document.getElementById("alarmPopupLogBtn").addEventListener(
      "click",
      async () => {
        closePopup();
        await openAlarmLog();
      },
    );
    document.getElementById("alarmLogClose").addEventListener(
      "click",
      closeLog,
    );
    document.getElementById("alarmLogRefresh").addEventListener(
      "click",
      openAlarmLog,
    );

    popupOverlay.addEventListener("click", (event) => {
      if (event.target === popupOverlay) closePopup();
    });
    logOverlay.addEventListener("click", (event) => {
      if (event.target === logOverlay) closeLog();
    });

    const pageLogButton = document.getElementById("openAlarmLogBtn");
    if (pageLogButton) {
      pageLogButton.addEventListener("click", openAlarmLog);
    }

    alarmUiReady = true;
  }

  function playAlarmTone() {
    try {
      audioContext ||= new (
        window.AudioContext || window.webkitAudioContext
      )();

      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();

      oscillator.frequency.value = 880;
      oscillator.type = "square";
      gain.gain.setValueAtTime(0.0001, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(
        0.13,
        audioContext.currentTime + 0.02,
      );
      gain.gain.exponentialRampToValueAtTime(
        0.0001,
        audioContext.currentTime + 0.45,
      );

      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.46);
    } catch (_) {
      // 浏览器未授权音频时仍会显示弹窗。
    }
  }

  function showAlarmPopup(events) {
    ensureAlarmUi();

    const activeEvents = events.filter((event) => event.active);
    if (!activeEvents.length) return;

    document.getElementById("alarmPopupContent").innerHTML =
      activeEvents
        .map(
          (event) => `
            <article class="alarm-popup-item">
              <div class="alarm-popup-icon">!</div>
              <div>
                <strong>${escapeHtml(event.label)}</strong>
                <p>${escapeHtml(event.message)}</p>
                <time>${escapeHtml(
                  String(event.time || "").replace("T", " "),
                )}</time>
              </div>
            </article>
          `,
        )
        .join("");

    document
      .getElementById("alarmPopupOverlay")
      .classList.remove("hidden");
    alarmPopupOpen = true;
    playAlarmTone();
  }

  function handleNewAlarmEvents(state) {
    const events = Array.isArray(state.alarm_events)
      ? state.alarm_events
      : [];
    if (!events.length) return;

    const maximumId = Math.max(
      0,
      ...events.map((event) => Number(event.id) || 0),
    );
    const storedId = Number(
      sessionStorage.getItem("hmi_last_alarm_event_id") || 0,
    );

    const newActiveEvents = events
      .filter(
        (event) =>
          Boolean(event.active) &&
          Number(event.id) > storedId,
      )
      .sort((a, b) => Number(a.id) - Number(b.id));

    if (maximumId > storedId) {
      sessionStorage.setItem(
        "hmi_last_alarm_event_id",
        String(maximumId),
      );
    }

    if (newActiveEvents.length && !alarmPopupOpen) {
      showAlarmPopup(newActiveEvents);
    }
  }

  async function openAlarmLog() {
    ensureAlarmUi();

    const overlay = document.getElementById("alarmLogOverlay");
    const list = document.getElementById("alarmLogList");
    const summary = document.getElementById("alarmLogSummary");

    overlay.classList.remove("hidden");
    list.innerHTML =
      '<div class="alarm-log-empty">正在读取异常日志…</div>';
    summary.textContent = "正在读取异常日志…";

    try {
      const result = await apiRequest("/api/alarms/log?limit=500");
      const events = result.events || [];

      summary.textContent =
        `共 ${result.count} 条记录 · ` +
        `${result.active_count} 条当前未解决`;

      if (!events.length) {
        list.innerHTML =
          '<div class="alarm-log-empty">当前还没有异常记录</div>';
        return;
      }

      list.innerHTML = events
        .map((event) => {
          const unresolved = Boolean(event.active);
          return `
            <article class="alarm-log-row ${
              unresolved ? "unresolved" : "resolved"
            }">
              <div class="alarm-log-status">
                <span class="alarm-log-dot"></span>
                <b>${unresolved ? "未解决" : "已解决"}</b>
              </div>
              <div class="alarm-log-main">
                <strong>${escapeHtml(event.label)}</strong>
                <p>${escapeHtml(event.message)}</p>
              </div>
              <div class="alarm-log-time">
                <span>发生：${escapeHtml(
                  String(event.time || "").replace("T", " "),
                )}</span>
                <span>${
                  event.cleared_at
                    ? `恢复：${escapeHtml(
                        String(event.cleared_at).replace("T", " "),
                      )}`
                    : "恢复：--"
                }</span>
              </div>
            </article>
          `;
        })
        .join("");
    } catch (error) {
      summary.textContent = "异常日志读取失败";
      list.innerHTML = `
        <div class="alarm-log-empty error">
          ${escapeHtml(error.message)}
        </div>
      `;
    }
  }

  function publish(state) {
    latestState = state;
    updateConnection(state);
    handleNewAlarmEvents(state);

    for (const callback of subscribers) {
      try {
        callback(state);
      } catch (error) {
        console.error("页面状态更新失败", error);
      }
    }
  }

  function subscribe(callback) {
    subscribers.add(callback);
    if (latestState) callback(latestState);
    return () => subscribers.delete(callback);
  }

  async function loadInitialState() {
    try {
      publish(await apiRequest("/api/state"));
    } catch (error) {
      showToast(`初始数据加载失败：${error.message}`, true);
    }
  }

  function connectWebSocket() {
    clearTimeout(reconnectTimer);
    clearInterval(pingTimer);

    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${protocol}//${location.host}/ws`);

    socket.addEventListener("open", () => {
      pingTimer = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send("ping");
        }
      }, 15000);
    });

    socket.addEventListener("message", (event) => {
      try {
        publish(JSON.parse(event.data));
      } catch (error) {
        console.error("WebSocket 数据解析失败", error);
      }
    });

    socket.addEventListener("close", () => {
      clearInterval(pingTimer);
      reconnectTimer = setTimeout(connectWebSocket, 1800);
    });

    socket.addEventListener("error", () => socket.close());
  }

  function startClock() {
    const clock = document.getElementById("footerClock");
    if (!clock) return;

    const update = () => {
      clock.textContent = new Date().toLocaleString("zh-CN");
    };

    update();
    setInterval(update, 1000);
  }

  function init() {
    ensureAlarmUi();
    startClock();
    loadInitialState();
    connectWebSocket();
  }

  return {
    apiRequest,
    escapeHtml,
    formatClock,
    formatDateTime,
    getState: () => latestState,
    openAlarmLog,
    showToast,
    subscribe,
    init,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  window.HMI.init();
});
