const BENCHMARK = { symbol: "SPY", name: "S&P 500 ETF" };
const SVG_NS = "http://www.w3.org/2000/svg";
const DATA_URLS = ["./data/rrg.json", "./public/data/rrg.json"];
const TIMEFRAMES = {
  daily: {
    label: "Daily",
    unit: "d",
    history: 1250
  },
  weekly: {
    label: "Weekly",
    unit: "w",
    history: 260
  },
  monthly: {
    label: "Monthly",
    unit: "m",
    history: 120
  }
};
const RRG_PERIODS = [10, 14, 20, 50, 100, 150, 200];
const DEFAULT_LENGTH_PERIOD = 14;
const DEFAULT_SMOOTH_PERIOD = 20;
const CHART_CENTER = 100;
const SCALE_LIMITS = { min: 1, max: 50, step: 1, initial: 10 };
const DOUBLE_TAP_ZOOM_DELAY = 320;

const UNIVERSES = {
  sectors: [
    ["XLC", "Communication Services", "#7c83fd", "GICS Sector"],
    ["XLY", "Consumer Discretionary", "#f38b5b", "GICS Sector"],
    ["XLP", "Consumer Staples", "#62c370", "GICS Sector"],
    ["XLE", "Energy", "#d6ae3d", "GICS Sector"],
    ["XLF", "Financials", "#4fb6d8", "GICS Sector"],
    ["XLV", "Health Care", "#e05f6f", "GICS Sector"],
    ["XLI", "Industrials", "#8fb35c", "GICS Sector"],
    ["XLB", "Materials", "#b38bdb", "GICS Sector"],
    ["XLRE", "Real Estate", "#d984ac", "GICS Sector"],
    ["XLK", "Information Technology", "#55a7ff", "GICS Sector"],
    ["XLU", "Utilities", "#58d5d1", "GICS Sector"]
  ].map(toAsset),
  industries: [
    ["XBI", "Biotechnology", "#e05f6f", "Health Care"],
    ["IBB", "Biotech Majors", "#b38bdb", "Health Care"],
    ["SOXX", "Semiconductors", "#55a7ff", "Information Technology"],
    ["XSD", "Semiconductors Equal Weight", "#3c7dd9", "Information Technology"],
    ["IGV", "Software", "#7c83fd", "Information Technology"],
    ["XSW", "Software & Services", "#6b68d8", "Information Technology"],
    ["XTL", "Telecom", "#37b9ba", "Communication Services"],
    ["KRE", "Regional Banks", "#4fb6d8", "Financials"],
    ["KBE", "Banks", "#58d5d1", "Financials"],
    ["KCE", "Capital Markets", "#4e9a78", "Financials"],
    ["KIE", "Insurance", "#62c370", "Financials"],
    ["PBJ", "Food & Beverage", "#6cbf5a", "Consumer Staples"],
    ["XRT", "Retail", "#f38b5b", "Consumer Discretionary"],
    ["XHB", "Homebuilders", "#d6ae3d", "Consumer Discretionary"],
    ["ITB", "Residential Construction", "#8fb35c", "Consumer Discretionary"],
    ["XME", "Metals & Mining", "#a67852", "Materials"],
    ["XOP", "Oil & Gas Exploration", "#d9843d", "Energy"],
    ["XES", "Oil Equipment & Services", "#b76d2c", "Energy"],
    ["IYT", "Transportation", "#d984ac", "Industrials"],
    ["XTN", "Transportation Equal Weight", "#c96ea2", "Industrials"],
    ["ITA", "Aerospace & Defense", "#9aa7ba", "Industrials"],
    ["IYR", "Real Estate", "#36c07e", "Real Estate"],
    ["IDU", "Utilities", "#58d5d1", "Utilities"],
    ["XPH", "Pharmaceuticals", "#b64e75", "Health Care"],
    ["IHF", "Health Care Providers", "#c76792", "Health Care"],
    ["IHI", "Medical Devices", "#82b1ff", "Health Care"],
    ["XHE", "Health Care Equipment", "#5d99d6", "Health Care"],
    ["XHS", "Health Care Services", "#8c74d6", "Health Care"],
    ["XAR", "Aerospace & Defense Equal Weight", "#ad8f42", "Industrials"]
  ].map(toAsset)
};

const state = {
  universeKey: "sectors",
  timeframe: "daily",
  histories: new Map(),
  model: null,
  selectedSymbol: "XLK",
  hoverSymbol: null,
  dataMeta: null,
  buildInfo: null,
  dateIndex: 0,
  visualDateIndex: 0,
  lengthPeriod: DEFAULT_LENGTH_PERIOD,
  smoothPeriod: DEFAULT_SMOOTH_PERIOD,
  tailLength: 18,
  chartExtent: SCALE_LIMITS.initial,
  chartCenterX: CHART_CENTER,
  chartCenterY: CHART_CENTER,
  hiddenSymbols: new Set(),
  renderPoints: [],
  activePointers: new Map(),
  dragStart: null,
  pinchZoom: null,
  chartPan: null,
  playbackTimer: null,
  timelineAnimation: null
};

let lastTouchEndAt = 0;

const els = {
  chart: document.querySelector("#rrgChart"),
  status: document.querySelector("#dataStatus"),
  dateSlider: document.querySelector("#dateSlider"),
  lengthPeriod: document.querySelector("#lengthPeriod"),
  smoothPeriod: document.querySelector("#smoothPeriod"),
  tailLength: document.querySelector("#tailLength"),
  tailLengthValue: document.querySelector("#tailLengthValue"),
  selectedDate: document.querySelector("#selectedDate"),
  lastUpdated: document.querySelector("#lastUpdated"),
  selectedQuadrant: document.querySelector("#selectedQuadrant"),
  selectedCard: document.querySelector("#selectedCard"),
  rankList: document.querySelector("#rankList"),
  benchmarkBar: document.querySelector("#benchmarkBar"),
  spySparkline: document.querySelector("#spySparkline"),
  startDate: document.querySelector("#startDate"),
  currentDate: document.querySelector("#currentDate"),
  endDate: document.querySelector("#endDate"),
  tooltip: document.querySelector("#tooltip"),
  refreshButton: document.querySelector("#refreshButton"),
  zoomInButton: document.querySelector("#zoomInButton"),
  zoomOutButton: document.querySelector("#zoomOutButton"),
  zoomValue: document.querySelector("#zoomValue"),
  stepBackButton: document.querySelector("#stepBackButton"),
  playPauseButton: document.querySelector("#playPauseButton"),
  stepForwardButton: document.querySelector("#stepForwardButton")
};

document.querySelectorAll("[data-universe]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-universe]").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    state.universeKey = button.dataset.universe;
    state.selectedSymbol = UNIVERSES[state.universeKey][0].symbol;
    state.hiddenSymbols.clear();
    stopPlayback();
    loadUniverse(false);
  });
});

document.querySelectorAll("[data-timeframe]").forEach((button) => {
  button.addEventListener("click", () => {
    if (state.timeframe === button.dataset.timeframe) return;
    document.querySelectorAll("[data-timeframe]").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    state.timeframe = button.dataset.timeframe;
    stopPlayback();
    rebuildCurrentModel();
  });
});

els.refreshButton.addEventListener("click", () => {
  stopPlayback();
  loadUniverse(true);
});
els.dateSlider.addEventListener("input", () => {
  stopPlayback();
  setDateIndex(Number(els.dateSlider.value));
});
els.tailLength.addEventListener("input", () => {
  state.tailLength = Number(els.tailLength.value);
  updateTailOutput();
  render();
});
els.lengthPeriod.addEventListener("change", () => {
  const period = Number(els.lengthPeriod.value);
  if (!RRG_PERIODS.includes(period) || state.lengthPeriod === period) return;
  state.lengthPeriod = period;
  stopPlayback();
  rebuildCurrentModel();
});
els.smoothPeriod.addEventListener("change", () => {
  const period = Number(els.smoothPeriod.value);
  if (!RRG_PERIODS.includes(period) || state.smoothPeriod === period) return;
  state.smoothPeriod = period;
  stopPlayback();
  rebuildCurrentModel();
});
els.zoomInButton.addEventListener("click", () => {
  setChartExtent(state.chartExtent - SCALE_LIMITS.step);
});
els.zoomOutButton.addEventListener("click", () => {
  setChartExtent(state.chartExtent + SCALE_LIMITS.step);
});

els.stepBackButton.addEventListener("click", () => {
  stopPlayback();
  stepDate(-1);
});
els.stepForwardButton.addEventListener("click", () => {
  stopPlayback();
  stepDate(1);
});
els.playPauseButton.addEventListener("click", () => {
  if (state.playbackTimer) {
    stopPlayback();
  } else {
    startPlayback();
  }
});

els.chart.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  trackChartPointer(event);
  captureChartPointer(event);
  if (state.activePointers.size >= 2) {
    startChartPinch();
    return;
  }

  const nearest = nearestPoint(event);
  state.dragStart = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    symbol: nearest?.symbol
  };
});

els.chart.addEventListener("pointermove", (event) => {
  if (state.activePointers.has(event.pointerId)) {
    trackChartPointer(event);
  }

  if (state.activePointers.size >= 2) {
    event.preventDefault();
    state.chartPan = null;
    updateChartPinch();
    return;
  }

  if (state.chartPan && state.chartPan.pointerId === event.pointerId) {
    event.preventDefault();
    updateChartPan(event);
    return;
  }

  if (state.pinchZoom) {
    return;
  }

  if (state.dragStart && state.dragStart.pointerId === event.pointerId && event.buttons === 1) {
    event.preventDefault();
    startChartPan(event.pointerId, state.activePointers.get(event.pointerId));
    updateChartPan(event);
    return;
  }

  const nearest = nearestPoint(event);
  state.hoverSymbol = nearest?.symbol ?? null;
  showTooltip(event, nearest);
});

els.chart.addEventListener("pointerup", (event) => {
  const wasPinching = Boolean(state.pinchZoom) || state.activePointers.size >= 2;
  const wasPanning = Boolean(state.chartPan);
  removeChartPointer(event);
  if (wasPanning) {
    state.chartPan = null;
    state.dragStart = null;
    hideTooltip();
    return;
  }
  if (wasPinching) {
    state.pinchZoom = null;
    state.dragStart = null;
    hideTooltip();
    return;
  }

  const start = state.dragStart;
  state.dragStart = null;
  if (!start) return;
  const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
  if (moved < 8 && start.symbol) {
    state.selectedSymbol = start.symbol;
    render();
  }
});

els.chart.addEventListener("pointercancel", (event) => {
  removeChartPointer(event);
  state.pinchZoom = null;
  state.chartPan = null;
  state.dragStart = null;
  hideTooltip();
});

els.chart.addEventListener("pointerleave", () => {
  state.hoverSymbol = null;
  if (state.activePointers.size > 0 || state.chartPan) return;
  state.dragStart = null;
  hideTooltip();
});

els.chart.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    setDateIndex(state.dateIndex + Math.sign(event.deltaY || event.deltaX));
  },
  { passive: false }
);

window.addEventListener("resize", render);
document.addEventListener("touchend", preventDoubleTapZoom, { passive: false });
document.addEventListener("gesturestart", preventGestureZoom, { passive: false });

updateLaunchMode();
watchLaunchMode();
loadBuildInfo();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./service-worker.js").catch(() => {});
}

loadUniverse(false);

function toAsset([symbol, name, color, group]) {
  return { symbol, name, color, group };
}

function updateLaunchMode() {
  const standalone = Boolean(
    window.navigator.standalone || window.matchMedia?.("(display-mode: standalone)")?.matches
  );
  const fullscreen = Boolean(window.matchMedia?.("(display-mode: fullscreen)")?.matches);
  const mode = standalone ? "standalone" : fullscreen ? "fullscreen" : "browser";
  document.documentElement.dataset.installTarget = "ipad-pwa";
  document.documentElement.dataset.launchMode = mode;
  document.body.dataset.launchMode = mode;
}

function watchLaunchMode() {
  ["standalone", "fullscreen"].forEach((mode) => {
    const media = window.matchMedia?.(`(display-mode: ${mode})`);
    if (!media) return;
    if (media.addEventListener) {
      media.addEventListener("change", updateLaunchMode);
    } else if (media.addListener) {
      media.addListener(updateLaunchMode);
    }
  });
}

async function loadBuildInfo() {
  const info = await fetch("./build-info.json", { cache: "no-cache" })
    .then((response) => (response.ok ? response.json() : null))
    .catch(() => null);
  if (!info?.buildId) return;

  state.buildInfo = info;
  document.documentElement.dataset.buildId = info.buildId;
  document.documentElement.dataset.buildDataGeneratedAt = info.dataGeneratedAt || "";
}

async function loadUniverse(forceRefresh) {
  const loadStartedAt = performance.now();
  const assets = UNIVERSES[state.universeKey];
  const symbols = [BENCHMARK.symbol, ...assets.map((asset) => asset.symbol)];
  els.status.textContent = forceRefresh ? "Reloading RRG data..." : "Loading RRG data...";

  const bundled = await loadSameOriginHistories(symbols, forceRefresh).catch(() => null);
  const loaded = bundled?.histories ?? buildFallbackHistories(symbols);
  state.dataMeta = bundled?.meta ?? {
    generatedAt: new Date().toISOString().slice(0, 10),
    generatedAtUtc: new Date().toISOString(),
    source: "Local sample data"
  };

  state.histories = loaded;
  state.hiddenSymbols.clear();
  const buildStartedAt = performance.now();
  state.model = buildModel(assets, loaded, state.timeframe);
  document.documentElement.dataset.modelBuildMs = String(Math.round(performance.now() - buildStartedAt));
  state.dateIndex = Math.max(0, state.model.dates.length - 1);
  state.visualDateIndex = state.dateIndex;
  configureSliders();
  updateLastUpdated();
  els.status.textContent = bundled ? "RRG data loaded" : "RRG data unavailable; showing sample data";
  const renderStartedAt = performance.now();
  render();
  document.documentElement.dataset.renderMs = String(Math.round(performance.now() - renderStartedAt));
  document.documentElement.dataset.loadMs = String(Math.round(performance.now() - loadStartedAt));
}

function rebuildCurrentModel() {
  if (!state.histories.size) {
    loadUniverse(false);
    return;
  }

  const assets = UNIVERSES[state.universeKey];
  const buildStartedAt = performance.now();
  state.model = buildModel(assets, state.histories, state.timeframe);
  document.documentElement.dataset.modelBuildMs = String(Math.round(performance.now() - buildStartedAt));
  state.dateIndex = Math.max(0, state.model.dates.length - 1);
  state.visualDateIndex = state.dateIndex;
  configureSliders();
  const renderStartedAt = performance.now();
  render();
  document.documentElement.dataset.renderMs = String(Math.round(performance.now() - renderStartedAt));
}

async function loadSameOriginHistories(symbols, forceRefresh) {
  let response = null;
  for (const url of DATA_URLS) {
    response = await fetch(url, { cache: forceRefresh ? "reload" : "no-cache" }).catch(() => null);
    if (response?.ok) break;
  }
  if (!response?.ok) throw new Error("Generated RRG data unavailable");

  const payload = await response.json();
  const rowsBySymbol = payload.symbols ?? {};
  const histories = new Map();

  symbols.forEach((symbol) => {
    const rows = rowsBySymbol[symbol];
    if (!Array.isArray(rows) || rows.length < 180) {
      if (symbol === BENCHMARK.symbol) {
        throw new Error(`Generated RRG data missing benchmark ${symbol}`);
      }
      return;
    }

    histories.set(
      symbol,
      rows
        .map((row) => ({ date: row.date, close: Number(row.close) }))
        .filter((row) => /^\d{4}-\d{2}-\d{2}$/.test(row.date) && Number.isFinite(row.close) && row.close > 0)
    );
  });

  return {
    histories,
    meta: {
      generatedAt: payload.generatedAt ?? "",
      generatedAtUtc: payload.generatedAtUtc ?? "",
      source: payload.source ?? "generated RRG data",
      priceField: payload.priceField ?? "adjusted close"
    }
  };
}

function buildFallbackHistories(symbols) {
  const dates = recentBusinessDates(720);
  const benchmark = generateSeries("SPY", dates, null);
  const histories = new Map([[BENCHMARK.symbol, benchmark]]);

  symbols
    .filter((symbol) => symbol !== BENCHMARK.symbol)
    .forEach((symbol) => histories.set(symbol, generateSeries(symbol, dates, benchmark)));

  return histories;
}

function recentBusinessDates(count) {
  const dates = [];
  const cursor = new Date();
  cursor.setHours(12, 0, 0, 0);

  while (dates.length < count) {
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) dates.push(cursor.toISOString().slice(0, 10));
    cursor.setDate(cursor.getDate() - 1);
  }

  return dates.reverse();
}

function generateSeries(symbol, dates, benchmark) {
  const seed = hashSymbol(symbol);
  let price = 70 + (seed % 90);
  let phase = (seed % 360) * (Math.PI / 180);
  const drift = 0.00014 + ((seed % 11) - 5) * 0.000015;
  const beta = 0.78 + (seed % 50) / 100;

  return dates.map((date, index) => {
    const cycle = Math.sin(index / (34 + (seed % 28)) + phase) * 0.006;
    const noise = Math.sin(index * (0.67 + (seed % 9) / 30) + phase * 2) * 0.004;

    if (benchmark) {
      const previous = benchmark[Math.max(0, index - 1)].close;
      const current = benchmark[index].close;
      const marketReturn = index ? current / previous - 1 : 0;
      price *= 1 + marketReturn * beta + drift + cycle + noise;
    } else {
      price *= 1 + drift + cycle + noise;
    }

    return { date, close: Number(price.toFixed(4)) };
  });
}

function hashSymbol(symbol) {
  return symbol.split("").reduce((total, char) => total * 31 + char.charCodeAt(0), 17);
}

function buildModel(assets, histories, timeframe) {
  const config = TIMEFRAMES[timeframe] ?? TIMEFRAMES.daily;
  const benchmark = sampleHistory(histories.get(BENCHMARK.symbol), timeframe);
  const dates = benchmark.slice(-config.history).map((row) => row.date);
  const benchmarkAligned = alignToDates(benchmark, dates);
  const series = assets
    .filter((asset) => histories.has(asset.symbol))
    .map((asset) => {
      const closes = alignToDates(sampleHistory(histories.get(asset.symbol), timeframe), dates);
      const points = computeRrgPoints(closes, benchmarkAligned, state.lengthPeriod, state.smoothPeriod);
      return { ...asset, points };
    });

  const firstValidIndex = series.reduce((maxIndex, item) => {
    const index = item.points.findIndex((point) => point);
    return Math.max(maxIndex, index);
  }, 0);

  return {
    dates: dates.slice(firstValidIndex),
    benchmarkCloses: benchmarkAligned.slice(firstValidIndex),
    series: series.map((item) => ({ ...item, points: item.points.slice(firstValidIndex) }))
  };
}

function sampleHistory(history, timeframe) {
  if (timeframe === "daily") return history.slice();

  const periods = new Map();
  history.forEach((row) => {
    const key = timeframe === "weekly" ? getWeekKey(row.date) : row.date.slice(0, 7);
    periods.set(key, row);
  });

  return Array.from(periods.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function getWeekKey(date) {
  const value = new Date(`${date}T12:00:00Z`);
  const day = value.getUTCDay() || 7;
  value.setUTCDate(value.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(value.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((value - yearStart) / 86400000 + 1) / 7);
  return `${value.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function alignToDates(history, dates) {
  const byDate = new Map(history.map((row) => [row.date, row.close]));
  const sorted = history.slice().sort((a, b) => a.date.localeCompare(b.date));
  let pointer = 0;
  let lastClose = sorted[0]?.close ?? 1;

  return dates.map((date) => {
    if (byDate.has(date)) {
      lastClose = byDate.get(date);
      return lastClose;
    }

    while (pointer < sorted.length && sorted[pointer].date <= date) {
      lastClose = sorted[pointer].close;
      pointer += 1;
    }

    return lastClose;
  });
}

function computeRrgPoints(closes, benchmark, lengthPeriod, smoothPeriod) {
  const relativeStrength = [];
  for (let index = 0; index < closes.length; index += 1) {
    const close = closes[index];
    const benchmarkClose = benchmark[index];
    relativeStrength.push(
      Number.isFinite(close) && close > 0 && Number.isFinite(benchmarkClose) && benchmarkClose > 0
        ? close / benchmarkClose
        : null
    );
  }

  const smoothedRelativeStrength = ema(relativeStrength, lengthPeriod);
  const relativeStrengthRatio = [];
  for (let index = 0; index < relativeStrength.length; index += 1) {
    const value = relativeStrength[index];
    const smoothedValue = smoothedRelativeStrength[index];
    relativeStrengthRatio.push(value === null || smoothedValue === null ? null : value / smoothedValue);
  }

  const ratio = ema(relativeStrengthRatio, smoothPeriod).map((value) => (value === null ? null : value * 100));

  const smoothedRatio = ema(ratio, smoothPeriod);

  const points = [];
  for (let index = 0; index < ratio.length; index += 1) {
    const ratioValue = ratio[index];
    const smoothedRatioValue = smoothedRatio[index];
    const momentumValue =
      ratioValue === null || smoothedRatioValue === null ? null : (ratioValue / smoothedRatioValue) * 100;
    if (ratioValue === null || momentumValue === null) {
      points.push(null);
      continue;
    }

    points.push({
      ratio: ratioValue,
      momentum: momentumValue
    });
  }

  return points;
}

function ema(values, period) {
  const multiplier = 2 / (period + 1);
  const output = [];
  let previous = null;

  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === null || !Number.isFinite(value)) {
      output.push(null);
      continue;
    }

    previous = previous === null ? value : value * multiplier + previous * (1 - multiplier);
    output.push(previous);
  }

  return output;
}

function configureSliders() {
  const lastIndex = Math.max(0, state.model.dates.length - 1);
  els.dateSlider.max = String(lastIndex);
  els.dateSlider.value = String(lastIndex);
  els.startDate.textContent = formatDate(state.model.dates[0]);
  els.endDate.textContent = formatDate(state.model.dates[lastIndex]);
  updateTailOutput();
  updateZoomOutput();
}

function render() {
  if (!state.model) return;

  const date = state.model.dates[state.dateIndex];
  const allCurrentPoints = state.model.series
    .map((item) => ({ ...item, point: item.points[state.dateIndex] }))
    .filter((item) => item.point);
  const currentPoints = allCurrentPoints.filter((item) => !state.hiddenSymbols.has(item.symbol));

  if (!currentPoints.some((item) => item.symbol === state.selectedSymbol) && currentPoints[0]) {
    state.selectedSymbol = currentPoints[0].symbol;
  }

  els.dateSlider.value = String(state.dateIndex);
  els.dateSlider.setAttribute("aria-valuetext", formatDate(date));
  els.selectedDate.textContent = formatDate(date);
  els.currentDate.textContent = formatDate(date);
  updateBenchmarkBar(date);
  renderSpySparkline();
  updateTimelineButtons();
  renderChart(currentPoints);
  renderDetails(allCurrentPoints, currentPoints);
}

function updateBenchmarkBar(date) {
  const close = state.model.benchmarkCloses?.[state.dateIndex];
  const config = TIMEFRAMES[state.timeframe] ?? TIMEFRAMES.daily;
  els.benchmarkBar.innerHTML = `
    <span>${BENCHMARK.symbol}</span>
    <strong>${Number.isFinite(close) ? `$${close.toFixed(2)}` : "--"}</strong>
    <small>${config.label} close • ${formatDate(date)}</small>`;
}

function updateLastUpdated() {
  const generatedAt = state.dataMeta?.generatedAt;
  const source = state.dataMeta?.source || "generated data";
  const label = generatedAt ? formatDate(generatedAt) : "--";
  els.lastUpdated.textContent = `Last updated: ${label}`;
  els.lastUpdated.title = source;
  document.documentElement.dataset.dataGeneratedAt = generatedAt || "";
}

function renderChart(currentPoints) {
  const svg = els.chart;
  svg.replaceChildren();
  svg.setAttribute("viewBox", "0 0 1000 680");
  svg.setAttribute("preserveAspectRatio", "xMidYMin meet");

  const plot = { left: 74, top: 40, width: 862, height: 560 };
  svg.dataset.plotWidth = String(plot.width);
  svg.dataset.plotHeight = String(plot.height);
  const extent = state.chartExtent;
  const minX = state.chartCenterX - extent;
  const maxX = state.chartCenterX + extent;
  const minY = state.chartCenterY - extent;
  const maxY = state.chartCenterY + extent;
  svg.dataset.chartCenterX = formatChartNumber(state.chartCenterX);
  svg.dataset.chartCenterY = formatChartNumber(state.chartCenterY);
  document.documentElement.dataset.chartCenterX = svg.dataset.chartCenterX;
  document.documentElement.dataset.chartCenterY = svg.dataset.chartCenterY;
  svg.dataset.chartMin = formatChartNumber(minX);
  svg.dataset.chartMax = formatChartNumber(maxX);
  svg.dataset.chartMinY = formatChartNumber(minY);
  svg.dataset.chartMaxY = formatChartNumber(maxY);
  const mapX = (value) => plot.left + ((value - minX) / (maxX - minX)) * plot.width;
  const mapY = (value) => plot.top + plot.height - ((value - minY) / (maxY - minY)) * plot.height;
  const centerX = mapX(CHART_CENTER);
  const centerY = mapY(CHART_CENTER);
  const splitX = clamp(centerX, plot.left, plot.left + plot.width);
  const splitY = clamp(centerY, plot.top, plot.top + plot.height);

  addRect(svg, plot.left, plot.top, splitX - plot.left, splitY - plot.top, "#e8f1ff");
  addRect(svg, splitX, plot.top, plot.left + plot.width - splitX, splitY - plot.top, "#e8f7ee");
  addRect(svg, plot.left, splitY, splitX - plot.left, plot.top + plot.height - splitY, "#fff0f0");
  addRect(svg, splitX, splitY, plot.left + plot.width - splitX, plot.top + plot.height - splitY, "#fff7da");
  addGrid(svg, plot, minX, maxX, minY, maxY, mapX, mapY);
  addQuadrantLabels(svg, plot);

  state.renderPoints = [];

  currentPoints.forEach((item) => {
    const trail = getVisualTrail(item);
    if (!trail.length) return;

    const end = trail[trail.length - 1];
    const quadrant = getQuadrant(end);
    const color = item.color;
    const trailPoints = trail.map((point) => ({ x: mapX(point.ratio), y: mapY(point.momentum) }));
    const selected = item.symbol === state.selectedSymbol;
    const hovered = item.symbol === state.hoverSymbol;
    const x = mapX(end.ratio);
    const y = mapY(end.momentum);

    addSmoothPath(svg, trailPoints, color, selected ? 5 : 3, selected ? 0.92 : 0.58);
    addTailDots(svg, trail, mapX, mapY, color, selected);
    addCircle(svg, x, y, selected ? 11 : hovered ? 10 : 8, color, item.symbol);
    addText(svg, x + 12, y - 10, item.symbol, selected ? 18 : 15, "#182033", selected ? 800 : 700);

    state.renderPoints.push({ ...item, x, y, point: end, quadrant });
  });

  addText(svg, plot.left + plot.width / 2, 650, "Relative Strength Ratio", 18, "#24324a", 720, "middle");
  const yLabelX = plot.left - 58;
  const yLabel = addText(svg, yLabelX, 322, "Relative Strength Momentum", 18, "#24324a", 720, "middle");
  yLabel.setAttribute("transform", `rotate(-90 ${yLabelX} 322)`);
}

function getVisualTrail(item) {
  const visualIndex = clamp(state.visualDateIndex, 0, state.model.dates.length - 1);
  const endIndex = Math.floor(visualIndex);
  const startIndex = Math.max(0, endIndex - state.tailLength + 1);
  const trail = [];

  for (let index = startIndex; index <= endIndex; index += 1) {
    const point = item.points[index];
    if (point) trail.push(point);
  }

  if (!Number.isInteger(visualIndex) && endIndex + 1 < item.points.length) {
    const point = interpolatePoint(item.points[endIndex], item.points[endIndex + 1], visualIndex - endIndex);
    if (point) {
      if (trail.length && item.points[endIndex]) trail[trail.length - 1] = point;
      else trail.push(point);
    }
  }

  return trail;
}

function interpolatePoint(start, end, progress) {
  if (!start && !end) return null;
  if (!start) return end;
  if (!end) return start;
  return {
    ratio: start.ratio + (end.ratio - start.ratio) * progress,
    momentum: start.momentum + (end.momentum - start.momentum) * progress
  };
}

function addGrid(svg, plot, minX, maxX, minY, maxY, mapX, mapY) {
  const xStep = gridStep(maxX - minX);
  const yStep = gridStep(maxY - minY);

  for (let value = Math.ceil(minX / xStep) * xStep; value <= maxX; value += xStep) {
    const emphasized = value === CHART_CENTER;
    const x = mapX(value);
    addLine(svg, x, plot.top, x, plot.top + plot.height, emphasized ? "#55627a" : "#d5dde8", emphasized ? 2 : 1);

    if (value !== CHART_CENTER) {
      addText(svg, x, plot.top + plot.height + 25, formatGridValue(value), 12, "#6b7486", 500, "middle");
    }
  }

  for (let value = Math.ceil(minY / yStep) * yStep; value <= maxY; value += yStep) {
    const emphasized = value === CHART_CENTER;
    const y = mapY(value);
    addLine(svg, plot.left, y, plot.left + plot.width, y, emphasized ? "#55627a" : "#d5dde8", emphasized ? 2 : 1);

    if (value !== CHART_CENTER) {
      addText(svg, plot.left - 22, y + 4, formatGridValue(value), 12, "#6b7486", 500, "middle");
    }
  }
}

function gridStep(range) {
  if (range <= 20) return 5;
  if (range <= 60) return 10;
  return 10;
}

function formatGridValue(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function addQuadrantLabels(svg, plot) {
  addText(svg, plot.left + plot.width * 0.75, plot.top + 35, "Leading", 22, "#228a5c", 800, "middle");
  addText(svg, plot.left + plot.width * 0.75, plot.top + plot.height - 22, "Weakening", 22, "#9b7417", 800, "middle");
  addText(svg, plot.left + plot.width * 0.25, plot.top + plot.height - 22, "Lagging", 22, "#b93b4d", 800, "middle");
  addText(svg, plot.left + plot.width * 0.25, plot.top + 35, "Improving", 22, "#2f78be", 800, "middle");
}

function addRect(svg, x, y, width, height, fill) {
  const rect = document.createElementNS(SVG_NS, "rect");
  rect.setAttribute("x", x);
  rect.setAttribute("y", y);
  rect.setAttribute("width", width);
  rect.setAttribute("height", height);
  rect.setAttribute("fill", fill);
  svg.append(rect);
  return rect;
}

function addLine(svg, x1, y1, x2, y2, stroke, width) {
  const line = document.createElementNS(SVG_NS, "line");
  line.setAttribute("x1", x1);
  line.setAttribute("y1", y1);
  line.setAttribute("x2", x2);
  line.setAttribute("y2", y2);
  line.setAttribute("stroke", stroke);
  line.setAttribute("stroke-width", width);
  svg.append(line);
  return line;
}

function addSmoothPath(svg, points, stroke, width, opacity) {
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", smoothPath(points));
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", stroke);
  path.setAttribute("stroke-width", width);
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  path.setAttribute("opacity", opacity);
  path.dataset.tailPath = "true";
  svg.append(path);
  return path;
}

function smoothPath(points) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  if (points.length === 2) {
    return `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)} L ${points[1].x.toFixed(1)} ${points[1].y.toFixed(1)}`;
  }

  const commands = [`M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`];
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const nextNext = points[index + 2] ?? next;
    const controlX = current.x + (next.x - (points[index - 1]?.x ?? current.x)) / 6;
    const controlY = current.y + (next.y - (points[index - 1]?.y ?? current.y)) / 6;
    const nextControlX = next.x - (nextNext.x - current.x) / 6;
    const nextControlY = next.y - (nextNext.y - current.y) / 6;
    commands.push(
      `C ${controlX.toFixed(1)} ${controlY.toFixed(1)}, ${nextControlX.toFixed(1)} ${nextControlY.toFixed(
        1
      )}, ${next.x.toFixed(1)} ${next.y.toFixed(1)}`
    );
  }
  return commands.join(" ");
}

function addTailDots(svg, trail, mapX, mapY, fill, selected) {
  const visibleTrail = trail.slice(0, -1);
  const interval = Math.max(1, Math.floor(visibleTrail.length / 9));

  visibleTrail.forEach((point, index) => {
    if (index % interval !== 0 && index !== visibleTrail.length - 1) return;

    const age = visibleTrail.length <= 1 ? 1 : (index + 1) / visibleTrail.length;
    const dot = document.createElementNS(SVG_NS, "circle");
    dot.setAttribute("cx", mapX(point.ratio));
    dot.setAttribute("cy", mapY(point.momentum));
    dot.setAttribute("r", (selected ? 3.9 : 2.8 + age * 1.3).toFixed(1));
    dot.setAttribute("fill", fill);
    dot.setAttribute("opacity", (0.18 + age * (selected ? 0.62 : 0.42)).toFixed(2));
    dot.dataset.tailDot = "true";
    svg.append(dot);
  });
}

function addCircle(svg, x, y, radius, fill, symbol) {
  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("cx", x);
  circle.setAttribute("cy", y);
  circle.setAttribute("r", radius);
  circle.setAttribute("fill", fill);
  circle.setAttribute("stroke", "#ffffff");
  circle.setAttribute("stroke-width", 3);
  circle.dataset.symbol = symbol;
  svg.append(circle);
  return circle;
}

function addText(svg, x, y, text, size, fill, weight, anchor = "start") {
  const node = document.createElementNS(SVG_NS, "text");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  node.setAttribute("font-size", size);
  node.setAttribute("font-weight", weight);
  node.setAttribute("fill", fill);
  node.setAttribute("text-anchor", anchor);
  node.textContent = text;
  svg.append(node);
  return node;
}

function renderDetails(allCurrentPoints, currentPoints) {
  const selected = currentPoints.find((item) => item.symbol === state.selectedSymbol) ?? currentPoints[0];
  const quadrant = selected ? getQuadrant(selected.point) : null;
  els.selectedQuadrant.textContent = quadrant?.label ?? "--";
  els.selectedQuadrant.style.background = quadrant ? quadrant.bg : "";
  els.selectedQuadrant.style.color = quadrant ? quadrant.fg : "";

  if (selected) {
    const history = state.histories.get(selected.symbol);
    const latest = history?.find((row) => row.date === state.model.dates[state.dateIndex]) ?? history?.at(-1);
    els.selectedCard.innerHTML = `
      <strong>${selected.symbol}</strong>
      <div>${selected.name}</div>
      <div class="asset-meta">${assetSubtitle(selected)}</div>
      <div class="metric-grid">
        <div class="metric"><span>RS-Ratio</span><b>${selected.point.ratio.toFixed(1)}</b></div>
        <div class="metric"><span>RS-Momentum</span><b>${selected.point.momentum.toFixed(1)}</b></div>
        <div class="metric"><span>Quadrant</span><b>${quadrant.label}</b></div>
        <div class="metric"><span>Close</span><b>${latest ? `$${latest.close.toFixed(2)}` : "--"}</b></div>
      </div>`;
  } else {
    els.selectedCard.innerHTML = "<p>All symbols are hidden. Show a row below to inspect its rotation.</p>";
  }

  const ranked = allCurrentPoints.slice().sort((a, b) => {
    const scoreA = a.point.ratio + a.point.momentum;
    const scoreB = b.point.ratio + b.point.momentum;
    return scoreB - scoreA;
  });

  els.rankList.replaceChildren(
    ...ranked.map((item) => {
      const row = document.createElement("button");
      const quadrant = getQuadrant(item.point);
      const hidden = state.hiddenSymbols.has(item.symbol);
      row.className = `rank-row ${item.symbol === state.selectedSymbol ? "active" : ""} ${
        hidden ? "hidden-symbol" : ""
      }`;
      row.type = "button";
      row.setAttribute("aria-label", `${item.symbol} ${hidden ? "hidden" : "visible"}, ${quadrant.label}`);
      row.innerHTML = `
        <span class="visibility-toggle" role="button" aria-pressed="${!hidden}" title="${
          hidden ? "Show symbol" : "Hide symbol"
        }">${hidden ? "○" : "●"}</span>
        <b><span class="dot" style="background:${item.color}"></span>${item.symbol}</b>
        <span>${item.name}</span>
        <span>${quadrant.label}</span>`;
      row.querySelector(".visibility-toggle").addEventListener("click", (event) => {
        event.stopPropagation();
        toggleSymbolVisibility(item.symbol);
      });
      row.addEventListener("click", (event) => {
        if (event.target.closest(".visibility-toggle")) return;
        if (hidden) {
          toggleSymbolVisibility(item.symbol);
        }
        state.selectedSymbol = item.symbol;
        render();
      });
      return row;
    })
  );
}

function toggleSymbolVisibility(symbol) {
  if (state.hiddenSymbols.has(symbol)) {
    state.hiddenSymbols.delete(symbol);
    state.selectedSymbol = symbol;
  } else {
    const visibleCount = state.model.series.filter((item) => !state.hiddenSymbols.has(item.symbol)).length;
    if (visibleCount <= 1) return;
    state.hiddenSymbols.add(symbol);
  }

  render();
}

function setChartExtent(extent) {
  state.chartExtent = Number(clamp(extent, SCALE_LIMITS.min, SCALE_LIMITS.max).toFixed(2));
  updateZoomOutput();
  render();
}

function updateZoomOutput() {
  els.zoomValue.value = `+/-${formatExtent(state.chartExtent)}`;
  document.documentElement.dataset.chartExtent = String(state.chartExtent);
  document.documentElement.dataset.chartCenterX = formatChartNumber(state.chartCenterX);
  document.documentElement.dataset.chartCenterY = formatChartNumber(state.chartCenterY);
  els.zoomInButton.disabled = state.chartExtent <= SCALE_LIMITS.min;
  els.zoomOutButton.disabled = state.chartExtent >= SCALE_LIMITS.max;
}

function formatExtent(extent) {
  return Number.isInteger(extent) ? String(extent) : extent.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function formatChartNumber(value) {
  return Number(value.toFixed(2)).toString();
}

function trackChartPointer(event) {
  state.activePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
}

function captureChartPointer(event) {
  try {
    els.chart.setPointerCapture?.(event.pointerId);
  } catch {
    // Synthetic touch events used in audits are not always capture-eligible.
  }
}

function removeChartPointer(event) {
  state.activePointers.delete(event.pointerId);
  try {
    if (els.chart.hasPointerCapture?.(event.pointerId)) {
      els.chart.releasePointerCapture(event.pointerId);
    }
  } catch {
    // Ignore stale synthetic pointers.
  }
}

function startChartPinch() {
  const pair = getChartPointerPair();
  if (!pair) return;
  const midpoint = pointerMidpoint(pair[0], pair[1]);
  state.pinchZoom = {
    startDistance: Math.max(pointerDistance(pair[0], pair[1]), 1),
    startMidX: midpoint.x,
    startMidY: midpoint.y,
    startCenterX: state.chartCenterX,
    startCenterY: state.chartCenterY,
    startExtent: state.chartExtent
  };
  state.dragStart = null;
  state.hoverSymbol = null;
  hideTooltip();
}

function updateChartPinch() {
  const pair = getChartPointerPair();
  if (!pair) return;
  if (!state.pinchZoom) {
    startChartPinch();
    return;
  }

  const distance = Math.max(pointerDistance(pair[0], pair[1]), 1);
  const zoomRatio = distance / state.pinchZoom.startDistance;
  setChartExtent(state.pinchZoom.startExtent / zoomRatio);

  const midpoint = pointerMidpoint(pair[0], pair[1]);
  const rect = els.chart.getBoundingClientRect();
  const deltaX = midpoint.x - state.pinchZoom.startMidX;
  const deltaY = midpoint.y - state.pinchZoom.startMidY;
  const valueRange = state.chartExtent * 2;
  state.chartCenterX = Number((state.pinchZoom.startCenterX - (deltaX / rect.width) * valueRange).toFixed(2));
  state.chartCenterY = Number((state.pinchZoom.startCenterY + (deltaY / rect.height) * valueRange).toFixed(2));
  render();
}

function getChartPointerPair() {
  const pointers = Array.from(state.activePointers.values());
  return pointers.length >= 2 ? [pointers[0], pointers[1]] : null;
}

function pointerDistance(first, second) {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function pointerMidpoint(first, second) {
  return {
    x: (first.x + second.x) / 2,
    y: (first.y + second.y) / 2
  };
}

function startChartPan(pointerId, pointer) {
  if (!pointer) return;
  const startPointer =
    state.dragStart && state.dragStart.pointerId === pointerId
      ? { x: state.dragStart.x, y: state.dragStart.y }
      : pointer;
  state.chartPan = {
    pointerId,
    startX: startPointer.x,
    startY: startPointer.y,
    startCenterX: state.chartCenterX,
    startCenterY: state.chartCenterY,
    startExtent: state.chartExtent
  };
  state.dragStart = null;
  state.hoverSymbol = null;
  hideTooltip();
}

function updateChartPan(event) {
  const rect = els.chart.getBoundingClientRect();
  const deltaX = event.clientX - state.chartPan.startX;
  const deltaY = event.clientY - state.chartPan.startY;
  const valueRange = state.chartPan.startExtent * 2;
  state.chartCenterX = Number((state.chartPan.startCenterX - (deltaX / rect.width) * valueRange).toFixed(2));
  state.chartCenterY = Number((state.chartPan.startCenterY + (deltaY / rect.height) * valueRange).toFixed(2));
  render();
}

function nearestPoint(event) {
  if (!state.renderPoints.length) return null;
  const rect = els.chart.getBoundingClientRect();
  const x = ((event.clientX - rect.left) / rect.width) * 1000;
  const y = ((event.clientY - rect.top) / rect.height) * 680;
  const nearest = state.renderPoints
    .map((point) => ({ ...point, distance: Math.hypot(point.x - x, point.y - y) }))
    .sort((a, b) => a.distance - b.distance)[0];

  return nearest && nearest.distance < 38 ? nearest : null;
}

function showTooltip(event, point) {
  if (!point) {
    hideTooltip();
    return;
  }

  const rect = els.chart.getBoundingClientRect();
  els.tooltip.classList.remove("hidden");
  els.tooltip.style.left = `${Math.min(rect.width - 166, event.clientX - rect.left + 14)}px`;
  els.tooltip.style.top = `${Math.max(10, event.clientY - rect.top - 62)}px`;
  els.tooltip.innerHTML = `<b>${point.symbol}</b> ${point.name}<br>${assetSubtitle(point)}<br>${point.quadrant.label}<br>RS-Ratio ${point.point.ratio.toFixed(
    1
  )} / Momentum ${point.point.momentum.toFixed(1)}`;
}

function hideTooltip() {
  els.tooltip.classList.add("hidden");
}

function setDateIndex(index, options = {}) {
  if (!state.model) return;
  const target = clamp(index, 0, state.model.dates.length - 1);
  state.dateIndex = target;
  els.dateSlider.value = String(target);
  updateTimelineButtons();

  if (options.immediate) {
    cancelTimelineAnimation();
    state.visualDateIndex = target;
    render();
    return;
  }

  animateVisualDate(target);
}

function stepDate(delta) {
  setDateIndex(state.dateIndex + delta);
}

function startPlayback() {
  if (!state.model || state.playbackTimer) return;
  if (state.dateIndex >= state.model.dates.length - 1) {
    setDateIndex(0);
  }

  state.playbackTimer = window.setInterval(() => {
    if (!state.model || state.dateIndex >= state.model.dates.length - 1) {
      stopPlayback();
      return;
    }

    stepDate(1);
  }, 520);
  updateTimelineButtons();
}

function stopPlayback() {
  if (!state.playbackTimer) return;
  window.clearInterval(state.playbackTimer);
  state.playbackTimer = null;
  updateTimelineButtons();
}

function animateVisualDate(target) {
  cancelTimelineAnimation();
  const start = Number.isFinite(state.visualDateIndex) ? state.visualDateIndex : state.dateIndex;
  const distance = Math.abs(target - start);
  const duration = clamp(160 + distance * 22, 180, 520);
  const startedAt = performance.now();

  const tick = (now) => {
    const progress = clamp((now - startedAt) / duration, 0, 1);
    const eased = 1 - (1 - progress) ** 3;
    state.visualDateIndex = start + (target - start) * eased;
    render();

    if (progress < 1) {
      state.timelineAnimation = requestAnimationFrame(tick);
    } else {
      state.timelineAnimation = null;
      state.visualDateIndex = target;
      render();
    }
  };

  state.timelineAnimation = requestAnimationFrame(tick);
}

function cancelTimelineAnimation() {
  if (!state.timelineAnimation) return;
  cancelAnimationFrame(state.timelineAnimation);
  state.timelineAnimation = null;
}

function renderSpySparkline() {
  const svg = els.spySparkline;
  const closes = state.model.benchmarkCloses;
  if (!svg || !Array.isArray(closes) || closes.length < 2) return;

  svg.replaceChildren();
  svg.setAttribute("viewBox", "0 0 320 48");
  svg.setAttribute("preserveAspectRatio", "none");

  const end = state.dateIndex;
  const start = Math.max(0, end - 90);
  const values = closes.slice(start, end + 1);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 0.01);
  const points = values.map((value, index) => ({
    x: values.length === 1 ? 0 : (index / (values.length - 1)) * 320,
    y: 42 - ((value - min) / spread) * 36
  }));
  const path = addSmoothPath(svg, points, "#58d5d1", 3, 0.95);
  path.dataset.spySparkline = "true";
}

function updateTailOutput() {
  const config = TIMEFRAMES[state.timeframe] ?? TIMEFRAMES.daily;
  els.tailLengthValue.value = `${state.tailLength}${config.unit}`;
}

function updateTimelineButtons() {
  if (!state.model) return;
  const atStart = state.dateIndex <= 0;
  const atEnd = state.dateIndex >= state.model.dates.length - 1;
  els.stepBackButton.disabled = atStart;
  els.stepForwardButton.disabled = atEnd;
  els.playPauseButton.innerHTML = state.playbackTimer ? "&#10073;&#10073;" : "&#9654;";
  els.playPauseButton.setAttribute("aria-label", state.playbackTimer ? "Pause timeline" : "Play timeline");
  els.playPauseButton.title = state.playbackTimer ? "Pause timeline" : "Play timeline";
}

function assetSubtitle(asset) {
  if (!asset?.group) return "";
  return state.universeKey === "sectors" ? asset.group : `${asset.group} industry proxy`;
}

function getQuadrant(point) {
  if (point.ratio >= CHART_CENTER && point.momentum >= CHART_CENTER) {
    return { label: "Leading", bg: "#e8f7ee", fg: "#17633f" };
  }
  if (point.ratio >= CHART_CENTER && point.momentum < CHART_CENTER) {
    return { label: "Weakening", bg: "#fff7da", fg: "#795811" };
  }
  if (point.ratio < CHART_CENTER && point.momentum >= CHART_CENTER) {
    return { label: "Improving", bg: "#e8f1ff", fg: "#1f5e9a" };
  }
  return { label: "Lagging", bg: "#fff0f0", fg: "#92303d" };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function formatDate(date) {
  if (!date) return "--";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(
    new Date(`${date}T12:00:00`)
  );
}

function readStorage(key) {
  try {
    return JSON.parse(localStorage.getItem(key));
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

function preventDoubleTapZoom(event) {
  const now = Date.now();
  if (now - lastTouchEndAt <= DOUBLE_TAP_ZOOM_DELAY) {
    event.preventDefault();
  }
  lastTouchEndAt = now;
}

function preventGestureZoom(event) {
  event.preventDefault();
}
