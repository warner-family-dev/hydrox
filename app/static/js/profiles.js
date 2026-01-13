const profileData = window.PROFILE_DATA || { fans: [], sensors: [] };

const sensorSelect = document.querySelector('[data-profile-sensor]');
const fanCheckboxes = Array.from(document.querySelectorAll('.profile-builder__fan input'));
const addButton = document.querySelector('[data-profile-add]');
const rulesContainer = document.querySelector('[data-profile-rules]');
const jsonField = document.querySelector('[data-profile-json]');
const settingsInputs = Array.from(document.querySelectorAll('[data-profile-setting]'));
const fallbackSelects = Array.from(document.querySelectorAll('[data-fallback-source]'));
const profileForm = document.querySelector('[data-profile-form]');
const profileIdField = document.querySelector('[data-profile-id]');
const profileNameField = document.querySelector('[data-profile-name]');
const profileSubmit = document.querySelector('[data-profile-submit]');
const editButtons = Array.from(document.querySelectorAll('[data-profile-edit]'));
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

const previewBounds = {
  left: 40,
  right: 500,
  top: 20,
  bottom: 280,
};

const previewViewBox = {
  width: 520,
  height: 320,
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

const scaleToChart = (temp, fan, bounds) => {
  const x = bounds.left + ((bounds.right - bounds.left) * temp) / 100;
  const y = bounds.bottom - ((bounds.bottom - bounds.top) * fan) / 100;
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

const renderMiniChart = (rule) => {
  const sorted = sortPoints(rule.points || []);
  if (!sorted.length) {
    return '';
  }
  const gridLines = [];
  for (let i = 0; i <= 4; i += 1) {
    const x = previewBounds.left + ((previewBounds.right - previewBounds.left) / 4) * i;
    const y = previewBounds.top + ((previewBounds.bottom - previewBounds.top) / 4) * i;
    gridLines.push(`<line x1="${x}" y1="${previewBounds.top}" x2="${x}" y2="${previewBounds.bottom}" />`);
    gridLines.push(`<line x1="${previewBounds.left}" y1="${y}" x2="${previewBounds.right}" y2="${y}" />`);
  }
  const polyline = sorted
    .map((point) => {
      const coords = scaleToChart(point.temp, point.fan, previewBounds);
      return `${coords.x.toFixed(1)},${coords.y.toFixed(1)}`;
    })
    .join(' ');
  const points = sorted
    .map((point) => {
      const coords = scaleToChart(point.temp, point.fan, previewBounds);
      return `<circle cx="${coords.x}" cy="${coords.y}" r="4" />`;
    })
    .join('');

  return `
    <div class="profile-rule__chart">
      <svg viewBox="0 0 ${previewViewBox.width} ${previewViewBox.height}" class="profile-rule__svg" aria-hidden="true">
        <g class="profile-rule__grid">${gridLines.join('')}</g>
        <g class="profile-rule__axes">
          <line x1="${previewBounds.left}" y1="${previewBounds.top}" x2="${previewBounds.left}" y2="${previewBounds.bottom}" />
          <line x1="${previewBounds.left}" y1="${previewBounds.bottom}" x2="${previewBounds.right}" y2="${previewBounds.bottom}" />
        </g>
        <polyline class="profile-rule__line" fill="none" stroke="var(--accent)" stroke-width="2" points="${polyline}" />
        <g class="profile-rule__points">${points}</g>
      </svg>
    </div>
  `;
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
      const miniChart = renderMiniChart(rule);
      return `
        <button type="button" class="profile-rule ${activeClass}" data-rule-index="${index}">
          <div class="profile-rule__title">${sensorLabel(rule.sensor_id)}</div>
          <div class="profile-rule__meta">${fanLabel}</div>
          <div class="profile-rule__meta">${rule.points.length} points</div>
          ${miniChart}
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
    const coords = scaleToChart(point.temp, point.fan, chartBounds);
    return `${coords.x.toFixed(1)},${coords.y.toFixed(1)}`;
  });
  chartLine.setAttribute('points', polylinePoints.join(' '));
  chartPoints.innerHTML = sorted
    .map((point) => {
      const coords = scaleToChart(point.temp, point.fan, chartBounds);
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

const resetEditMode = () => {
  if (profileForm) {
    profileForm.setAttribute('action', '/profiles');
  }
  if (profileIdField) {
    profileIdField.value = '';
  }
  if (profileSubmit) {
    profileSubmit.textContent = 'Save Profile';
  }
};

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

const normalizeCurvePayload = (payload) => {
  if (!payload || typeof payload !== 'object') {
    return { rules: [], settings: {} };
  }
  if (Array.isArray(payload.rules)) {
    return {
      rules: payload.rules,
      settings: payload.settings || {},
    };
  }
  const rules = [];
  Object.keys(payload).forEach((key) => {
    if (!key.startsWith('fan_')) {
      return;
    }
    const channel = Number(key.split('_', 2)[1]);
    if (Number.isNaN(channel)) {
      return;
    }
    rules.push({
      sensor_id: 'cpu',
      fan_channels: [channel],
      points: payload[key],
    });
  });
  return { rules, settings: {} };
};

const populateSettings = (settings) => {
  settingsInputs.forEach((input) => {
    if (!input.name) {
      return;
    }
    const value = settings?.[input.name];
    if (value === null || value === undefined || Number.isNaN(value)) {
      input.value = '';
      return;
    }
    input.value = value;
  });
  fallbackSelects.forEach((select) => {
    const source = select.getAttribute('data-fallback-source');
    if (!source) {
      return;
    }
    select.value = settings?.fallback_map?.[source] ?? '';
  });
};

const loadProfileIntoForm = (profileId, name, curveJson) => {
  if (!profileForm || !profileNameField || !profileIdField) {
    return;
  }
  let parsed = null;
  try {
    const decoded = JSON.parse(curveJson);
    parsed = typeof decoded === 'string' ? JSON.parse(decoded) : decoded;
  } catch (err) {
    parsed = null;
  }
  const normalized = normalizeCurvePayload(parsed);
  rules.length = 0;
  normalized.rules.forEach((rule) => {
    rules.push(rule);
  });
  populateSettings(normalized.settings || {});
  profileForm.setAttribute('action', '/profiles/update');
  profileIdField.value = profileId;
  profileNameField.value = name;
  if (profileSubmit) {
    profileSubmit.textContent = 'Save Changes';
  }
  fanCheckboxes.forEach((input) => {
    input.checked = false;
  });
  setActiveRule(null);
  updateJson();
};

const getSvgCoords = (event) => {
  if (!chartSvg) {
    return null;
  }
  const rect = chartSvg.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
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
    const mapped = scaleToChart(point.temp, point.fan, chartBounds);
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

editButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const profileId = button.getAttribute('data-profile-id');
    const profileName = button.getAttribute('data-profile-name') || '';
    const curveJson = button.getAttribute('data-profile-curve') || '';
    if (!profileId || !curveJson) {
      return;
    }
    loadProfileIntoForm(profileId, profileName, curveJson);
  });
});

settingsInputs.forEach((input) => {
  input.addEventListener('input', updateJson);
});

fallbackSelects.forEach((select) => {
  select.addEventListener('change', updateJson);
});

renderRules();
updateJson();
resetEditMode();
