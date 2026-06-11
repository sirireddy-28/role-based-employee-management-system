import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'employee_mgmt.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_hr_extensions_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS ctc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL UNIQUE,
            base_salary REAL NOT NULL DEFAULT 0,
            bonus REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            total_ctc REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS leave_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL UNIQUE,
            total_leaves INTEGER NOT NULL DEFAULT 20,
            leaves_taken INTEGER NOT NULL DEFAULT 0,
            leave_balance INTEGER NOT NULL DEFAULT 20,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date DATE NOT NULL,
            clock_in TIME,
            clock_out TIME,
            working_hours REAL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS compensations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            comp_type TEXT NOT NULL,
            amount REAL NOT NULL,
            date DATE NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_name TEXT NOT NULL,
            date DATE NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS helpdesk_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );
    """)

    conn.commit()
    conn.close()
    print("HR Extensions Database Initialized.")

if __name__ == '__main__':
    init_hr_extensions_db()
