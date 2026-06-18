# HRMS Attendance Script

Automates KvonTech HRMS attendance actions from the command line.

The script can:

- check in with office coordinates
- check out after submitting a timesheet
- add a random delay for automated check-ins
- send Telegram notifications about success or failure
- run on GitHub Actions for weekday morning check-ins

## Requirements

- Python 3.14 or newer
- HRMS API URL
- valid KvonTech HRMS employee credentials
- office latitude and longitude
- Telegram bot token and chat ID
- internet access from the machine or GitHub runner

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

If you use `uv`, you can also run commands with:

```bash
uv run python main.py --action check-in
```

## Environment Variables

Create a `.env` file in the project root. The file is ignored by git, so keep your real credentials there.

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
| `KVON_API_URL` | Base HRMS API URL, without a trailing endpoint path (+/api, if all your endpoints use it) |
| `OFFICE_LAT` | Office latitude used for attendance location |
| `OFFICE_LONG` | Office longitude used for attendance location |
| `KVON_EMP_ID` | Employee ID used during login |
| `KVON_PASSWORD` | HRMS password |
| `KVON_EMAIL` | HRMS email address |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | Telegram chat ID that receives notifications |

## How To Run

Run a manual check-in:

```bash
python main.py --action check-in
```

Run an automated check-in with a random delay of up to 15 minutes:

```bash
python main.py --action check-in --automated
```

Run a manual check-out:

```bash
python main.py --action check-out
```

Check-out asks for timesheet details before submitting attendance:

- task name
- task details
- mentor name
- start time, default `09:00`
- end time, default `18:00`

Because check-out requires interactive input, do not use it in a headless cron job or GitHub Actions job unless the script is updated to accept timesheet values as command-line arguments.

## Weekend Behavior

The workflow skips execution on Saturdays and Sundays.

This applies to both check-in and check-out because `main.py` checks the current weekday before doing any HRMS work.

## Logs

Runtime logs are written to:

```text
hrms_system.log
```

The log file is ignored by git.

## GitHub Actions Setup

The repository includes `.github/workflows/attendance.yml` for automated weekday morning check-ins.

The workflow currently runs:

```bash
python main.py --action check-in --automated
```

Schedule:

- Monday to Friday
- `03:30 UTC`
- `09:00 IST`

Add these repository secrets in GitHub:

- `KVON_API_URL`
- `OFFICE_LAT`
- `OFFICE_LONG`
- `KVON_EMP_ID`
- `KVON_PASSWORD`
- `KVON_EMAIL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

You can also trigger the workflow manually from the GitHub Actions tab using `workflow_dispatch`.

## How It Works

1. Loads required settings from `.env` or environment variables.
2. Skips execution if today is a weekend.
3. Optionally waits for a random delay when `--automated` is used.
4. Logs in to the HRMS API.
5. For check-out, submits a timesheet first.
6. Sends the check-in or check-out request with slightly jittered office coordinates.
7. Sends a Telegram notification with the result.

## Troubleshooting

If the script exits with a configuration error, check that all required variables exist in `.env` or in your shell environment.

If login fails, verify `KVON_EMP_ID`, `KVON_EMAIL`, `KVON_PASSWORD`, and `KVON_API_URL`.

If location-based attendance is rejected, confirm `OFFICE_LAT` and `OFFICE_LONG` match the office location expected by HRMS.

If Telegram notifications fail, verify that the bot token is valid and that the bot can message the configured chat ID.

## Project Structure

```text
main.py                  CLI entry point
config.py                Environment loading and validation
core/api_client.py       HTTP client with retry behavior
services/hrms_service.py HRMS login, timesheet, and attendance logic
services/geo_service.py  Coordinate jitter helper
services/notifier.py     Telegram notification service
```
