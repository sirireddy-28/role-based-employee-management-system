import sqlite3
import os
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'employee_mgmt.db')

def seed_real_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Define realistic employee data
    employees_data = [
        {"name": "Aarav Patel", "username": "aarav", "email": "aarav.patel@company.com", "phone": "+91 98765 11111", "dept": "Engineering", "title": "Senior Developer", "role": "employee", "join": "2021-06-15"},
        {"name": "Priya Sharma", "username": "priya", "email": "priya.sharma@company.com", "phone": "+91 98765 22222", "dept": "Marketing", "title": "Marketing Lead", "role": "employee", "join": "2022-01-10"},
        {"name": "Vikram Singh", "username": "vikram", "email": "vikram.singh@company.com", "phone": "+91 98765 33333", "dept": "Sales", "title": "Sales Executive", "role": "employee", "join": "2023-03-20"},
        {"name": "Ananya Desai", "username": "ananya", "email": "ananya.desai@company.com", "phone": "+91 98765 44444", "dept": "Finance", "title": "Financial Analyst", "role": "employee", "join": "2020-11-05"},
        {"name": "Rohan Gupta", "username": "rohan", "email": "rohan.gupta@company.com", "phone": "+91 98765 55555", "dept": "Operations", "title": "Operations Manager", "role": "employee", "join": "2019-08-12"},
        {"name": "Sneha Iyer", "username": "sneha", "email": "sneha.iyer@company.com", "phone": "+91 98765 66666", "dept": "Engineering", "title": "UI/UX Designer", "role": "employee", "join": "2022-07-25"},
        {"name": "Karan Mehra", "username": "karan", "email": "karan.mehra@company.com", "phone": "+91 98765 77777", "dept": "IT Support", "title": "System Administrator", "role": "employee", "join": "2021-02-18"},
        {"name": "Meera Reddy", "username": "meera", "email": "meera.reddy@company.com", "phone": "+91 98765 88888", "dept": "Human Resources", "title": "HR Executive", "role": "hr", "join": "2023-09-01"},
    ]

    password_hash = generate_password_hash("password123")
    
    months = ['January', 'February', 'March']
    year = 2026

    for ed in employees_data:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username=?", (ed["username"],))
        if cursor.fetchone():
            continue # Skip if exists

        # Insert user
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            (ed["username"], ed["email"], password_hash, ed["role"])
        )
        user_id = cursor.lastrowid

        # Insert employee
        cursor.execute(
            "INSERT INTO employees (user_id, name, email, phone, department, designation, joining_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, ed["name"], ed["email"], ed["phone"], ed["dept"], ed["title"], ed["join"], "active")
        )
        emp_id = cursor.lastrowid

        # Insert salaries for Jan, Feb, Mar 2026
        base_salary = random.randint(40000, 120000)
        allowances = int(base_salary * 0.15)
        deductions = int(base_salary * 0.05)
        net_salary = base_salary + allowances - deductions

        for m_idx, m in enumerate(months):
            # To make it realistic, maybe vary slightly or keep same
            paid_on_date = f"2026-{m_idx+1:02d}-28"
            cursor.execute(
                "INSERT INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (emp_id, m, year, base_salary, allowances, deductions, net_salary, paid_on_date, "paid")
            )

        # Insert Random Leaves
        num_leaves = random.randint(0, 3)
        reasons = ["Family function", "Medical emergency", "Vacation check", "Personal work", "Fever and cold"]
        statuses = ["approved", "rejected", "pending"]
        
        for _ in range(num_leaves):
            # random past or future date in 2026
            start_date_obj = datetime(2026, random.randint(1, 4), random.randint(1, 28))
            duration = random.randint(1, 4)
            end_date_obj = start_date_obj + timedelta(days=duration)
            
            start_date = start_date_obj.strftime('%Y-%m-%d')
            end_date = end_date_obj.strftime('%Y-%m-%d')
            reason = random.choice(reasons)
            status = random.choice(statuses)
            
            cursor.execute(
                "INSERT INTO leaves (employee_id, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?)",
                (emp_id, start_date, end_date, reason, status)
            )

    # Let's also add some dummy leaves/salaries to existing demo users if they have none
    # "johndoe" employee (id=3 based on init)
    cursor.execute("SELECT id FROM employees WHERE email='john@company.com'")
    demo_emp = cursor.fetchone()
    if demo_emp:
        demo_id = demo_emp[0]
        # Check leaves
        cursor.execute("SELECT count(*) FROM leaves WHERE employee_id=?", (demo_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO leaves (employee_id, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?)",
                (demo_id, '2026-04-10', '2026-04-12', 'Attending cousin wedding in Mumbai', 'pending'))
            cursor.execute("INSERT INTO leaves (employee_id, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?)",
                (demo_id, '2026-02-05', '2026-02-06', 'High fever, doctor recommended rest', 'approved'))

    # And for 'siri' if exists (wait I don't know the user ID exactly, but I can fetch by email if I knew it)
    cursor.execute("SELECT id FROM employees WHERE email='sirichandanareddy2805@gmail.com'")
    siri_emp = cursor.fetchone()
    if siri_emp:
        siri_id = siri_emp[0]
        # Update her details if they are blank
        cursor.execute("UPDATE employees SET phone='+91 99999 88888', department='Human Resources', designation='Sr. HR Manager', joining_date='2025-01-10' WHERE id=? AND department IS NULL", (siri_id,))
        
        # Add a salary record if none
        cursor.execute("SELECT count(*) FROM salaries WHERE employee_id=?", (siri_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (siri_id, 'March', 2026, 85000, 15000, 5000, 95000, '2026-03-31', 'paid'))

    conn.commit()
    conn.close()
    print("Database seeded with realistic data successfully!")

if __name__ == '__main__':
    seed_real_data()
