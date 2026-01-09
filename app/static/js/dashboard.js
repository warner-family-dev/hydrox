const toggles = document.querySelectorAll('.toggle input');
const metricEls = document.querySelectorAll('[data-metric]');
const lineIds = ['cpu-line', 'ambient-line'];
const grid = document.getElementById('trend-grid');
const labels = document.getElementById('trend-labels');
const fanGrid = document.getElementById('fan-grid');
const fanLabels = document.getElementById('fan-labels');

const fanPalette = ['#38bdf8', '#818cf8', '#f472b6', '#22c55e', '#eab308', '#f97316', '#a855f7'];
const fanTiles = document.querySelectorAll('[data-fan-channel]');

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
    const response = await fetch('/api/metrics/recent?limit=24', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    if (!Array.isArray(data) || data.length < 2) {
      return;
    }
    const cpu = data.map((row) => row.cpu_temp);
    const ambient = data.map((row) => row.ambient_temp);
    const allTemps = cpu.concat(ambient);
    const min = Math.min(...allTemps);
    const max = Math.max(...allTemps);
    const padding = Math.max((max - min) * 0.1, 0.5);
    const rangeMin = min - padding;
    const rangeMax = max + padding;
    const seriesMap = {
      'cpu-line': cpu,
      'ambient-line': ambient,
    };
    drawGrid(rangeMin, rangeMax);
    lineIds.forEach((id) => {
      const line = document.getElementById(id);
      if (!line) {
        return;
      }
      line.setAttribute('points', buildPoints(seriesMap[id], rangeMin, rangeMax));
    });
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
  });
};

applyFanPalette();
drawFanGrid();
refreshMetrics();
refreshTrend();
refreshFanChart();
refreshFanTiles();
setInterval(() => {
  refreshMetrics();
  refreshTrend();
  refreshFanChart();
  refreshFanTiles();
}, 2000);
