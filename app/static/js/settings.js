const calibrateForm = document.getElementById('calibrate-form');
const calibrateModal = document.getElementById('calibrate-modal');
const timerEl = document.querySelector('.modal__timer');
const noteEl = document.querySelector('.modal__note');

if (calibrateForm && calibrateModal && timerEl) {
  calibrateForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    calibrateModal.classList.add('modal--open');
    calibrateModal.setAttribute('aria-hidden', 'false');
    timerEl.textContent = '00:15';
    if (noteEl) {
      noteEl.textContent = 'Calibration is running. This window will close when the timer ends.';
    }
    try {
      await fetch(calibrateForm.action, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'fetch',
          Accept: 'application/json',
        },
      });
    } catch (error) {
      // Ignore submission errors; status poll will reflect state.
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch('/api/calibration/status', { cache: 'no-store' });
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        if (!data.running) {
          clearInterval(interval);
          calibrateModal.classList.remove('modal--open');
          calibrateModal.setAttribute('aria-hidden', 'true');
          return;
        }
        const remaining = Math.max(0, data.remaining_seconds || 0);
        const seconds = String(remaining).padStart(2, '0');
        timerEl.textContent = `00:${seconds}`;
        if (noteEl) {
          noteEl.textContent =
            data.phase === 'restoring'
              ? 'Restoring fan speeds to the active profile.'
              : 'Calibration is running. This window will close when fans are restored.';
        }
      } catch (error) {
        // Ignore polling errors.
      }
    }, 1000);
  });
}
