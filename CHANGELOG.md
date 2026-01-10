### Changelog

## v0.0.3 - January 9, 2026

- Add linked RPM/percent readouts in the fan control modal with live calculations.
- Add hover cursor/affordance for dashboard fan tiles.
- Add dashboard fan tile modal for manual PWM/RPM overrides with calibration-aware validation.
- Add OLED chain playlists with drag-and-drop ordering and per-screen rotation timing.
- Publish OLED chains as playlists and turn panels off when a chain is empty.
- Add OLED publish flow with luma.oled and PCA9548A channel selection.
- Add font dropdown with bundled DejaVu and Liberation fonts for OLED rendering.
- Add Publish button to send a saved screen to OLED 1-3.
- Mount `/dev/i2c-1` for OLED access.
- Render font names in the dropdown using their own typefaces.
- Add OLED templates with live tokens, pixel shifting, inline edits, and per-OLED off controls.
- Replace the font dropdown with a custom list that previews typefaces.

## v0.0.2 - January 9, 2026

- Add Wi-Fi signal gauge to the admin status table and remove duplicate disk row.
- Log Wi-Fi signal read failures to `hydrox.log`.
- Auto-refresh admin status metrics every 5 seconds.
- Add Wi-Fi interface fallback and log missing interface once per boot.
- Move hardware sampling into an internal daemon thread.
- Switch Wi-Fi signal collection to `iw` and drop host `/proc` binding.
- Fix missing threading import that prevented app startup.
- Append container logs after compose up to the build log wrapper.
- Auto-detect Wi-Fi interface when `wlan0` is missing.
- Revert Wi-Fi detection to host `/proc/net/wireless` bind-mount.
- Add sysfs Wi-Fi fallback via `/sys/class/net`.
- Add wpa_cli signal polling via `/run/wpa_supplicant`.
- Add admin note that Wi-Fi strength detection needs follow-up.
- Add sensor management with DS18B20 discovery, Liquid Temp 1/2 mapping, and unit conversion.
- Parse liquidctl sensor temperature lines for Liquid Temp 1/2.
- Reorder dashboard layout and plot sensor temperatures in the trend chart.
- Rewrite README to focus on usage, setup, and requirements.

## v0.0.1 - January 8, 2026

- Initial commit
- Add settings page for renaming fan channels.
- Add temperature sparklines to the dashboard.
- Expand profile JSON guidance to per-fan curves and cron+window schedules.
- Add configurable fan count controls and chart line toggles.
- Validate per-fan curve JSON and cron/window schedules on save.
- Remove legacy compose file version key for Docker Compose v2.
- Switch `/data` to a named volume to avoid host permission issues.
- Add logging strategy docs and initial build log entry.
- Handle missing git binary gracefully on the Admin page.
- Install git in the container so Admin can read branch and commit metadata.
- Add `.dockerignore` to exclude logs, env files, and local artifacts.
- Add `.gitignore` for logs, env files, and local artifacts.
- Sample CPU temp via `vcgencmd` in a background thread.
- Add local datetime to build logs.
- Install `libraspberrypi-bin` in the container to enable `vcgencmd`.
- Add build log entry for the missing `libraspberrypi-bin` package error.
- Add Raspberry Pi apt repo to install `libraspberrypi-bin` during builds.
- Mount VideoCore devices into the container for `vcgencmd`.
- Add build log entry for missing `/dev/vchiq`.
- Auto-refresh dashboard metrics every 2 seconds.
- Replace multiple sparklines with a single multi-line chart and axis grid.
- Plot CPU and ambient temperature only with auto-scaled grid labels.
- Add fan output chart with toggles and calibrated max RPM support.
- Add fan calibration workflow and active profile apply setting.
- Mount host `liquidctl` and CPU fan sysfs paths into the container.
- Log hardware and permission errors to `/logs/hydrox.log`.
- Map app logs to `./logs` and remove the extra `./log` folder.
- Add build log wrapper script and set TZ to America/Chicago.
- Install build tooling during image build for `smbus` (liquidctl).
- Keep build tooling installed to allow `smbus` to compile during `pip install`.
- Log unhandled exceptions to `/logs/hydrox.log` with local timestamps.
- Consolidate build logs into `docker-compose-buildlog.log`.
- Run the container with configured `PUID` and `PGID`.
- Mount the correct host `liquidctl` binary path.
- Mount `/sys/class/hwmon` and update CPU fan RPM fallback path.
- Log system startup entries to `hydrox.log`.
- Mount the pipx `liquidctl` venv for host CLI access.
- Add startup banner with boot time and branch in `hydrox.log`.
- Mount the pipx venv at its original path for `liquidctl` shebangs.
- Add liquidctl path fallback to the container binary.
- Install liquidctl in a builder stage and remove host mounts.
- Run the container as root and relax permissions on the embedded liquidctl.
- Remove `user:` override so root can execute embedded liquidctl.
- Pass `/dev/bus/usb` into the container for liquidctl device access.
- Fix duplicate `devices` entry in docker-compose.
- Run container in privileged mode for USB access.
- Treat CPU fan RPM 0 as valid and reduce missing-path log spam.
- Fix git command ordering so branch metadata resolves.
- Add calibration countdown modal and dashboard fan RPM updates.
- Format admin commit date using local CPT timestamp.
- Center chart axis labels and keep calibration modal open until restore.
- Extend calibration countdown and make it dynamic until restore completes.
- Add chart legends and hover tooltips.
- Add admin status table with uptime, memory usage, and liquidctl connection.
- Expand admin status table with CPU load, disk usage, RAM percent, and image uptime.
- Add CI spot-check workflow for PRs into main.
- Add CI safeguards to block direct pushes to main and prevent dev-docs merges.
