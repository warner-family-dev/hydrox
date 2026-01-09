### Changelog

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
