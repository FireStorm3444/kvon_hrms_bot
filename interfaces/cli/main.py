import time
import random
import logging
import argparse
from datetime import datetime
from config import get_config, ConfigError
from core.api_client import APIClient
from core.database import DatabaseManager
from core.logging_config import setup_logging
from services.hrms_service import HRMSService, AttendanceAction
from services.notifier import NotificationService

setup_logging()
logger = logging.getLogger(__name__)

def run_workflow(action: AttendanceAction, is_automated: bool):
    logger.info("Starting workflow for action=%s automated=%s.", action.value, is_automated)
    try:
        config = get_config()
    except ConfigError as exc:
        logger.error("Configuration Error: %s", exc)
        return

    # Initialize State Engines
    db = DatabaseManager()
    today_str = datetime.today().strftime("%Y-%m-%d")
    
    api_client = APIClient(config.api_url)
    hrms = HRMSService(config, api_client)
    notifier = NotificationService(config)

    # 1. Idempotent Skip-Date Verification
    if db.is_date_skipped(today_str):
        logger.info("📆 Date %s matches skip ledger. Gracefully aborting execution.", today_str)
        notifier.send_alert(f"ℹ️ Automated *{action.value}* skipped for today (`{today_str}`) via Telegram command.")
        return

    # 2. Weekend Check
    if datetime.today().weekday() > 4:  # 5 = Saturday, 6 = Sunday
        logger.info("Weekend detected. Skipping execution.")
        notifier.send_alert("Weekend detected. Automated attendance skipped.")
        return
    
    # 3. Apply organic delay for automated morning check-ins
    if is_automated:
        delay = random.randint(0, 900)  # Up to 15 minutes
        logger.info("Scheduled to %s after %s seconds...", action.value, delay)
        notifier.send_alert(f"Automated {action.value} will be attempted in {delay} seconds.")
        time.sleep(delay)

    # 4. Authenticate
    success, message = hrms.login()
    if not success:
        notifier.send_alert(f"Failed to login for {action.value}: {message}")
        return

    # 5. Non-Interactive Headless Timesheet Management (Batch Processing)
    if action == AttendanceAction.CHECK_OUT:
        logger.info("Querying local persistence for pending timesheet entries...")
        pending_timesheets = db.get_pending_timesheets()
        
        if pending_timesheets:
            logger.info("📝 %d staged timesheet payload(s) found. Dispatching to API...", len(pending_timesheets))
            ts_success = hrms.submit_timesheet(pending_timesheets)
            
            if ts_success:
                notifier.send_alert(f"✅ {len(pending_timesheets)} staged timesheet(s) flushed and uploaded successfully.")
                db.clear_pending_timesheets()
            else:
                notifier.send_alert("⚠️ Staged timesheet batch upload rejected by API. Forcing check-out attempt anyway.")
        else:
            logger.info("ℹ️ No staged timesheet metadata discovered. Attempting raw check-out.")

    # 6. Execute Attendance Pipeline
    result = hrms.submit_attendance(action)
    
    # Normalize varied return types from the service layer wrapper
    if isinstance(result, tuple):
        status, server_msg = result
    else:
        status, server_msg = result, "Action completed successfully."

    if status:
        logger.info("Workflow completed successfully for action=%s.", action.value)
        notifier.send_alert(f"Successfully executed {action.value}: {server_msg}")
    else:
        # If this fails with "please fill the timesheet", the text maps cleanly into server_msg
        logger.warning("Workflow failed for action=%s with message: %s", action.value, server_msg)
        notifier.send_alert(f"❌ Failed to execute {action.value}: `{server_msg}`")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KvonTech Automated HRMS")
    parser.add_argument("--action", type=str, choices=["check-in", "check-out"], required=True)
    parser.add_argument("--automated", action="store_true", help="Enable random delays for cron execution")
    
    args = parser.parse_args()
    
    action_enum = AttendanceAction.CHECK_IN if args.action == "check-in" else AttendanceAction.CHECK_OUT
    run_workflow(action_enum, args.automated)