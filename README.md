# HRMS Attendance Bot

Automation for KvonTech HRMS attendance, timesheets, and Telegram-driven daily workflow.

This project can run in two main ways:

- as a simple command-line automation for check-in/check-out
- as an interactive Telegram bot on a server, powered by `interfaces/telegram/bot_daemon.py`

## Features

- Automated HRMS check-in and check-out
- Random check-in delay for more natural scheduled runs
- Telegram success/failure notifications
- Interactive Telegram commands for status, check-in, check-out, timesheets, and skip dates
- Local SQLite state in `hrms_state.db`
- Timesheet staging before check-out
- Bulk timesheet upload during check-out
- Scheduled checkout from Telegram while the daemon is running
- Weekend skip behavior for automated CLI runs

## Requirements

- Python 3.14 or newer
- KvonTech HRMS API URL
- Valid HRMS employee credentials
- Office latitude and longitude
- Telegram bot token and chat ID
- A server/VPS/always-on machine if you want the interactive Telegram bot

## Installation

Clone the project, then install dependencies:

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Windows Command Prompt:

```bat
py -m venv .venv
.\.venv\Scripts\activate.bat
py -m pip install -r requirements.txt
```

If you use `uv`, you can install and run with:

Linux/macOS:

```bash
uv sync
uv run python -m interfaces.cli.main --action check-in
```

Windows PowerShell:

```powershell
uv sync
uv run python -m interfaces.cli.main --action check-in
```

## Environment Setup

Create a `.env` file in the project root:

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Windows Command Prompt:

```bat
copy .env.example .env
```

Fill it with your real values:

```env
KVON_API_URL=https://your-hrms-api.example.com/api
OFFICE_LAT=12.9716
OFFICE_LONG=77.5946
KVON_EMP_ID=YOUR_EMPLOYEE_ID
KVON_PASSWORD=YOUR_PASSWORD
KVON_EMAIL=you@example.com
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_TELEGRAM_CHAT_ID
```

Variable reference:

| Variable | Purpose |
| --- | --- |
| `KVON_API_URL` | Base HRMS API URL, usually ending with `/api` |
| `OFFICE_LAT` | Office latitude used for attendance location |
| `OFFICE_LONG` | Office longitude used for attendance location |
| `KVON_EMP_ID` | Employee ID used during login |
| `KVON_PASSWORD` | HRMS password |
| `KVON_EMAIL` | HRMS email address |
| `TELEGRAM_BOT_TOKEN` | Bot token from Telegram BotFather |
| `TELEGRAM_CHAT_ID` | Telegram chat/user/group ID that receives messages |

## CLI Usage

Run a manual check-in:

Linux/macOS:

```bash
python -m interfaces.cli.main --action check-in
```

Windows:

```powershell
py -m interfaces.cli.main --action check-in
```

Run an automated check-in with a random delay of up to 15 minutes:

Linux/macOS:

```bash
python -m interfaces.cli.main --action check-in --automated
```

Windows:

```powershell
py -m interfaces.cli.main --action check-in --automated
```

Run check-out:

Linux/macOS:

```bash
python -m interfaces.cli.main --action check-out
```

Windows:

```powershell
py -m interfaces.cli.main --action check-out
```

For check-out, the CLI looks for pending timesheets in the local SQLite database. If timesheets were staged through Telegram, they are uploaded first, then the check-out request is sent. If no timesheets are staged, the app still attempts a raw check-out and reports the HRMS response.

## Telegram Bot Setup

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`, choose a name and username, then copy the bot token.
3. Put the token in `.env` as `TELEGRAM_BOT_TOKEN`.
4. Message your new bot once so Telegram creates a chat with it.
5. Visit this URL in your browser, replacing `<TOKEN>`:

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

6. Find the `chat.id` value and put it in `.env` as `TELEGRAM_CHAT_ID`.

For a group chat, add the bot to the group, send a message in the group, then use the same `getUpdates` URL to find the group chat ID.

## Interactive Telegram Mode

If you have a server, VPS, Raspberry Pi, or any always-on machine, you can run the interactive bot:

Linux/macOS:

```bash
python -m interfaces.telegram.bot_daemon
```

Windows:

```powershell
py -m interfaces.telegram.bot_daemon
```

The daemon polls Telegram and enables these commands:

| Command | What it does |
| --- | --- |
| `/status` | Shows live HRMS status and local timesheet state |
| `/check_in` | Forces an immediate check-in |
| `/timesheet` | Stages, reviews, resets, or uploads timesheets |
| `/check_out` | Starts checkout flow using staged timesheets |
| `/skip_check_in` | Skips an automated check-in for tomorrow or a custom date |

The daemon also runs a background checkout scheduler. From `/check_out`, choose automated checkout, enter a time like `06:30 PM`, and keep the daemon running. At that IST time, it uploads staged timesheets and checks out.

## Automated Check-In Scheduling

For a simple automated morning check-in, schedule the CLI on an always-on machine.

### Linux Server Cron

Open crontab:

```bash
crontab -e
```

Example weekday check-in at 9:00 AM IST:

```cron
0 9 * * 1-5 cd /absolute/path/to/HRMS && /absolute/path/to/HRMS/.venv/bin/python -m interfaces.cli.main --action check-in --automated >> hrms_cron.log 2>&1
```

If you do not use a virtual environment, use the full path to your Python executable instead:

```cron
0 9 * * 1-5 cd /absolute/path/to/HRMS && /usr/bin/python3 -m interfaces.cli.main --action check-in --automated >> hrms_cron.log 2>&1
```

`cron-job.org` is useful for calling HTTP URLs, but this project currently exposes a CLI and Telegram polling daemon, not a web endpoint. Use normal server cron for the command above. If you later add a secured webhook endpoint, then cron-job.org can call that endpoint on a schedule.

### Windows Task Scheduler

Most Windows users should use Task Scheduler instead of cron.

Create a scheduled task from the GUI:

1. Open **Task Scheduler**.
2. Choose **Create Basic Task**.
3. Set the trigger to weekdays at your check-in time.
4. Choose **Start a program**.
5. Set **Program/script** to the full path of Python, for example:

```text
C:\Users\YourName\AppData\Local\Programs\Python\Python314\python.exe
```

6. Set **Add arguments** to:

```text
-m interfaces.cli.main --action check-in --automated
```

7. Set **Start in** to your project folder, for example:

```text
C:\Users\YourName\Projects\HRMS
```

If you use the project virtual environment, set **Program/script** to:

```text
C:\Users\YourName\Projects\HRMS\.venv\Scripts\python.exe
```

You can also create the task from PowerShell:

```powershell
$project = "C:\Users\YourName\Projects\HRMS"
$python = "$project\.venv\Scripts\python.exe"
$action = New-ScheduledTaskAction -Execute $python -Argument "-m interfaces.cli.main --action check-in --automated" -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 9:00AM
Register-ScheduledTask -TaskName "HRMS Automated Check-In" -Action $action -Trigger $trigger -Description "Automated weekday HRMS check-in"
```

## GitHub Actions

You can also run automated check-in from GitHub Actions by using this command in the workflow:

```bash
python -m interfaces.cli.main --action check-in --automated
```

Add these repository secrets:

- `KVON_API_URL`
- `OFFICE_LAT`
- `OFFICE_LONG`
- `KVON_EMP_ID`
- `KVON_PASSWORD`
- `KVON_EMAIL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Because attendance automation depends on your account, network, timezone, and HRMS availability, test the workflow manually before relying on a schedule.

## Local State

The app writes local state to:

```text
hrms_state.db
```

This database stores:

- dates skipped through `/skip_check_in`
- pending timesheets staged through `/timesheet`
- the scheduled checkout time created through Telegram

The database is intentionally ignored by git.

## Logs

Runtime logs are written to:

```text
hrms_system.log
```

You can change the log file or log level with:

Linux/macOS:

```bash
HRMS_LOG_FILE=logs/hrms.log HRMS_LOG_LEVEL=DEBUG python -m interfaces.cli.main --action check-in
```

Windows PowerShell:

```powershell
$env:HRMS_LOG_FILE = "logs/hrms.log"
$env:HRMS_LOG_LEVEL = "DEBUG"
py -m interfaces.cli.main --action check-in
```

## How It Works

1. Loads settings from `.env` or environment variables.
2. Checks the local skip-date ledger.
3. Skips weekend CLI automation.
4. Applies a random delay when `--automated` is used.
5. Logs in to the HRMS API.
6. Uploads staged timesheets before check-out.
7. Sends attendance with slightly jittered office coordinates.
8. Sends Telegram notifications with the result.

## Troubleshooting

If configuration fails, check that every required variable exists in `.env`.

If Telegram does not respond, verify the bot token, chat ID, and that you sent at least one message to the bot.

If login fails, verify `KVON_EMP_ID`, `KVON_EMAIL`, `KVON_PASSWORD`, and `KVON_API_URL`.

If attendance is rejected for location, confirm `OFFICE_LAT` and `OFFICE_LONG` match the office location expected by HRMS.

If checkout fails because timesheets are missing, stage them first with `/timesheet`, or use the `/timesheet` send option to upload them before checkout.

## Project Structure

```text
config.py                              Environment loading and validation
core/api_client.py                     HTTP client with retry behavior
core/database.py                       SQLite state for skips, timesheets, and checkout schedule
core/logging_config.py                 Shared logging setup
interfaces/cli/main.py                 CLI entry point for check-in/check-out
interfaces/telegram/bot_daemon.py      Telegram polling daemon
interfaces/telegram/handlers/          Telegram command handlers
services/hrms_service.py               HRMS login, timesheet, attendance, and status logic
services/geo_service.py                Coordinate jitter helper
services/notifier.py                   Telegram notification service
```
