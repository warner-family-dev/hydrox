const toggles = document.querySelectorAll('.toggle input');
const metricEls = document.querySelectorAll('[data-metric]');
const tempPalette = ['#38bdf8', '#22c55e', '#f97316', '#a855f7', '#eab308', '#f472b6', '#14b8a6'];
const grid = document.getElementById('trend-grid');
const labels = document.getElementById('trend-labels');
const fanGrid = document.getElementById('fan-grid');
const fanLabels = document.getElementById('fan-labels');
const tempLegend = document.querySelector('[data-legend="temperature"]');
const fanLegend = document.querySelector('[data-legend="fan"]');
const tempTooltip = document.querySelector('[data-tooltip="temperature"]');
const fanTooltip = document.querySelector('[data-tooltip="fan"]');
const tempChart = document.querySelector('[data-chart="temperature"]');
const fanChart = document.querySelector('[data-chart="fan"]');

const fanPalette = ['#38bdf8', '#818cf8', '#f472b6', '#22c55e', '#eab308', '#f97316', '#a855f7'];
const fanTiles = document.querySelectorAll('[data-fan-channel]');
const sensorTiles = document.querySelectorAll('[data-sensor-id]');
let latestTempSeries = [];
let latestFanSeries = {};
let latestTempLabels = [];

const metricFormatters = {
  cpu_temp: (value) => `${value}°C`,
  ambient_temp: (value) => `${value}°C`,
  fan_rpm: (value) => `${value}`,
  pump_percent: (value) => `${value}%`,
};

const setMetricValue = (el, value) => {
  const key = el.getAttribute('data-metric');
  if (!key) {
    return;
  }
  const formatter = metricFormatters[key];
  const formatted = formatter ? formatter(value) : value;
  el.textContent = formatted;
};

const buildPoints = (series, min, max) => {
  const left = 40;
  const top = 20;
  const width = 460;
  const height = 190;
  const span = Math.max(max - min, 0.1);
  const points = [];
  series.forEach((value, index) => {
    const x = left + (index / (series.length - 1)) * width;
    const normalized = (value - min) / span;
    const y = top + height - normalized * height;
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  });
  return points.join(' ');
};

const refreshMetrics = async () => {
  try {
    const response = await fetch('/api/metrics/latest', { cache: 'no-store' });
    if (response.ok) {
      const data = await response.json();
      metricEls.forEach((el) => {
        const key = el.getAttribute('data-metric');
        const value = data[key];
        if (value === undefined || value === null) {
          return;
        }
        setMetricValue(el, value);
      });
    }
  } catch (error) {
    // Ignore transient fetch failures.
  }
};

const refreshTrend = async () => {
  try {
    const response = await fetch('/api/temperature/recent?limit=24', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    const series = payload.series || {};
    const sensorMeta = payload.sensors || [];
    const sensorNameMap = new Map(sensorMeta.map((sensor) => [String(sensor.id), sensor.name]));
    const cpu = series.cpu || [];
    const ambient = series.ambient || [];
    const tempSeries = [];
    if (cpu.length > 1) {
      tempSeries.push({ key: 'cpu', label: 'CPU', values: cpu, color: 'var(--accent)' });
    }
    if (ambient.length > 1) {
      tempSeries.push({ key: 'ambient', label: 'Ambient', values: ambient, color: 'var(--alert)' });
    }
    sensorMeta.forEach((sensor, index) => {
      const key = `sensor_${sensor.id}`;
      const values = series[key] || [];
      if (values.length < 2) {
        return;
      }
      const label = sensorNameMap.get(String(sensor.id)) || `Sensor ${sensor.id}`;
      const color = tempPalette[index % tempPalette.length];
      tempSeries.push({ key, label, values, color });
    });
    if (!tempSeries.length) {
      return;
    }
    const allTemps = tempSeries.flatMap((item) => item.values);
    const min = Math.min(...allTemps);
    const max = Math.max(...allTemps);
    const padding = Math.max((max - min) * 0.1, 0.5);
    const rangeMin = min - padding;
    const rangeMax = max + padding;
    drawGrid(rangeMin, rangeMax);
    const lines = Array.from(document.querySelectorAll('[data-temp-line]'));
    lines.forEach((line) => {
      const key = line.getAttribute('data-temp-line');
      if (!key) {
        return;
      }
      const match = tempSeries.find((item) => item.key === key);
      if (!match) {
        line.setAttribute('points', '');
        return;
      }
      line.setAttribute('points', buildPoints(match.values, rangeMin, rangeMax));
      if (match.color) {
        line.setAttribute('stroke', match.color);
      }
    });
    applyTempPalette(tempSeries);
    updateTempLegend(tempSeries);
    latestTempSeries = tempSeries;
    latestTempLabels = payload.labels || [];
  } catch (error) {
    // Ignore transient fetch failures.
  }
};

const drawGrid = (min, max) => {
  if (!grid || !labels) {
    return;
  }
  const lines = [];
  const labelEls = [];
  const ySteps = 5;
  const xSteps = 6;
  for (let i = 0; i <= ySteps; i += 1) {
    const y = 20 + (190 / ySteps) * i;
    lines.push(`<line x1="40" y1="${y}" x2="500" y2="${y}" />`);
    const value = max - ((max - min) / ySteps) * i;
    labelEls.push(
      `<text x="30" y="${y + 4}" text-anchor="end">${value.toFixed(1)}</text>`
    );
  }
  for (let i = 0; i <= xSteps; i += 1) {
    const x = 40 + (460 / xSteps) * i;
    lines.push(`<line x1="${x}" y1="20" x2="${x}" y2="210" />`);
  }
  grid.innerHTML = lines.join('');
  labels.innerHTML = labelEls.join('');
};

const drawFanGrid = () => {
  if (!fanGrid || !fanLabels) {
    return;
  }
  const lines = [];
  const labelEls = [];
  const ySteps = 5;
  const xSteps = 6;
  for (let i = 0; i <= ySteps; i += 1) {
    const y = 20 + (190 / ySteps) * i;
    lines.push(`<line x1="40" y1="${y}" x2="500" y2="${y}" />`);
    const value = 100 - (100 / ySteps) * i;
    labelEls.push(`<text x="30" y="${y + 4}" text-anchor="end">${value.toFixed(0)}</text>`);
  }
  for (let i = 0; i <= xSteps; i += 1) {
    const x = 40 + (460 / xSteps) * i;
    lines.push(`<line x1="${x}" y1="20" x2="${x}" y2="210" />`);
  }
  fanGrid.innerHTML = lines.join('');
  fanLabels.innerHTML = labelEls.join('');
};

const refreshFanChart = async () => {
  try {
    const response = await fetch('/api/fans/percent?limit=24', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const series = data.series || {};
    latestFanSeries = series;
    const fanLines = Array.from(document.querySelectorAll('[id^="fan-"][id$="-line"]'));
    fanLines.forEach((line) => {
      const id = line.getAttribute('id');
      const key = id ? id.replace('-', '_').replace('-line', '') : '';
      const values = series[key];
      if (!values || values.length < 2) {
        line.setAttribute('points', '');
        return;
      }
      line.setAttribute('points', buildPoints(values, 0, 100));
    });

    const cpuLine = document.getElementById('cpu-fan-line');
    if (cpuLine) {
      const cpuSeries = series.cpu_fan;
      if (cpuSeries && cpuSeries.length > 1) {
        cpuLine.setAttribute('points', buildPoints(cpuSeries, 0, 100));
      }
    }
    const pumpLine = document.getElementById('pump-line');
    if (pumpLine) {
      const pumpSeries = series.pump;
      if (pumpSeries && pumpSeries.length > 1) {
        pumpLine.setAttribute('points', buildPoints(pumpSeries, 0, 100));
      }
    }
  } catch (error) {
    // Ignore transient fetch failures.
  }
};

const refreshFanTiles = async () => {
  if (!fanTiles.length) {
    return;
  }
  try {
    const response = await fetch('/api/fans/latest', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const readings = data.fans || [];
    const rpmMap = new Map(readings.map((row) => [String(row.channel_index), row.rpm]));
    fanTiles.forEach((tile) => {
      const channel = tile.getAttribute('data-fan-channel');
      const valueEl = tile.querySelector('.fan-tile__value');
      const subEl = tile.querySelector('.fan-tile__sub');
      if (!channel || !valueEl || !subEl) {
        return;
      }
      const rpm = rpmMap.get(channel);
      if (rpm === undefined) {
        valueEl.textContent = '-- RPM';
        subEl.textContent = 'Awaiting live feed';
        return;
      }
      valueEl.textContent = `${rpm} RPM`;
      subEl.textContent = 'Live fan RPM';
    });
  } catch (error) {
    // Ignore transient fetch failures.
  }
};

const refreshSensors = async () => {
  if (!sensorTiles.length) {
    return;
  }
  try {
    const response = await fetch('/api/sensors/latest', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const readings = data.sensors || [];
    const valueMap = new Map(readings.map((row) => [String(row.id), row.value]));
    sensorTiles.forEach((tile) => {
      const sensorId = tile.getAttribute('data-sensor-id');
      const valueEl = tile.querySelector('.fan-tile__value');
      if (!sensorId || !valueEl) {
        return;
      }
      const value = valueMap.get(sensorId);
      valueEl.textContent = value ?? '--';
    });
  } catch (error) {
    // Ignore transient fetch failures.
  }
};

toggles.forEach((toggle) => {
  toggle.addEventListener('change', (event) => {
    const targetId = event.target.getAttribute('data-target');
    if (!targetId) {
      return;
    }
    const line = document.getElementById(targetId);
    if (line) {
      line.style.display = event.target.checked ? 'block' : 'none';
    }
  });
});

const applyFanPalette = () => {
  const fanLines = Array.from(document.querySelectorAll('[id^="fan-"][id$="-line"]'));
  fanLines.forEach((line, index) => {
    line.setAttribute('stroke', fanPalette[index % fanPalette.length]);
    const label = document.querySelector(`label[data-series="fan_${index + 1}"]`);
    if (label) {
      label.style.setProperty('--toggle-color', fanPalette[index % fanPalette.length]);
    }
  });
  const cpuToggle = document.querySelector('label[data-series="cpu_fan"]');
  if (cpuToggle) {
    cpuToggle.style.setProperty('--toggle-color', '#22c55e');
  }
  const pumpToggle = document.querySelector('label[data-series="pump"]');
  if (pumpToggle) {
    pumpToggle.style.setProperty('--toggle-color', '#f97316');
  }
  const cpuTempToggle = document.querySelector('label input[data-target="cpu-line"]')?.parentElement;
  if (cpuTempToggle) {
    cpuTempToggle.style.setProperty('--toggle-color', 'var(--accent)');
  }
  const ambientToggle = document.querySelector('label input[data-target="ambient-line"]')?.parentElement;
  if (ambientToggle) {
    ambientToggle.style.setProperty('--toggle-color', 'var(--alert)');
  }
};

const applyTempPalette = (series) => {
  const cpuToggle = document.querySelector('label input[data-target="cpu-line"]')?.parentElement;
  if (cpuToggle) {
    cpuToggle.style.setProperty('--toggle-color', 'var(--accent)');
  }
  const ambientToggle = document.querySelector('label input[data-target="ambient-line"]')?.parentElement;
  if (ambientToggle) {
    ambientToggle.style.setProperty('--toggle-color', 'var(--alert)');
  }
  const sensorColors = new Map(
    series
      .filter((item) => item.key.startsWith('sensor_'))
      .map((item) => [item.key, item.color])
  );
  const sensorLabels = Array.from(document.querySelectorAll('label[data-series^="sensor_"]'));
  sensorLabels.forEach((label) => {
    const key = label.getAttribute('data-series');
    const color = key ? sensorColors.get(key) : null;
    if (color) {
      label.style.setProperty('--toggle-color', color);
    }
  });
  const tempLines = Array.from(document.querySelectorAll('[data-temp-line^="sensor_"]'));
  tempLines.forEach((line) => {
    const key = line.getAttribute('data-temp-line');
    const color = key ? sensorColors.get(key) : null;
    if (color) {
      line.setAttribute('stroke', color);
    }
  });
};

const buildLegend = (container, items) => {
  if (!container) {
    return;
  }
  container.innerHTML = items
    .map(
      (item) =>
        `<div class="legend__item"><span class="legend__swatch" style="--legend-color:${item.color}"></span>${item.label}</div>`
    )
    .join('');
};

const updateTempLegend = (series) => {
  buildLegend(
    tempLegend,
    series.map((item) => ({ label: item.label, color: item.color }))
  );
};

const updateLegends = () => {
  if (latestTempSeries.length) {
    updateTempLegend(latestTempSeries);
  }

  if (!fanLegend) {
    return;
  }
  const fanItems = [];
  const fanLines = Array.from(document.querySelectorAll('label[data-series^="fan_"]'));
  fanLines.forEach((label, index) => {
    const input = label.querySelector('input');
    if (!input || input.disabled) {
      return;
    }
    const color = fanPalette[index % fanPalette.length];
    fanItems.push({ label: label.textContent.trim(), color });
  });
  fanItems.push({ label: 'CPU Fan', color: '#22c55e' });
  fanItems.push({ label: 'Pump', color: '#f97316' });
  buildLegend(fanLegend, fanItems);
};

const attachTooltip = (chart, tooltipEl, getSeries, unit) => {
  if (!chart || !tooltipEl) {
    return;
  }
  chart.addEventListener('mousemove', (event) => {
    const rect = chart.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const clamped = Math.min(Math.max(x - 40, 0), 460);
    const seriesPayload = getSeries();
    const length = seriesPayload.length;
    if (!length) {
      return;
    }
    const index = Math.round((clamped / 460) * (length - 1));
    const lines = seriesPayload
      .map((item) => {
        if (item.values[index] === undefined) {
          return null;
        }
        const value = unit === '%' ? item.values[index].toFixed(1) : item.values[index].toFixed(1);
        return `${item.label}: ${value}${unit}`;
      })
      .filter(Boolean);
    if (!lines.length) {
      return;
    }
    tooltipEl.innerHTML = lines.join('<br />');
    tooltipEl.classList.add('trend__tooltip--visible');
  });
  chart.addEventListener('mouseleave', () => {
    tooltipEl.classList.remove('trend__tooltip--visible');
  });
};

applyFanPalette();
applyTempPalette([]);
drawFanGrid();
updateLegends();
refreshMetrics();
refreshTrend();
refreshFanChart();
refreshFanTiles();
refreshSensors();
attachTooltip(
  tempChart,
  tempTooltip,
  () => latestTempSeries,
  '°C'
);
attachTooltip(
  fanChart,
  fanTooltip,
  () => {
    const items = [];
    const fanLabels = document.querySelectorAll('label[data-series^="fan_"]');
    fanLabels.forEach((label) => {
      const input = label.querySelector('input');
      const seriesKey = label.getAttribute('data-series');
      if (!input || input.disabled || !input.checked || !seriesKey) {
        return;
      }
      const values = latestFanSeries[seriesKey];
      if (!values) {
        return;
      }
      items.push({ label: label.textContent.trim(), values });
    });
    if (latestFanSeries.cpu_fan) {
      items.push({ label: 'CPU Fan', values: latestFanSeries.cpu_fan });
    }
    if (latestFanSeries.pump) {
      items.push({ label: 'Pump', values: latestFanSeries.pump });
    }
    return items;
  },
  '%'
);
setInterval(() => {
  refreshMetrics();
  refreshTrend();
  refreshFanChart();
  refreshFanTiles();
  refreshSensors();
  updateLegends();
}, 2000);
