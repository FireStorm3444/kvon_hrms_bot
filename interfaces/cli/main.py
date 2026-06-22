import time
import random
import logging
import argparse
from datetime import datetime
from config import get_config, ConfigError #[cite: 8]
from core.api_client import APIClient #[cite: 8]
from core.database import DatabaseManager
from core.logging_config import setup_logging
from services.hrms_service import HRMSService, AttendanceAction #[cite: 8]
from services.notifier import NotificationService #[cite: 8]

setup_logging()
logger = logging.getLogger(__name__)

def run_workflow(action: AttendanceAction, is_automated: bool):
    logger.info("Starting workflow for action=%s automated=%s.", action.value, is_automated)
    try:
        config = get_config() #[cite: 8]
    except ConfigError as exc:
        logger.error("Configuration Error: %s", exc) #[cite: 8]
        return

    # Initialize State Engines
    db = DatabaseManager()
    today_str = datetime.today().strftime("%Y-%m-%d")
    
    api_client = APIClient(config.api_url) #[cite: 8]
    hrms = HRMSService(config, api_client) #[cite: 8]
    notifier = NotificationService(config) #[cite: 8]

    # 1. Idempotent Skip-Date Verification
    if db.is_date_skipped(today_str):
        logger.info("📆 Date %s matches skip ledger. Gracefully aborting execution.", today_str)
        notifier.send_alert(f"ℹ️ Automated *{action.value}* skipped for today (`{today_str}`) via Telegram command.")
        return

    # 2. Weekend Check
    if datetime.today().weekday() > 4:  # 5 = Saturday, 6 = Sunday[cite: 8]
        logger.info("Weekend detected. Skipping execution.") #[cite: 8]
        notifier.send_alert("Weekend detected. Automated attendance skipped.") #[cite: 8]
        return
    
    # 3. Apply organic delay for automated morning check-ins
    if is_automated:
        delay = random.randint(0, 900)  # Up to 15 minutes[cite: 8]
        logger.info("Scheduled to %s after %s seconds...", action.value, delay) #[cite: 8]
        notifier.send_alert(f"Automated {action.value} will be attempted in {delay} seconds.") #[cite: 8]
        time.sleep(delay) #[cite: 8]

    # 4. Authenticate
    success, message = hrms.login() #[cite: 8]
    if not success:
        notifier.send_alert(f"Failed to login for {action.value}: {message}") #[cite: 8]
        return

    # 5. Non-Interactive Headless Timesheet Management
    if action == AttendanceAction.CHECK_OUT: #[cite: 8]
        logger.info("Querying local persistence for pending timesheet entries...")
        pending_ts = db.get_pending_timesheet()
        
        if pending_ts:
            logger.info("📝 Staged timesheet payload found. Dispatching to API...")
            ts_success = hrms.submit_timesheet(
                task_name=pending_ts["task_name"],
                task_details=pending_ts["task_details"],
                mentor_name=pending_ts["mentor_name"],
                start_time=pending_ts["start_time"],
                end_time=pending_ts["end_time"]
            ) #[cite: 5]
            
            if ts_success:
                notifier.send_alert("✅ Staged timesheet data flushed and uploaded successfully.")
                db.clear_pending_timesheet()
            else:
                notifier.send_alert("⚠️ Staged timesheet upload rejected by API. Forcing check-out attempt anyway.")
        else:
            logger.info("ℹ️ No staged timesheet metadata discovered. Attempting raw check-out.")

    # 6. Execute Attendance Pipeline
    result = hrms.submit_attendance(action) #[cite: 8]
    
    # Normalize varied return types from the service layer wrapper
    if isinstance(result, tuple):
        status, server_msg = result #[cite: 5]
    else:
        status, server_msg = result, "Action completed successfully." #[cite: 5]

    if status:
        logger.info("Workflow completed successfully for action=%s.", action.value)
        notifier.send_alert(f"Successfully executed {action.value}: {server_msg}") #[cite: 8]
    else:
        # If this fails with "please fill the timesheet", the text maps cleanly into server_msg
        logger.warning("Workflow failed for action=%s with message: %s", action.value, server_msg)
        notifier.send_alert(f"❌ Failed to execute {action.value}: `{server_msg}`")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KvonTech Automated HRMS") #[cite: 8]
    parser.add_argument("--action", type=str, choices=["check-in", "check-out"], required=True) #[cite: 8]
    parser.add_argument("--automated", action="store_true", help="Enable random delays for cron execution") #[cite: 8]
    
    args = parser.parse_args() #[cite: 8]
    
    action_enum = AttendanceAction.CHECK_IN if args.action == "check-in" else AttendanceAction.CHECK_OUT #[cite: 8]
    run_workflow(action_enum, args.automated) #[cite: 8]
