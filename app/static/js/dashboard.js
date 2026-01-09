const toggles = document.querySelectorAll('.toggle input');
const metricEls = document.querySelectorAll('[data-metric]');
const lineIds = ['cpu-line', 'ambient-line', 'fan-line', 'pump-line'];
const grid = document.getElementById('trend-grid');

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

const drawGrid = () => {
  if (!grid) {
    return;
  }
  const lines = [];
  for (let i = 0; i <= 4; i += 1) {
    const y = 20 + (190 / 4) * i;
    lines.push(`<line x1="40" y1="${y}" x2="500" y2="${y}" />`);
  }
  for (let i = 0; i <= 5; i += 1) {
    const x = 40 + (460 / 5) * i;
    lines.push(`<line x1="${x}" y1="20" x2="${x}" y2="210" />`);
  }
  grid.innerHTML = lines.join('');
};

const normalizeSeries = (series) => {
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = Math.max(max - min, 0.01);
  return series.map((value) => ((value - min) / span) * 100);
};

const buildPoints = (series) => {
  const left = 40;
  const top = 20;
  const width = 460;
  const height = 190;
  const points = [];
  series.forEach((value, index) => {
    const x = left + (index / (series.length - 1)) * width;
    const y = top + height - (value / 100) * height;
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
    const cpu = normalizeSeries(data.map((row) => row.cpu_temp));
    const ambient = normalizeSeries(data.map((row) => row.ambient_temp));
    const fan = normalizeSeries(data.map((row) => row.fan_rpm));
    const pump = normalizeSeries(data.map((row) => row.pump_percent));
    const seriesMap = {
      'cpu-line': cpu,
      'ambient-line': ambient,
      'fan-line': fan,
      'pump-line': pump,
    };
    lineIds.forEach((id) => {
      const line = document.getElementById(id);
      if (!line) {
        return;
      }
      line.setAttribute('points', buildPoints(seriesMap[id]));
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

drawGrid();
refreshMetrics();
refreshTrend();
setInterval(() => {
  refreshMetrics();
  refreshTrend();
}, 2000);
