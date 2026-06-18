import time
import random
import logging
import argparse
from datetime import datetime
from config import get_config, ConfigError
from core.api_client import APIClient
from services.hrms_service import HRMSService, AttendanceAction
from services.notifier import NotificationService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("hrms_system.log"), logging.StreamHandler()]
)

def run_workflow(action: AttendanceAction, is_automated: bool):
    if datetime.today().weekday() > 4:
        logging.info("Weekend detected. Skipping execution.")
        return

    try:
        config = get_config()
    except ConfigError as exc:
        logging.error("Configuration Error: %s", exc)
        return

    api_client = APIClient(config.api_url)
    hrms = HRMSService(config, api_client)
    notifier = NotificationService(config)

    # 1. Apply organic delay for automated morning check-ins
    if is_automated:
        delay = random.randint(0, 900)  # Up to 15 minutes
        logging.info("Scheduled to %s after %s seconds...", action.value, delay)
        time.sleep(delay)

    # 2. Authenticate
    sucess, message = hrms.login()
    if not sucess:
        notifier.send_alert(f"Failed to login for {action.value}: {message}")
        return

    # 3. Handle Timesheet for Check-out
    if action == AttendanceAction.CHECK_OUT:
        print("\n📝 --- Timesheet Entry Required ---")
        try:
            task_name = input("Enter Task Name: ").strip()
            task_details = input("Enter Task Details: ").strip()
            mentor_name = input("Enter Mentor Name: ").strip()
            start_time = input("Enter Start Time (HH:MM) [09:00]: ").strip() or "09:00"
            end_time = input("Enter End Time (HH:MM) [18:00]: ").strip() or "18:00"
        except EOFError:
            logging.error("❌ Headless execution detected. Cannot prompt for timesheet.")
            notifier.send_alert("Check-out failed: Headless execution hit interactive prompt.")
            return

        if not all([task_name, task_details, mentor_name]):
            logging.error("❌ Missing timesheet fields. Aborting.")
            return

        if not hrms.submit_timesheet(task_name, task_details, mentor_name, start_time, end_time):
            notifier.send_alert("Timesheet submission failed.")
            return

    # 4. Execute Attendance
    success, message = hrms.submit_attendance(action)
    if success:
        notifier.send_alert(f"Successfully executed {action.value}: {message}")
    else:
        notifier.send_alert(f"Failed to execute {action.value}: {message}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KvonTech Automated HRMS")
    parser.add_argument("--action", type=str, choices=["check-in", "check-out"], required=True)
    parser.add_argument("--automated", action="store_true", help="Enable random delays for cron execution")
    
    args = parser.parse_args()
    
    action_enum = AttendanceAction.CHECK_IN if args.action == "check-in" else AttendanceAction.CHECK_OUT
    run_workflow(action_enum, args.automated)