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
    ATTENDANCE_STATUS = "/attendance/today/status"

class HRMSService:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def login(self, silent: bool = False) -> tuple[bool, str]:
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
                if not silent:
                    notifier.send_alert("✅ Authentication successful.")
                return True, "Authentication successful"
            
            logger.error("❌ Failed to extract token. API response type: %s", type(data).__name__)
            if not silent:
                notifier.send_alert("❌ Authentication failed: Unable to extract token.")
            return False, "Failed to extract token"
            
        except Exception as e:
            logger.exception("❌ Login failed.")
            if not silent:
                notifier.send_alert("❌ Login failed.")
            return False, str(e)

    def submit_timesheet(self, timesheets: list[dict]) -> bool:
        """Takes a list of timesheet dictionaries and submits them as a single bulk payload."""
        if not timesheets:
            logger.info("ℹ️ No timesheets provided for submission.")
            return True

        # Defensively sort the list chronologically to ensure network safety
        sorted_timesheets = sorted(timesheets, key=lambda x: x["start_time"])
        
        payload = []
        for ts in sorted_timesheets:
            # Fallback to today's date if target_date isn't present in the dictionary
            date_str = ts.get("target_date") or datetime.today().strftime("%Y-%m-%d")
            
            payload.append({
                "date": date_str,
                "start_time": ts["start_time"],
                "end_time": ts["end_time"],
                "mentor_name": ts["mentor_name"],
                "task_name": ts["task_name"],
                "task_details": ts["task_details"]
            })

        logger.info("📝 Submitting batch of %d timesheet(s)...", len(payload))
        try:
            response = self.api.post(api_endpoints.TIMESHEET_BULK.value, payload)
            if response.status_code in [200, 201]:
                logger.info("✅ Bulk timesheet logged successfully.")
                return True
                
            logger.warning("❌ Timesheet batch rejected: %s", response.text)
            return False
        except Exception:
            logger.exception("❌ Timesheet bulk request failed.")
            return False

    def submit_attendance(self, action: AttendanceAction) -> bool | tuple[bool, str]:
        lat, long = GeoService.get_jittered_coordinates(self.config.office_lat, self.config.office_long)
        payload = {"latitude": lat, "longitude": long}
        action_name = action.value.replace('-', ' ').title()
        
        logger.info("📍 Sending %s payload: %s, %s", action.value, lat, long)
        try:
            response = self.api.post(
                api_endpoints.ATTENDANCE_CHECK_IN.value if action == AttendanceAction.CHECK_IN 
                else api_endpoints.ATTENDANCE_CHECK_OUT.value, 
                payload
            )
            text = response.text
            if response.status_code in [200, 201]:
                logger.info("✅ %s successful.", action_name)
                return True
                
            logger.warning("❌ %s rejected: %s", action_name, text)
            return False, text
        except Exception as e:
            logger.exception("❌ %s request failed.", action_name)
            return False, str(e)
        
    def get_status(self) -> dict | None:
        logger.info("📊 Fetching live attendance status...")
        try:
            response = self.api.get(api_endpoints.ATTENDANCE_STATUS.value)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.exception("❌ Failed to fetch status.")
            return None