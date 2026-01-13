const profileData = window.PROFILE_DATA || { fans: [], sensors: [] };

const sensorSelect = document.querySelector('[data-profile-sensor]');
const fanCheckboxes = Array.from(document.querySelectorAll('.profile-builder__fan input'));
const addButton = document.querySelector('[data-profile-add]');
const rulesContainer = document.querySelector('[data-profile-rules]');
const jsonField = document.querySelector('[data-profile-json]');
const settingsInputs = Array.from(document.querySelectorAll('[data-profile-setting]'));
const fallbackSelects = Array.from(document.querySelectorAll('[data-fallback-source]'));
const chart = document.querySelector('[data-profile-chart]');
const chartLine = document.querySelector('[data-profile-line]');
const chartPoints = document.querySelector('[data-profile-points]');
const chartGrid = document.querySelector('[data-profile-grid]');

const chartBounds = {
  left: 40,
  right: 500,
  top: 20,
  bottom: 280,
};

const rules = [];
let activeRuleIndex = null;

const sensorLabel = (sensorId) => {
  if (sensorId === 'cpu') {
    return 'CPU Temp';
  }
  const found = profileData.sensors.find((sensor) => String(sensor.id) === String(sensorId));
  return found ? found.name : `Sensor ${sensorId}`;
};

const renderGrid = () => {
  if (!chartGrid) {
    return;
  }
  const lines = [];
  for (let i = 0; i <= 10; i += 1) {
    const x = chartBounds.left + ((chartBounds.right - chartBounds.left) / 10) * i;
    const y = chartBounds.top + ((chartBounds.bottom - chartBounds.top) / 10) * i;
    lines.push(`<line x1="${x}" y1="${chartBounds.top}" x2="${x}" y2="${chartBounds.bottom}" />`);
    lines.push(`<line x1="${chartBounds.left}" y1="${y}" x2="${chartBounds.right}" y2="${y}" />`);
  }
  chartGrid.innerHTML = lines.join('');
};

const scaleToChart = (temp, fan) => {
  const x = chartBounds.left + ((chartBounds.right - chartBounds.left) * temp) / 100;
  const y = chartBounds.bottom - ((chartBounds.bottom - chartBounds.top) * fan) / 100;
  return { x, y };
};

const scaleFromChart = (x, y) => {
  const temp = ((x - chartBounds.left) / (chartBounds.right - chartBounds.left)) * 100;
  const fan = ((chartBounds.bottom - y) / (chartBounds.bottom - chartBounds.top)) * 100;
  return {
    temp: Math.max(0, Math.min(100, Number.parseFloat(temp.toFixed(1)))),
    fan: Math.max(0, Math.min(100, Number.parseFloat(fan.toFixed(1)))),
  };
};

const renderRules = () => {
  if (!rulesContainer) {
    return;
  }
  if (!rules.length) {
    rulesContainer.innerHTML = '<div class="empty">No curves yet. Add the first rule above.</div>';
    return;
  }
  rulesContainer.innerHTML = rules
    .map((rule, index) => {
      const fanLabel = rule.fan_channels.map((fan) => `Fan ${fan}`).join(', ');
      const activeClass = index === activeRuleIndex ? 'profile-rule--active' : '';
      return `
        <button type="button" class="profile-rule ${activeClass}" data-rule-index="${index}">
          <div class="profile-rule__title">${sensorLabel(rule.sensor_id)}</div>
          <div class="profile-rule__meta">${fanLabel}</div>
          <div class="profile-rule__meta">${rule.points.length} points</div>
        </button>
      `;
    })
    .join('');
};

const renderChart = () => {
  if (!chartLine || !chartPoints) {
    return;
  }
  const rule = rules[activeRuleIndex] || null;
  if (!rule) {
    chartLine.setAttribute('points', '');
    chartPoints.innerHTML = '';
    return;
  }
  const sorted = [...rule.points].sort((a, b) => a.temp - b.temp);
  const polylinePoints = sorted.map((point) => {
    const coords = scaleToChart(point.temp, point.fan);
    return `${coords.x.toFixed(1)},${coords.y.toFixed(1)}`;
  });
  chartLine.setAttribute('points', polylinePoints.join(' '));
  chartPoints.innerHTML = sorted
    .map((point) => {
      const coords = scaleToChart(point.temp, point.fan);
      return `<circle cx="${coords.x}" cy="${coords.y}" r="5" data-temp="${point.temp}" data-fan="${point.fan}" />`;
    })
    .join('');
};

const collectSettings = () => {
  const settings = {};
  settingsInputs.forEach((input) => {
    if (input.name) {
      settings[input.name] = input.value === '' ? null : Number(input.value);
    }
  });
  const fallback_map = {};
  fallbackSelects.forEach((select) => {
    const source = select.getAttribute('data-fallback-source');
    if (!source) {
      return;
    }
    if (select.value) {
      fallback_map[source] = select.value;
    }
  });
  settings.fallback_map = fallback_map;
  return settings;
};

const updateJson = () => {
  if (!jsonField) {
    return;
  }
  const payload = {
    rules,
    settings: collectSettings(),
  };
  jsonField.value = JSON.stringify(payload, null, 2);
};

const setActiveRule = (index) => {
  activeRuleIndex = index;
  renderRules();
  renderChart();
};

const addRule = () => {
  if (!sensorSelect) {
    return;
  }
  const selectedFans = fanCheckboxes.filter((input) => input.checked).map((input) => Number(input.value));
  if (!selectedFans.length) {
    return;
  }
  const rule = {
    sensor_id: sensorSelect.value,
    fan_channels: selectedFans,
    points: [
      { temp: 20, fan: 30 },
      { temp: 60, fan: 70 },
    ],
  };
  rules.push(rule);
  fanCheckboxes.forEach((input) => {
    input.checked = false;
  });
  setActiveRule(rules.length - 1);
  updateJson();
};

const handleChartClick = (event) => {
  if (activeRuleIndex === null) {
    return;
  }
  const rect = chart.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  if (
    x < chartBounds.left ||
    x > chartBounds.right ||
    y < chartBounds.top ||
    y > chartBounds.bottom
  ) {
    return;
  }
  const coords = scaleFromChart(x, y);
  rules[activeRuleIndex].points.push({ temp: coords.temp, fan: coords.fan });
  rules[activeRuleIndex].points.sort((a, b) => a.temp - b.temp);
  renderChart();
  updateJson();
};

const handleChartRightClick = (event) => {
  event.preventDefault();
  if (activeRuleIndex === null) {
    return;
  }
  const rect = chart.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const rule = rules[activeRuleIndex];
  let closestIndex = -1;
  let closestDist = Infinity;
  rule.points.forEach((point, index) => {
    const coords = scaleToChart(point.temp, point.fan);
    const dist = Math.hypot(coords.x - x, coords.y - y);
    if (dist < closestDist) {
      closestDist = dist;
      closestIndex = index;
    }
  });
  if (closestIndex !== -1 && closestDist <= 12) {
    rule.points.splice(closestIndex, 1);
    renderChart();
    updateJson();
  }
};

if (addButton) {
  addButton.addEventListener('click', addRule);
}

if (rulesContainer) {
  rulesContainer.addEventListener('click', (event) => {
    const button = event.target.closest('[data-rule-index]');
    if (!button) {
      return;
    }
    const index = Number(button.getAttribute('data-rule-index'));
    if (!Number.isNaN(index)) {
      setActiveRule(index);
    }
  });
}

if (chart) {
  chart.addEventListener('click', handleChartClick);
  chart.addEventListener('contextmenu', handleChartRightClick);
}

settingsInputs.forEach((input) => {
  input.addEventListener('input', updateJson);
});

fallbackSelects.forEach((select) => {
  select.addEventListener('change', updateJson);
});

renderGrid();
renderRules();
renderChart();
updateJson();
