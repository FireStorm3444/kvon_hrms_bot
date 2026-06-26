import sqlite3
import logging
from typing import Optional, List, Dict

class DatabaseManager:
    def __init__(self, db_path: str = "hrms_state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the schema with enterprise-grade PRAGMAs and IST timezone offsets."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            # Table 1: Idempotent Skip Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skipped_dates (
                    target_date TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table 2: Multi-Row Timesheet Engine (Upgraded)
            # Notice the IST timezone shift for target_date
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_timesheets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    task_details TEXT NOT NULL,
                    mentor_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    target_date DATE DEFAULT (date('now', '+5 hours', '+30 minutes')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # --- SKIP COMMAND LOGIC ---

    def add_skip_date(self, target_date: str) -> bool:
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM skipped_dates WHERE target_date = ?", 
                (current_date,)
            )
            return cursor.fetchone() is not None

    def clear_skip_dates(self) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("DELETE FROM skipped_dates")
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error clearing skip dates: {e}")
                return False

    # --- TIMESHEET BATCH LOGIC (PHASE 1 UPGRADES) ---

    def check_time_overlap(self, new_start: str, new_end: str) -> bool:
        """
        Calculates if the proposed times intersect with any existing timesheets for today.
        Overlap formula: (NewStart < ExistingEnd) AND (NewEnd > ExistingStart)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 1 FROM pending_timesheets 
                WHERE target_date = date('now', '+5 hours', '+30 minutes')
                AND (? < end_time AND ? > start_time)
            """, (new_start, new_end))
            return cursor.fetchone() is not None

    def save_pending_timesheet(self, task: str, details: str, mentor: str, start: str, end: str) -> tuple[bool, str]:
        """Appends a new timesheet row, aborting if overlaps are detected."""
        if self.check_time_overlap(start, end):
            logging.warning(f"Time overlap detected for {start}-{end}. Rejecting save.")
            return False, "Time overlap detected with an existing entry."

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO pending_timesheets 
                    (task_name, task_details, mentor_name, start_time, end_time) 
                    VALUES (?, ?, ?, ?, ?)
                """, (task, details, mentor, start, end))
                conn.commit()
                return True, "Success"
            except sqlite3.Error as e:
                logging.error(f"Database error saving timesheet: {e}")
                return False, "Database insertion failed."

    def get_pending_timesheets(self) -> List[Dict]:
        """Retrieves all pending timesheets for today, ordered chronologically by start time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM pending_timesheets 
                WHERE target_date = date('now', '+5 hours', '+30 minutes')
                ORDER BY start_time ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def clear_pending_timesheets(self) -> bool:
        """Wipes today's timesheet state after a successful bulk upload or manual reset."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("DELETE FROM pending_timesheets WHERE target_date = date('now', '+5 hours', '+30 minutes')")
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error clearing timesheets: {e}")
                return False