const calibrateForm = document.getElementById('calibrate-form');
const calibrateModal = document.getElementById('calibrate-modal');
const timerEl = document.querySelector('.modal__timer');

if (calibrateForm && calibrateModal && timerEl) {
  calibrateForm.addEventListener('submit', () => {
    let remaining = 15;
    calibrateModal.classList.add('modal--open');
    calibrateModal.setAttribute('aria-hidden', 'false');
    timerEl.textContent = '00:15';
    const interval = setInterval(() => {
      remaining -= 1;
      const seconds = String(Math.max(remaining, 0)).padStart(2, '0');
      timerEl.textContent = `00:${seconds}`;
      if (remaining <= 0) {
        clearInterval(interval);
        calibrateModal.classList.remove('modal--open');
        calibrateModal.setAttribute('aria-hidden', 'true');
      }
    }, 1000);
  });
}
