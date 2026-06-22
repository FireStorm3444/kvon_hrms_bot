import sqlite3
import logging
from typing import Optional

class DatabaseManager:
    def __init__(self, db_path: str = "hrms_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the schema with enterprise-grade PRAGMAs."""
        with sqlite3.connect(self.db_path) as conn:
            # Enable Write-Ahead Logging for better concurrent read/writes
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            # Table 1: Idempotent Skip Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skipped_dates (
                    target_date TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table 2: Single-Row State Engine for Timesheets
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_timesheets (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    task_name TEXT NOT NULL,
                    task_details TEXT NOT NULL,
                    mentor_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logging.info("🗄️ Database schema verified.")

    # --- SKIP COMMAND LOGIC ---

    def add_skip_date(self, target_date: str) -> bool:
        """Upserts a date to skip. Format: YYYY-MM-DD"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO skipped_dates (target_date) VALUES (?)", 
                    (target_date,)
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error adding skip date: {e}")
                return False

    def is_date_skipped(self, current_date: str) -> bool:
        """Checks if the cron job should abort for the given date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM skipped_dates WHERE target_date = ?", 
                (current_date,)
            )
            return cursor.fetchone() is not None

    # --- TIMESHEET STATE LOGIC ---

    def save_pending_timesheet(self, task: str, details: str, mentor: str, start: str, end: str) -> bool:
        """Overwrites the single pending timesheet row."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO pending_timesheets 
                    (id, task_name, task_details, mentor_name, start_time, end_time, updated_at) 
                    VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (task, details, mentor, start, end))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error saving timesheet: {e}")
                return False

    def get_pending_timesheet(self) -> Optional[dict]:
        """Retrieves the pending timesheet to be injected into the API payload."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Returns dict-like objects
            cursor = conn.execute("SELECT * FROM pending_timesheets WHERE id = 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def clear_pending_timesheet(self) -> None:
        """Wipes the timesheet state after a successful check-out."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM pending_timesheets WHERE id = 1")
            conn.commit()