"use strict";

window.HMICharts = (() => {
  const sensorConfig = {
    temperature: {
      label: "温度",
      unit: "℃",
      color: "#e35858",
      decimals: 2,
      minTick: 0.5,
    },
    humidity: {
      label: "湿度",
      unit: "%RH",
      color: "#2685dc",
      decimals: 2,
      minTick: 1,
    },
    co2: {
      label: "CO₂",
      unit: "ppm",
      color: "#27a36c",
      decimals: 1,
      minTick: 50,
    },
    light: {
      label: "光照 / 灯组状态",
      unit: "",
      color: "#e39b20",
      decimals: 0,
      minTick: 0.25,
      boolean: true,
    },
  };

  function hexToRgba(hex, alpha) {
    const value = parseInt(hex.replace("#", ""), 16);
    return `rgba(${(value >> 16) & 255},${(value >> 8) & 255},${
      value & 255
    },${alpha})`;
  }

  function formatValue(sensor, value) {
    const config = sensorConfig[sensor];

    if (
      value === undefined ||
      value === null ||
      Number.isNaN(Number(value))
    ) {
      return "--";
    }

    if (config.boolean) {
      return Number(value) >= 0.5 ? "ON" : "OFF";
    }

    return Number(value).toFixed(config.decimals);
  }

  function niceStep(rawStep, minimumStep) {
    const safeRaw = Math.max(rawStep, minimumStep);
    const exponent = Math.floor(Math.log10(safeRaw));
    const fraction = safeRaw / 10 ** exponent;
    let niceFraction;

    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 2.5) niceFraction = 2.5;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;

    return Math.max(minimumStep, niceFraction * 10 ** exponent);
  }

  function computeYAxis(sensor, values) {
    const config = sensorConfig[sensor];

    if (config.boolean) {
      return {
        min: -0.15,
        max: 1.15,
        tick: 0.25,
      };
    }

    const finite = values
      .map(Number)
      .filter((value) => Number.isFinite(value));
    let dataMin = finite.length ? Math.min(...finite) : 0;
    let dataMax = finite.length ? Math.max(...finite) : 1;
    const minTick = config.minTick;
    const minimumSpan = minTick * 4;
    let span = dataMax - dataMin;

    if (span < minimumSpan) {
      const center = (dataMin + dataMax) / 2;
      dataMin = center - minimumSpan / 2;
      dataMax = center + minimumSpan / 2;
      span = minimumSpan;
    } else {
      const padding = span * 0.10;
      dataMin -= padding;
      dataMax += padding;
      span = dataMax - dataMin;
    }

    const tick = niceStep(span / 4, minTick);
    let min = Math.floor(dataMin / tick) * tick;
    let max = Math.ceil(dataMax / tick) * tick;

    while (max - min < tick * 4) {
      min -= tick / 2;
      max += tick / 2;
    }

    return { min, max, tick };
  }

  function formatAxisValue(sensor, value, tick) {
    if (sensorConfig[sensor].boolean) {
      if (value > 0.75) return "ON";
      if (value < 0.25) return "OFF";
      return "";
    }

    if (tick >= 10) return Math.round(value).toLocaleString("zh-CN");
    if (tick >= 1) return value.toFixed(0);
    if (tick >= 0.1) return value.toFixed(1);
    return value.toFixed(2);
  }

  function formatAxisTime(timestamp, rangeSeconds) {
    const date = new Date(timestamp * 1000);

    if (rangeSeconds >= 86400) {
      return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    if (rangeSeconds >= 3600) {
      return date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    return date.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function prepareCanvas(canvas) {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(10, Math.round(rect.width * dpr));
    const height = Math.max(10, Math.round(rect.height * dpr));

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    return {
      ctx,
      width: rect.width,
      height: rect.height,
    };
  }

  function drawAxes({
    ctx,
    width,
    height,
    sensor,
    yAxis,
    domainStart,
    domainEnd,
    showMiddleTime,
  }) {
    const padding = {
      left: 58,
      right: 16,
      top: 13,
      bottom: 34,
    };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const valueSpan = Math.max(0.0001, yAxis.max - yAxis.min);
    const timeSpan = Math.max(0.001, domainEnd - domainStart);

    ctx.strokeStyle = "#e5ebf2";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#8491a2";
    ctx.font = "11px Segoe UI";

    for (let index = 0; index <= 4; index += 1) {
      const y = padding.top + (plotHeight * index) / 4;
      const value = yAxis.max - (valueSpan * index) / 4;

      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(
        formatAxisValue(sensor, value, yAxis.tick),
        padding.left - 7,
        y,
      );
    }

    const labelTimes = showMiddleTime
      ? [
          domainStart,
          domainStart + timeSpan / 2,
          domainEnd,
        ]
      : [domainStart, domainEnd];
    const alignments = showMiddleTime
      ? ["left", "center", "right"]
      : ["left", "right"];

    ctx.fillStyle = "#8a96a6";
    ctx.textBaseline = "top";

    labelTimes.forEach((timestamp, index) => {
      ctx.textAlign = alignments[index];
      const x = showMiddleTime
        ? index === 0
          ? padding.left
          : index === 1
            ? padding.left + plotWidth / 2
            : width - padding.right
        : index === 0
          ? padding.left
          : width - padding.right;

      ctx.fillText(
        formatAxisTime(timestamp, timeSpan),
        x,
        height - padding.bottom + 10,
      );
    });

    return {
      padding,
      plotWidth,
      plotHeight,
      timeSpan,
      valueSpan,
      xFor: (timestamp) =>
        padding.left +
        ((timestamp - domainStart) / timeSpan) * plotWidth,
      yFor: (value) =>
        padding.top +
        ((yAxis.max - Number(value)) / valueSpan) * plotHeight,
    };
  }

  class LineChart {
    constructor(
      canvas,
      sensor,
      dataProvider,
      domainProvider,
      emptyText = "等待数据",
      options = {},
    ) {
      this.canvas = canvas;
      this.sensor = sensor;
      this.dataProvider = dataProvider;
      this.domainProvider = domainProvider;
      this.emptyText = emptyText;
      this.options = {
        showMiddleTime: true,
        ...options,
      };

      new ResizeObserver(() => this.draw()).observe(canvas.parentElement);
    }

    draw() {
      const { ctx, width, height } = prepareCanvas(this.canvas);
      const config = sensorConfig[this.sensor];
      const points = (this.dataProvider() || [])
        .filter(
          (point) =>
            Number.isFinite(Number(point.timestamp)) &&
            Number.isFinite(Number(point.value)),
        )
        .sort((a, b) => a.timestamp - b.timestamp);

      ctx.clearRect(0, 0, width, height);

      const suppliedDomain = this.domainProvider?.();
      let domainStart = Number(suppliedDomain?.start);
      let domainEnd = Number(suppliedDomain?.end);

      if (!Number.isFinite(domainStart) || !Number.isFinite(domainEnd)) {
        domainStart = points.length
          ? points[0].timestamp
          : Date.now() / 1000 - 60;
        domainEnd = points.length
          ? points.at(-1).timestamp
          : Date.now() / 1000;
      }

      if (domainEnd <= domainStart) {
        domainEnd = domainStart + 1;
      }

      const visiblePoints = points.filter(
        (point) =>
          point.timestamp >= domainStart &&
          point.timestamp <= domainEnd,
      );
      const yAxis = computeYAxis(
        this.sensor,
        visiblePoints.map((point) => point.value),
      );
      const axes = drawAxes({
        ctx,
        width,
        height,
        sensor: this.sensor,
        yAxis,
        domainStart,
        domainEnd,
        showMiddleTime: this.options.showMiddleTime,
      });

      if (visiblePoints.length < 2) {
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#9aa6b5";
        ctx.fillText(this.emptyText, width / 2, height / 2);
        return;
      }

      const gradient = ctx.createLinearGradient(
        0,
        axes.padding.top,
        0,
        height - axes.padding.bottom,
      );
      gradient.addColorStop(0, hexToRgba(config.color, 0.18));
      gradient.addColorStop(1, hexToRgba(config.color, 0.008));

      ctx.beginPath();
      visiblePoints.forEach((point, index) => {
        const x = axes.xFor(point.timestamp);
        const y = axes.yFor(point.value);
        index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.lineTo(
        axes.xFor(visiblePoints.at(-1).timestamp),
        height - axes.padding.bottom,
      );
      ctx.lineTo(
        axes.xFor(visiblePoints[0].timestamp),
        height - axes.padding.bottom,
      );
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      ctx.beginPath();
      visiblePoints.forEach((point, index) => {
        const x = axes.xFor(point.timestamp);
        const y = axes.yFor(point.value);
        index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.strokeStyle = config.color;
      ctx.lineWidth = 1.8;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();

      const lastPoint = visiblePoints.at(-1);
      ctx.beginPath();
      ctx.arc(
        axes.xFor(lastPoint.timestamp),
        axes.yFor(lastPoint.value),
        3,
        0,
        Math.PI * 2,
      );
      ctx.fillStyle = config.color;
      ctx.fill();
    }
  }

  class OverlayLineChart {
    constructor(
      canvas,
      sensorProvider,
      seriesProvider,
      domainProvider,
      emptyText = "尚未设置预设曲线",
    ) {
      this.canvas = canvas;
      this.sensorProvider = sensorProvider;
      this.seriesProvider = seriesProvider;
      this.domainProvider = domainProvider;
      this.emptyText = emptyText;

      new ResizeObserver(() => this.draw()).observe(canvas.parentElement);
    }

    draw() {
      const { ctx, width, height } = prepareCanvas(this.canvas);
      ctx.clearRect(0, 0, width, height);

      const sensor = this.sensorProvider();
      const domain = this.domainProvider?.();
      const domainStart = Number(domain?.start);
      const domainEnd = Number(domain?.end);
      const series = (this.seriesProvider() || []).map((item) => ({
        ...item,
        points: (item.points || [])
          .filter(
            (point) =>
              Number.isFinite(Number(point.timestamp)) &&
              Number.isFinite(Number(point.value)),
          )
          .sort((a, b) => a.timestamp - b.timestamp),
      }));

      if (
        !Number.isFinite(domainStart) ||
        !Number.isFinite(domainEnd) ||
        domainEnd <= domainStart
      ) {
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#9aa6b5";
        ctx.font = "12px Segoe UI";
        ctx.fillText(this.emptyText, width / 2, height / 2);
        return;
      }

      const allValues = series.flatMap((item) =>
        item.points
          .filter(
            (point) =>
              point.timestamp >= domainStart &&
              point.timestamp <= domainEnd,
          )
          .map((point) => point.value),
      );
      const yAxis = computeYAxis(sensor, allValues);
      const axes = drawAxes({
        ctx,
        width,
        height,
        sensor,
        yAxis,
        domainStart,
        domainEnd,
        showMiddleTime: true,
      });

      let visibleSeriesCount = 0;

      series.forEach((item) => {
        const points = item.points.filter(
          (point) =>
            point.timestamp >= domainStart &&
            point.timestamp <= domainEnd,
        );

        if (points.length < 2) return;
        visibleSeriesCount += 1;

        ctx.save();
        ctx.beginPath();
        points.forEach((point, index) => {
          const x = axes.xFor(point.timestamp);
          const y = axes.yFor(point.value);
          index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        });
        ctx.strokeStyle = item.color;
        ctx.lineWidth = item.width || 2;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.setLineDash(item.dash || []);
        ctx.stroke();
        ctx.restore();

        if (item.markLast) {
          const last = points.at(-1);
          ctx.beginPath();
          ctx.arc(
            axes.xFor(last.timestamp),
            axes.yFor(last.value),
            3.2,
            0,
            Math.PI * 2,
          );
          ctx.fillStyle = item.color;
          ctx.fill();
        }
      });

      if (!visibleSeriesCount) {
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#9aa6b5";
        ctx.font = "12px Segoe UI";
        ctx.fillText(this.emptyText, width / 2, height / 2);
      }
    }
  }

  return {
    LineChart,
    OverlayLineChart,
    formatValue,
    sensorConfig,
  };
})();
