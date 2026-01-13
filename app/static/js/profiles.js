const profileData = window.PROFILE_DATA || { fans: [], sensors: [] };

const sensorSelect = document.querySelector('[data-profile-sensor]');
const fanCheckboxes = Array.from(document.querySelectorAll('.profile-builder__fan input'));
const addButton = document.querySelector('[data-profile-add]');
const rulesContainer = document.querySelector('[data-profile-rules]');
const jsonField = document.querySelector('[data-profile-json]');
const settingsInputs = Array.from(document.querySelectorAll('[data-profile-setting]'));
const fallbackSelects = Array.from(document.querySelectorAll('[data-fallback-source]'));
const modal = document.querySelector('[data-profile-modal]');
const modalCloseButtons = Array.from(document.querySelectorAll('[data-profile-close]'));
const modalCancel = document.querySelector('[data-profile-cancel]');
const modalSave = document.querySelector('[data-profile-save]');
const chart = modal ? modal.querySelector('[data-profile-chart]') : null;
const chartSvg = modal ? modal.querySelector('.profile-chart__svg') : null;
const chartLine = modal ? modal.querySelector('[data-profile-line]') : null;
const chartPoints = modal ? modal.querySelector('[data-profile-points]') : null;
const chartGrid = modal ? modal.querySelector('[data-profile-grid]') : null;

const chartBounds = {
  left: 60,
  right: 860,
  top: 30,
  bottom: 470,
};

const chartViewBox = {
  width: 900,
  height: 520,
};

const rules = [];
let activeRuleIndex = null;
let editRuleIndex = null;
let draftPoints = [];
let draftMeta = null;

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

const sortPoints = (points) => [...points].sort((a, b) => a.temp - b.temp);

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
  if (!draftPoints.length) {
    chartLine.setAttribute('points', '');
    chartPoints.innerHTML = '';
    return;
  }
  const sorted = sortPoints(draftPoints);
  const polylinePoints = sorted.map((point) => {
    const coords = scaleToChart(point.temp, point.fan);
    return `${coords.x.toFixed(1)},${coords.y.toFixed(1)}`;
  });
  chartLine.setAttribute('points', polylinePoints.join(' '));
  chartPoints.innerHTML = sorted
    .map((point) => {
      const coords = scaleToChart(point.temp, point.fan);
      return `<circle cx="${coords.x}" cy="${coords.y}" r="6" data-temp="${point.temp}" data-fan="${point.fan}" />`;
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
};

const getSelectedFans = () => fanCheckboxes.filter((input) => input.checked).map((input) => Number(input.value));

const defaultPoints = () => [
  { temp: 20, fan: 30 },
  { temp: 60, fan: 70 },
];

const openModal = (meta, points, index = null) => {
  if (!modal) {
    return;
  }
  editRuleIndex = index;
  draftMeta = meta;
  draftPoints = points.map((point) => ({ temp: point.temp, fan: point.fan }));
  setActiveRule(index);
  renderGrid();
  renderChart();
  modal.classList.add('profile-modal--open');
};

const closeModal = () => {
  if (!modal) {
    return;
  }
  modal.classList.remove('profile-modal--open');
  editRuleIndex = null;
  draftMeta = null;
  draftPoints = [];
  setActiveRule(null);
  renderChart();
};

const addRule = () => {
  if (!sensorSelect) {
    return;
  }
  const selectedFans = getSelectedFans();
  if (!selectedFans.length) {
    window.alert('Select at least one fan channel before adding a curve.');
    return;
  }
  const meta = {
    sensor_id: sensorSelect.value,
    fan_channels: selectedFans,
  };
  openModal(meta, defaultPoints());
};

const saveRule = () => {
  if (!draftMeta) {
    return;
  }
  const points = sortPoints(draftPoints).map((point) => ({
    temp: Number(point.temp.toFixed(1)),
    fan: Number(point.fan.toFixed(1)),
  }));
  const rule = {
    sensor_id: draftMeta.sensor_id,
    fan_channels: draftMeta.fan_channels,
    points,
  };
  if (editRuleIndex === null || editRuleIndex === undefined) {
    rules.push(rule);
    fanCheckboxes.forEach((input) => {
      input.checked = false;
    });
  } else {
    rules[editRuleIndex] = rule;
  }
  updateJson();
  renderRules();
  closeModal();
};

const getSvgCoords = (event) => {
  if (!chartSvg) {
    return null;
  }
  const rect = chartSvg.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  // Convert screen coordinates into SVG viewBox coordinates.
  const x = ((event.clientX - rect.left) / rect.width) * chartViewBox.width;
  const y = ((event.clientY - rect.top) / rect.height) * chartViewBox.height;
  return { x, y };
};

const handleChartClick = (event) => {
  if (!draftMeta) {
    return;
  }
  const coords = getSvgCoords(event);
  if (!coords) {
    return;
  }
  const { x, y } = coords;
  if (x < chartBounds.left || x > chartBounds.right || y < chartBounds.top || y > chartBounds.bottom) {
    return;
  }
  const scaled = scaleFromChart(x, y);
  draftPoints.push({ temp: scaled.temp, fan: scaled.fan });
  draftPoints = sortPoints(draftPoints);
  renderChart();
};

const handleChartRightClick = (event) => {
  event.preventDefault();
  if (!draftMeta || !draftPoints.length) {
    return;
  }
  const coords = getSvgCoords(event);
  if (!coords) {
    return;
  }
  const { x, y } = coords;
  let closestIndex = -1;
  let closestDist = Infinity;
  draftPoints.forEach((point, index) => {
    const mapped = scaleToChart(point.temp, point.fan);
    const dist = Math.hypot(mapped.x - x, mapped.y - y);
    if (dist < closestDist) {
      closestDist = dist;
      closestIndex = index;
    }
  });
  if (closestIndex !== -1 && closestDist <= 14) {
    draftPoints.splice(closestIndex, 1);
    renderChart();
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
    if (Number.isNaN(index) || !rules[index]) {
      return;
    }
    const rule = rules[index];
    openModal(
      { sensor_id: rule.sensor_id, fan_channels: [...rule.fan_channels] },
      rule.points,
      index,
    );
  });
}

if (chart) {
  chart.addEventListener('click', handleChartClick);
  chart.addEventListener('contextmenu', handleChartRightClick);
}

modalCloseButtons.forEach((button) => {
  button.addEventListener('click', closeModal);
});

if (modalCancel) {
  modalCancel.addEventListener('click', closeModal);
}

if (modalSave) {
  modalSave.addEventListener('click', saveRule);
}

settingsInputs.forEach((input) => {
  input.addEventListener('input', updateJson);
});

fallbackSelects.forEach((select) => {
  select.addEventListener('change', updateJson);
});

renderRules();
updateJson();
