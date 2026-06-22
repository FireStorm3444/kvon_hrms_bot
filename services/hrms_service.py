import logging
from enum import Enum
from datetime import datetime
from config import Config
from core.api_client import APIClient
from services.geo_service import GeoService
from services.notifier import NotificationService

logger = logging.getLogger(__name__)

class AttendanceAction(str, Enum):
    CHECK_IN = "check-in"
    CHECK_OUT = "check-out"

class api_endpoints(str, Enum):
    LOGIN = "/auth/login"
    TIMESHEET_BULK = "/timesheets/bulk"
    ATTENDANCE_CHECK_IN = "/attendance/check-in"
    ATTENDANCE_CHECK_OUT = "/attendance/check-out"

class HRMSService:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def login(self) -> bool:
        logger.info("🔑 Attempting authentication...")
        payload = {
            "emp_id": self.config.emp_id,
            "email": self.config.email,
            "password": self.config.password
        }

        notifier = NotificationService(self.config)
        
        try:
            response = self.api.post(api_endpoints.LOGIN.value, payload)
            response.raise_for_status()
            data = response.json()
            
            token = data[0].get("access_token") if isinstance(data, list) and data else data.get("access_token") if isinstance(data, dict) else None
                
            if token:
                self.api.set_bearer_token(token)
                logger.info("✅ Authentication successful.")
                notifier.send_alert("✅ Authentication successful.")
                return True, "Authentication successful"
            
            logger.error("❌ Failed to extract token. API response type: %s", type(data).__name__)
            notifier.send_alert("❌ Authentication failed: Unable to extract token.")
            return False, "Failed to extract token"
            
        except Exception as e:
            logger.exception("❌ Login failed.")
            notifier.send_alert("❌ Login failed.")
            return False, str(e)

    def submit_timesheet(self, task_name: str, task_details: str, mentor_name: str, start_time: str, end_time: str) -> bool:
        today_str = datetime.today().strftime("%Y-%m-%d")
        payload = [{
            "date": today_str,
            "start_time": start_time,
            "end_time": end_time,
            "mentor_name": mentor_name,
            "task_name": task_name,
            "task_details": task_details
        }]

        logger.info("📝 Submitting timesheet for %s...", today_str)
        try:
            response = self.api.post(api_endpoints.TIMESHEET_BULK.value, payload)
            if response.status_code in [200, 201]:
                logger.info("✅ Timesheet logged successfully.")
                return True
                
            logger.warning("❌ Timesheet rejected: %s", response.text)
            return False
        except Exception:
            logger.exception("❌ Timesheet request failed.")
            return False

    def submit_attendance(self, action: AttendanceAction) -> bool:
        lat, long = GeoService.get_jittered_coordinates(self.config.office_lat, self.config.office_long)
        payload = {"latitude": lat, "longitude": long}
        action_name = action.value.replace('-', ' ').title()
        
        logger.info("📍 Sending %s payload: %s, %s", action.value, lat, long)
        try:
            response = self.api.post(api_endpoints.ATTENDANCE_CHECK_IN.value if action == AttendanceAction.CHECK_IN else api_endpoints.ATTENDANCE_CHECK_OUT.value, payload)
            text = response.text
            if response.status_code in [200, 201]:
                logger.info("✅ %s successful.", action_name)
                return True
                
            logger.warning("❌ %s rejected: %s", action_name, text)
            return False, text
        except Exception as e:
            logger.exception("❌ %s request failed.", action_name)
            return False, str(e)
