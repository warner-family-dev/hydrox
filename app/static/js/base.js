const statusDot = document.querySelector('[data-status-dot]');

const updateStatusDot = async () => {
  if (!statusDot) {
    return;
  }
  try {
    const response = await fetch('/api/admin/status', { cache: 'no-store' });
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const ok = data.status === 'Ok';
    const warning = data.status === 'Warning';
    const liquidctlOk = data.liquidctl === 'Connected';
    const wifiOk = data.wifi?.percent !== null && data.wifi?.percent !== undefined;
    const fullyOk = ok && liquidctlOk && wifiOk;
    statusDot.classList.toggle('brand__dot--ok', fullyOk);
    statusDot.classList.toggle('brand__dot--warn', warning && !fullyOk);
  } catch (error) {
    // Ignore transient failures.
  }
};

updateStatusDot();
setInterval(updateStatusDot, 10000);
