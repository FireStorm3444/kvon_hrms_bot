import logging
from enum import Enum
from datetime import datetime
from config import Config
from core.api_client import APIClient
from services.geo_service import GeoService

class AttendanceAction(str, Enum):
    CHECK_IN = "check-in"
    CHECK_OUT = "check-out"

class HRMSService:
    def __init__(self, config: Config, api_client: APIClient):
        self.config = config
        self.api = api_client

    def login(self) -> bool:
        logging.info("🔑 Attempting authentication...")
        payload = {
            "emp_id": self.config.emp_id,
            "email": self.config.email,
            "password": self.config.password
        }
        
        try:
            response = self.api.post("/auth/login", payload)
            response.raise_for_status()
            data = response.json()
            
            token = data[0].get("access_token") if isinstance(data, list) and data else data.get("access_token") if isinstance(data, dict) else None
                
            if token:
                self.api.set_bearer_token(token)
                logging.info("✅ Authentication successful.")
                return True
            
            logging.error("❌ Failed to extract token. API returned: %s", data)
            return False
            
        except Exception as e:
            logging.error("❌ Login failed: %s", e)
            return False

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

        logging.info("📝 Submitting timesheet for %s...", today_str)
        try:
            response = self.api.post("/timesheets/bulk", payload)
            if response.status_code in [200, 201]:
                logging.info("✅ Timesheet logged successfully.")
                return True
                
            logging.warning("❌ Timesheet rejected: %s", response.text)
            return False
        except Exception as e:
            logging.error("❌ Timesheet request failed: %s", e)
            return False

    def submit_attendance(self, action: AttendanceAction) -> bool:
        lat, long = GeoService.get_jittered_coordinates(self.config.office_lat, self.config.office_long)
        payload = {"latitude": lat, "longitude": long}
        action_name = action.value.replace('-', ' ').title()
        
        logging.info("📍 Sending %s payload: %s, %s", action.value, lat, long)
        try:
            response = self.api.post(f"/attendance/{action.value}", payload)
            if response.status_code in [200, 201]:
                logging.info("✅ %s successful.", action_name)
                return True
                
            logging.warning("❌ %s rejected: %s", action_name, response.text)
            return False
        except Exception as e:
            logging.error("❌ %s request failed: %s", action_name, e)
            return False