import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'employee_mgmt.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            department TEXT,
            designation TEXT,
            joining_date DATE,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            basic_salary REAL NOT NULL,
            allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            net_salary REAL NOT NULL,
            paid_on DATE,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date DATE NOT NULL,
            check_in_time TIME NOT NULL,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date DATE NOT NULL,
            time TIME NOT NULL,
            description TEXT,
            google_meet_link TEXT,
            created_by INTEGER NOT NULL,
            FOREIGN KEY (created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER NOT NULL,
            assigned_by INTEGER NOT NULL,
            deadline DATE,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (assigned_to) REFERENCES employees(id),
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            feedback TEXT,
            review_date DATE DEFAULT CURRENT_DATE,
            reviewer_id INTEGER NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    # Seed default admin
    try:
        hashed = generate_password_hash('admin123')
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            ('admin', 'admin@company.com', hashed, 'admin')
        )
        cursor.execute(
            "INSERT OR IGNORE INTO employees (user_id, name, email, department, designation) VALUES (?, ?, ?, ?, ?)",
            (1, 'System Admin', 'admin@company.com', 'Administration', 'Administrator')
        )

        # Seed HR user
        hr_hash = generate_password_hash('hr123')
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            ('hrmanager', 'hr@company.com', hr_hash, 'hr')
        )
        cursor.execute(
            "INSERT OR IGNORE INTO employees (user_id, name, email, department, designation) VALUES (?, ?, ?, ?, ?)",
            (2, 'HR Manager', 'hr@company.com', 'Human Resources', 'HR Manager')
        )

        # Seed Employee user
        emp_hash = generate_password_hash('emp123')
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            ('johndoe', 'john@company.com', emp_hash, 'employee')
        )
        cursor.execute(
            "INSERT OR IGNORE INTO employees (user_id, name, email, department, designation, joining_date) VALUES (?, ?, ?, ?, ?, ?)",
            (3, 'John Doe', 'john@company.com', 'Engineering', 'Software Engineer', '2023-01-15')
        )

        # Seed salary
        cursor.execute(
            "INSERT OR IGNORE INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (3, 'March', 2026, 60000, 10000, 5000, 65000, '2026-03-31', 'paid')
        )
        cursor.execute(
            "INSERT OR IGNORE INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (3, 'February', 2026, 60000, 10000, 5000, 65000, '2026-02-28', 'paid')
        )

    except Exception as e:
        print(f"Seed error (may already exist): {e}")

    conn.commit()
    conn.close()
