const adminField = (name) => document.querySelector(`[data-admin-field="${name}"]`);

const updateText = (name, value) => {
  const el = adminField(name);
  if (el) {
    el.textContent = value;
  }
};

const renderWifi = (wifi) => {
  const container = adminField("wifi");
  if (!container) {
    return;
  }
  if (!wifi || wifi.percent === null || wifi.percent === undefined) {
    container.innerHTML = "<span>unknown</span>";
    return;
  }
  const percent = Math.max(0, Math.min(100, wifi.percent));
  const signal = wifi.signal_dbm !== null && wifi.signal_dbm !== undefined ? `${wifi.signal_dbm} dBm · ` : "";
  container.innerHTML = `
    <div class="wifi-meter">
      <div class="wifi-meter__bar">
        <div class="wifi-meter__fill" style="width: ${percent}%;"></div>
      </div>
      <div class="wifi-meter__label">${signal}${percent}% (${wifi.label})</div>
    </div>
  `;
};

const refreshStatus = async () => {
  try {
    const response = await fetch("/api/admin/status");
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    updateText("status", data.status ?? "unknown");
    updateText("host_uptime", data.host_uptime ?? "unknown");
    updateText("image_uptime", data.image_uptime ?? "unknown");
    updateText("cpu", data.cpu ?? "unknown");
    updateText("memory", data.memory ?? "unknown");
    updateText("disk_data", data.disk_data ?? "unknown");
    updateText("liquidctl", data.liquidctl ?? "unknown");
    updateText("wifi_interface", data.wifi?.interface ?? "wlan0");
    renderWifi(data.wifi);
  } catch (err) {
    // Silent: avoid spam on transient API failures.
  }
};

refreshStatus();
setInterval(refreshStatus, 5000);
