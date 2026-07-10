# AI Stock Hunter macOS Automation

This folder contains project-local launchd automation for AI Stock Hunter. It prepares scheduled jobs but does not install or load them automatically.

## Architecture

Automation is split into two independent workflows:

1. Daily scanner/export pipeline:
   - Runs `main.py`.
   - Generates daily reports under `reports/` and history under `performance/`.
   - Runs `web_exporter.py` after the scanner because `main.py` does not currently call the exporter.
   - Updates `data/web_snapshot.json`.
   - Updates paper-trading daily picks and opens newly eligible paper positions through the exporter path.

2. Intraday paper-ledger refresh:
   - Runs `refresh_paper_trading.py`.
   - Updates existing paper positions only.
   - Refreshes mark-to-market values, unrealized P/L, exits, equity curve, portfolio summary, and performance statistics.
   - Does not run the scanner.
   - Does not generate new signals.
   - Does not open new positions.

## Project Paths

- Project root: `/Users/rileychalmers/AI_Stock_Hunter/AI_Stock_Hunter_v2`
- Python executable: `/Users/rileychalmers/AI_Stock_Hunter/AI_Stock_Hunter_v2/venv/bin/python`
- Daily wrapper: `/Users/rileychalmers/AI_Stock_Hunter/AI_Stock_Hunter_v2/automation/scripts/run_daily_pipeline.sh`
- Refresh wrapper: `/Users/rileychalmers/AI_Stock_Hunter/AI_Stock_Hunter_v2/automation/scripts/refresh_paper_ledger.sh`

The wrappers set a limited launchd-safe `PATH`, change to the project root, and use the venv Python directly.

## Schedules

Daily scanner/export:

- Monday through Friday.
- 6:00 PM in the Mac's local timezone.
- Intended to run after the U.S. market close, when reliable end-of-day market data is expected to be available.
- The wrapper records the `America/New_York` market date and uses that market date for same-day duplicate protection.
- If launchd runs late after sleep or wake, the wrapper will not process before the New York post-close window unless `--force` is used manually.

Paper ledger refresh:

- Launchd checks hourly at `:05` between 9:05 AM and 4:05 PM local time.
- The wrapper evaluates the actual market window in `America/New_York`, not the Mac's local timezone.
- The wrapper performs a scheduled refresh only on weekdays during the New York 9:30 AM to 4:00 PM regular market window.
- `MarketDataService` must report `market_state=OPEN` before a scheduled refresh proceeds.
- If quotes are unavailable or stale, the paper-trading engine retains last known prices, marks positions stale, and does not process exits from stale quotes.

The launchd trigger itself remains local-time based because launchd calendar intervals are local to the Mac. The wrappers are timezone-aware and use `America/New_York` with daylight saving handled by Python `zoneinfo`, so market-session decisions remain correct if the Mac travels to another timezone.

## Environment And Secrets

- `.env` remains local and ignored by Git.
- Scripts load `.env` if it exists.
- Secret values are never printed intentionally.
- No API keys or passwords are embedded in plist files.
- Missing email credentials do not block the scanner; `main.py` already skips email when `EMAIL_ADDRESS` or `EMAIL_PASSWORD` is missing.

## Logs And Locks

Runtime logs:

- `automation/logs/daily-pipeline.log`
- `automation/logs/daily-pipeline-error.log`
- `automation/logs/paper-refresh.log`
- `automation/logs/paper-refresh-error.log`
- `automation/logs/*.launchd.log`

Runtime locks and markers:

- `automation/locks/`

Logs and locks are ignored by Git. Basic stale lock recovery is included. macOS/system log rotation is not configured yet; rotate or delete old project log files manually if they grow too large.

## Manual Testing

Validate shell scripts:

```bash
bash -n automation/scripts/*.sh
```

Validate launchd plists:

```bash
plutil -lint automation/launchd/*.plist
```

Test the daily wrapper without modifying reports or opening duplicate paper positions:

```bash
automation/scripts/run_daily_pipeline.sh --dry-run
```

Run the daily pipeline manually:

```bash
automation/scripts/run_daily_pipeline.sh
```

Force a same-day manual rerun:

```bash
automation/scripts/run_daily_pipeline.sh --force
```

Test the refresh wrapper without writing ledger or export files:

```bash
automation/scripts/refresh_paper_ledger.sh --dry-run --force
```

Run one manual paper refresh:

```bash
automation/scripts/refresh_paper_ledger.sh --force
```

View status:

```bash
automation/scripts/status_launch_agents.sh
```

Check for old cron jobs before installing launchd:

```bash
crontab -l
```

Do not let an old scanner cron job and the launchd daily pipeline run at the same time. Disable any previous scanner cron entry manually before enabling these launch agents.

Tail logs:

```bash
tail -f automation/logs/daily-pipeline.log
tail -f automation/logs/paper-refresh.log
```

## Install

This task does not install or load launch agents. To install later:

```bash
automation/scripts/install_launch_agents.sh
```

For non-interactive installation after reviewing the scripts:

```bash
automation/scripts/install_launch_agents.sh --yes
```

The installer validates project paths, validates plist syntax, refuses to overwrite unrelated existing agents, copies the plists into `~/Library/LaunchAgents`, and loads them with `launchctl bootstrap`.

Before confirmation, the installer prints the plist destination, labels, resolved project path, resolved Python path, daily schedule, refresh schedule, market timezone, log locations, and cron-conflict reminder.

## Uninstall

Disable all AI Stock Hunter automation safely:

```bash
automation/scripts/uninstall_launch_agents.sh
```

For non-interactive uninstall:

```bash
automation/scripts/uninstall_launch_agents.sh --yes
```

The uninstall script unloads only these labels and removes only their plist files:

- `com.aistockhunter.daily-pipeline`
- `com.aistockhunter.paper-refresh`

It does not delete project data, reports, logs, or ledger state.

## Reinstall

```bash
automation/scripts/uninstall_launch_agents.sh --yes
automation/scripts/install_launch_agents.sh --yes
```

## Failure Handling

- Mac asleep: launchd does not guarantee missed calendar jobs run while the Mac is asleep or powered off, and it does not guarantee catch-up execution after wake. Check status/logs after wake.
- Delayed wake-up: daily duplicate markers are keyed to the New York market date, and the wrapper refuses pre-close runs unless forced. This prevents a late launchd event from silently processing the wrong market date or duplicating a completed date.
- No internet or yfinance failure: scanner or refresh may fail or mark prices stale; no ledger reset is performed.
- Market holiday: scheduled refresh should no-op when the market is not open. If the clock window is open but market data is unavailable or stale, the engine marks prices stale and avoids processing exits.
- Missing `.env`: allowed unless email delivery is required.
- Missing venv: wrappers fail before running jobs.
- Stale scanner report: daily wrapper regenerates the scanner report before export; refresh uses existing daily picks only for metadata.
- Corrupt ledger state: refresh exits non-zero and does not delete or reset state.
- Duplicate same-day scanner run: daily wrapper writes a same-day success marker and skips later runs unless `--force` is used. Paper engine processed-pick tracking remains the deeper duplicate-position guard.
- Overlapping runs: lock directories prevent overlap. Stale locks are removed after a timeout if the original process is gone.

## Changing Schedules Safely

1. Edit the matching plist under `automation/launchd/`.
2. Run `plutil -lint automation/launchd/*.plist`.
3. Reinstall agents:

```bash
automation/scripts/uninstall_launch_agents.sh --yes
automation/scripts/install_launch_agents.sh --yes
```
