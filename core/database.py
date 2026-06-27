import sqlite3
import logging
from typing import Optional, List, Dict
from contextlib import contextmanager

class DatabaseManager:
    def __init__(self, db_path: str = "hrms_state.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Creates a database connection and strictly guarantees it closes after use."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            
            # Table 1: Idempotent Skip Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skipped_dates (
                    target_date TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table 2: Multi-Row Timesheet Engine
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

            # Table 3: Single-Row Scheduled Checkout Engine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_checkout (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    target_time TEXT NOT NULL
                )
            """)
            conn.commit()

    # --- SKIP COMMAND LOGIC ---
    def add_skip_date(self, target_date: str) -> bool:
        with self.get_connection() as conn:
            try:
                conn.execute("INSERT OR IGNORE INTO skipped_dates (target_date) VALUES (?)", (target_date,))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error adding skip date: {e}")
                return False

    def is_date_skipped(self, current_date: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM skipped_dates WHERE target_date = ?", (current_date,))
            return cursor.fetchone() is not None

    def clear_skip_dates(self) -> bool:
        with self.get_connection() as conn:
            try:
                conn.execute("DELETE FROM skipped_dates")
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error clearing skip dates: {e}")
                return False

    # --- TIMESHEET BATCH LOGIC ---
    def check_time_overlap(self, new_start: str, new_end: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 1 FROM pending_timesheets 
                WHERE target_date = date('now', '+5 hours', '+30 minutes')
                AND (? < end_time AND ? > start_time)
            """, (new_start, new_end))
            return cursor.fetchone() is not None

    def save_pending_timesheet(self, task: str, details: str, mentor: str, start: str, end: str) -> tuple[bool, str]:
        if self.check_time_overlap(start, end):
            logging.warning(f"Time overlap detected for {start}-{end}. Rejecting save.")
            return False, "Time overlap detected with an existing entry."

        with self.get_connection() as conn:
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
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM pending_timesheets 
                WHERE target_date = date('now', '+5 hours', '+30 minutes')
                ORDER BY start_time ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def clear_pending_timesheets(self) -> bool:
        with self.get_connection() as conn:
            try:
                conn.execute("DELETE FROM pending_timesheets WHERE target_date = date('now', '+5 hours', '+30 minutes')")
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error clearing timesheets: {e}")
                return False

    # --- SCHEDULED CHECKOUT LOGIC ---
    def set_scheduled_checkout(self, time_24h: str) -> bool:
        with self.get_connection() as conn:
            try:
                conn.execute("INSERT OR REPLACE INTO scheduled_checkout (id, target_time) VALUES (1, ?)", (time_24h,))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Database error saving schedule: {e}")
                return False

    def get_scheduled_checkout(self) -> str | None:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT target_time FROM scheduled_checkout WHERE id = 1")
            row = cursor.fetchone()
            return row[0] if row else None

    def clear_scheduled_checkout(self) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM scheduled_checkout WHERE id = 1")
            conn.commit()