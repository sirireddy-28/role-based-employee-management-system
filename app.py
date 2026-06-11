from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        db = get_db()
        n = db.execute("SELECT * FROM notifications WHERE user_id=? AND is_read=0 ORDER BY created_at DESC LIMIT 5", (session['user_id'],)).fetchall()
        c = db.execute("SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0", (session['user_id'],)).fetchone()['c']
        db.close()
        return dict(recent_notifications=n, unread_notifications_count=c)
    return dict(recent_notifications=[], unread_notifications_count=0)

# ── Decorators ──────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Access denied. Insufficient permissions.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Auth Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['email'] = user['email']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role = request.form.get('role', 'employee')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('auth/signup.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/signup.html')

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username=? OR email=?", (username, email)).fetchone()
        if existing:
            db.close()
            flash('Username or email already exists.', 'danger')
            return render_template('auth/signup.html')

        hashed = generate_password_hash(password)
        try:
            cursor = db.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                (username, email, hashed, role)
            )
            user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO employees (user_id, name, email) VALUES (?, ?, ?)",
                (user_id, username, email)
            )
            db.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error creating account: {str(e)}', 'danger')
        finally:
            db.close()

    return render_template('auth/signup.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ── Dashboard Router ─────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'hr':
        return redirect(url_for('hr_dashboard'))
    else:
        return redirect(url_for('employee_dashboard'))


# ── Admin Routes ─────────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    db = get_db()
    stats = {
        'total_employees': db.execute("SELECT COUNT(*) as c FROM employees").fetchone()['c'],
        'total_users': db.execute("SELECT COUNT(*) as c FROM users").fetchone()['c'],
        'pending_leaves': db.execute("SELECT COUNT(*) as c FROM leaves WHERE status='pending'").fetchone()['c'],
        'departments': db.execute("SELECT COUNT(DISTINCT department) as c FROM employees WHERE department IS NOT NULL").fetchone()['c'],
    }
    recent_employees = db.execute(
        "SELECT e.*, u.role FROM employees e LEFT JOIN users u ON e.user_id=u.id ORDER BY e.id DESC LIMIT 5"
    ).fetchall()
    db.close()
    return render_template('admin/dashboard.html', stats=stats, recent_employees=recent_employees)


@app.route('/admin/employees')
@login_required
@role_required('admin')
def admin_employees():
    db = get_db()
    employees = db.execute(
        "SELECT e.*, u.username, u.role FROM employees e LEFT JOIN users u ON e.user_id=u.id ORDER BY e.id DESC"
    ).fetchall()
    db.close()
    return render_template('admin/employees.html', employees=employees)


@app.route('/admin/employees/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_add_employee():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        joining_date = request.form.get('joining_date', '')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'employee')

        db = get_db()
        try:
            hashed = generate_password_hash(password)
            cursor = db.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                (username, email, hashed, role)
            )
            user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO employees (user_id, name, email, phone, department, designation, joining_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, email, phone, department, designation, joining_date)
            )
            db.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('admin_employees'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()

    return render_template('admin/add_employee.html')


@app.route('/admin/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_employee(emp_id):
    db = get_db()
    employee = db.execute(
        "SELECT e.*, u.username, u.role FROM employees e LEFT JOIN users u ON e.user_id=u.id WHERE e.id=?",
        (emp_id,)
    ).fetchone()
    if not employee:
        db.close()
        flash('Employee not found.', 'danger')
        return redirect(url_for('admin_employees'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        joining_date = request.form.get('joining_date', '')
        status = request.form.get('status', 'active')
        role = request.form.get('role', 'employee')
        try:
            db.execute(
                "UPDATE employees SET name=?, phone=?, department=?, designation=?, joining_date=?, status=? WHERE id=?",
                (name, phone, department, designation, joining_date, status, emp_id)
            )
            if employee['user_id']:
                db.execute("UPDATE users SET role=? WHERE id=?", (role, employee['user_id']))
            db.commit()
            flash('Employee updated successfully!', 'success')
            return redirect(url_for('admin_employees'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()
        return redirect(url_for('admin_employees'))

    db.close()
    return render_template('admin/edit_employee.html', employee=employee)


@app.route('/admin/employees/delete/<int:emp_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_employee(emp_id):
    db = get_db()
    emp = db.execute("SELECT user_id FROM employees WHERE id=?", (emp_id,)).fetchone()
    try:
        db.execute("DELETE FROM salaries WHERE employee_id=?", (emp_id,))
        db.execute("DELETE FROM leaves WHERE employee_id=?", (emp_id,))
        db.execute("DELETE FROM employees WHERE id=?", (emp_id,))
        if emp and emp['user_id']:
            db.execute("DELETE FROM users WHERE id=?", (emp['user_id'],))
        db.commit()
        flash('Employee deleted.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('admin_employees'))


@app.route('/admin/salary')
@login_required
@role_required('admin')
def admin_salary():
    db = get_db()
    salaries = db.execute(
        "SELECT s.*, e.name, e.department FROM salaries s JOIN employees e ON s.employee_id=e.id ORDER BY s.id DESC"
    ).fetchall()
    employees = db.execute("SELECT id, name FROM employees").fetchall()
    db.close()
    return render_template('admin/salary.html', salaries=salaries, employees=employees)


@app.route('/admin/salary/add', methods=['POST'])
@login_required
@role_required('admin')
def admin_add_salary():
    db = get_db()
    try:
        emp_id = int(request.form.get('employee_id'))
        month = request.form.get('month')
        year = int(request.form.get('year'))
        
        existing = db.execute("SELECT id FROM salaries WHERE employee_id=? AND month=? AND year=?", (emp_id, month, year)).fetchone()
        if existing:
            db.close()
            flash(f'Salary record for {month} {year} already exists for this employee.', 'warning')
            return redirect(url_for('admin_salary'))

        basic = float(request.form.get('basic_salary', 0))
        allowances = float(request.form.get('allowances', 0))
        deductions = float(request.form.get('deductions', 0))
        net = basic + allowances - deductions
        paid_on = request.form.get('paid_on')
        status = request.form.get('status', 'pending')
        db.execute(
            "INSERT INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (emp_id, month, year, basic, allowances, deductions, net, paid_on, status)
        )
        db.commit()
        flash('Salary record added.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('admin_salary'))


@app.route('/admin/salary/edit/<int:sal_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_salary(sal_id):
    db = get_db()
    salary = db.execute(
        "SELECT s.*, e.name FROM salaries s JOIN employees e ON s.employee_id=e.id WHERE s.id=?",
        (sal_id,)
    ).fetchone()
    
    if not salary:
        db.close()
        flash('Salary record not found.', 'danger')
        return redirect(url_for('admin_salary'))

    if request.method == 'POST':
        basic = float(request.form.get('basic_salary', 0))
        allowances = float(request.form.get('allowances', 0))
        deductions = float(request.form.get('deductions', 0))
        net = basic + allowances - deductions
        paid_on = request.form.get('paid_on')
        status = request.form.get('status', 'pending')
        
        try:
            db.execute(
                "UPDATE salaries SET basic_salary=?, allowances=?, deductions=?, net_salary=?, paid_on=?, status=? WHERE id=?",
                (basic, allowances, deductions, net, paid_on, status, sal_id)
            )
            db.commit()
            flash('Salary record updated.', 'success')
            return redirect(url_for('admin_salary'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()
            
    db.close()
    return render_template('admin/edit_salary.html', salary=salary)


@app.route('/admin/leaves')
@login_required
@role_required('admin')
def admin_leaves():
    db = get_db()
    leaves = db.execute(
        "SELECT l.*, e.name, e.department FROM leaves l JOIN employees e ON l.employee_id=e.id ORDER BY l.applied_at DESC"
    ).fetchall()
    db.close()
    return render_template('admin/leaves.html', leaves=leaves)


# ── HR Routes ────────────────────────────────────────────────────────────────

@app.route('/hr/dashboard')
@login_required
@role_required('hr', 'admin')
def hr_dashboard():
    db = get_db()
    stats = {
        'total_employees': db.execute("SELECT COUNT(*) as c FROM employees WHERE status='active'").fetchone()['c'],
        'pending_leaves': db.execute("SELECT COUNT(*) as c FROM leaves WHERE status='pending'").fetchone()['c'],
        'approved_leaves': db.execute("SELECT COUNT(*) as c FROM leaves WHERE status='approved'").fetchone()['c'],
    }
    recent_leaves = db.execute(
        "SELECT l.*, e.name FROM leaves l JOIN employees e ON l.employee_id=e.id WHERE l.status='pending' ORDER BY l.applied_at DESC LIMIT 5"
    ).fetchall()
    db.close()
    return render_template('hr/dashboard.html', stats=stats, recent_leaves=recent_leaves)


@app.route('/hr/employees')
@login_required
@role_required('hr', 'admin')
def hr_employees():
    db = get_db()
    employees = db.execute(
        "SELECT e.*, u.role FROM employees e LEFT JOIN users u ON e.user_id=u.id ORDER BY e.name"
    ).fetchall()
    db.close()
    return render_template('hr/employees.html', employees=employees)


@app.route('/hr/employees/add', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_add_employee():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        joining_date = request.form.get('joining_date', '')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'employee')
        
        if role == 'admin' and session.get('role') != 'admin':
            role = 'hr'

        db = get_db()
        try:
            hashed = generate_password_hash(password)
            cursor = db.execute(
                "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
                (username, email, hashed, role)
            )
            user_id = cursor.lastrowid
            db.execute(
                "INSERT INTO employees (user_id, name, email, phone, department, designation, joining_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, email, phone, department, designation, joining_date)
            )
            db.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('hr_employees'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()

    return render_template('hr/add_employee.html')


@app.route('/hr/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_edit_employee(emp_id):
    db = get_db()
    employee = db.execute("SELECT * FROM employees WHERE id=?", (emp_id,)).fetchone()
    if not employee:
        db.close()
        flash('Employee not found.', 'danger')
        return redirect(url_for('hr_employees'))

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        try:
            db.execute(
                "UPDATE employees SET phone=?, department=?, designation=? WHERE id=?",
                (phone, department, designation, emp_id)
            )
            db.commit()
            flash('Employee info updated.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()
        return redirect(url_for('hr_employees'))

    db.close()
    return render_template('hr/edit_employee.html', employee=employee)


@app.route('/hr/leaves')
@login_required
@role_required('hr', 'admin')
def hr_leaves():
    db = get_db()
    leaves = db.execute(
        "SELECT l.*, e.name, e.department FROM leaves l JOIN employees e ON l.employee_id=e.id ORDER BY l.applied_at DESC"
    ).fetchall()
    db.close()
    return render_template('hr/leaves.html', leaves=leaves)


@app.route('/hr/leaves/update/<int:leave_id>', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def hr_update_leave(leave_id):
    status = request.form.get('status')
    db = get_db()
    try:
        db.execute(
            "UPDATE leaves SET status=?, reviewed_by=? WHERE id=?",
            (status, session['user_id'], leave_id)
        )
        db.commit()
        
        # Notify employee
        emp = db.execute("SELECT u.id, u.email FROM leaves l JOIN employees e ON l.employee_id=e.id JOIN users u ON e.user_id=u.id WHERE l.id=?", (leave_id,)).fetchone()
        if emp:
            from email_service import send_email
            from notification_service import add_notification
            send_email(emp['email'], f"Leave {status.capitalize()}", f"Your leave request has been marked as {status}.")
            add_notification(emp['id'], f"Your leave request was {status}.", "info")

        flash(f'Leave {status}.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('hr_leaves'))


@app.route('/hr/salary')
@login_required
@role_required('hr', 'admin')
def hr_salary():
    db = get_db()
    salaries = db.execute(
        "SELECT s.*, e.name, e.department FROM salaries s JOIN employees e ON s.employee_id=e.id ORDER BY s.year DESC, s.id DESC"
    ).fetchall()
    employees = db.execute("SELECT id, name FROM employees").fetchall()
    db.close()
    return render_template('hr/salary.html', salaries=salaries, employees=employees)


@app.route('/hr/salary/add', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def hr_add_salary():
    db = get_db()
    try:
        emp_id = int(request.form.get('employee_id'))
        month = request.form.get('month')
        year = int(request.form.get('year'))
        
        existing = db.execute("SELECT id FROM salaries WHERE employee_id=? AND month=? AND year=?", (emp_id, month, year)).fetchone()
        if existing:
            db.close()
            flash(f'Salary record for {month} {year} already exists for this employee.', 'warning')
            return redirect(url_for('hr_salary'))

        basic = float(request.form.get('basic_salary', 0))
        allowances = float(request.form.get('allowances', 0))
        deductions = float(request.form.get('deductions', 0))
        net = basic + allowances - deductions
        paid_on = request.form.get('paid_on')
        status = request.form.get('status', 'pending')
        db.execute(
            "INSERT INTO salaries (employee_id, month, year, basic_salary, allowances, deductions, net_salary, paid_on, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (emp_id, month, year, basic, allowances, deductions, net, paid_on, status)
        )
        db.commit()
        flash('Salary record added.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('hr_salary'))


@app.route('/hr/salary/edit/<int:sal_id>', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_edit_salary(sal_id):
    db = get_db()
    salary = db.execute(
        "SELECT s.*, e.name FROM salaries s JOIN employees e ON s.employee_id=e.id WHERE s.id=?",
        (sal_id,)
    ).fetchone()
    
    if not salary:
        db.close()
        flash('Salary record not found.', 'danger')
        return redirect(url_for('hr_salary'))

    if request.method == 'POST':
        basic = float(request.form.get('basic_salary', 0))
        allowances = float(request.form.get('allowances', 0))
        deductions = float(request.form.get('deductions', 0))
        net = basic + allowances - deductions
        paid_on = request.form.get('paid_on')
        status = request.form.get('status', 'pending')
        
        try:
            db.execute(
                "UPDATE salaries SET basic_salary=?, allowances=?, deductions=?, net_salary=?, paid_on=?, status=? WHERE id=?",
                (basic, allowances, deductions, net, paid_on, status, sal_id)
            )
            db.commit()
            flash('Salary record updated.', 'success')
            return redirect(url_for('hr_salary'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            db.close()
            
    db.close()
    return render_template('hr/edit_salary.html', salary=salary)


# ── Employee Routes ──────────────────────────────────────────────────────────

@app.route('/employee/dashboard')
@login_required
@role_required('employee', 'hr', 'admin')
def employee_dashboard():
    db = get_db()
    emp = db.execute(
        "SELECT * FROM employees WHERE user_id=?", (session['user_id'],)
    ).fetchone()
    if not emp:
        db.close()
        flash('Employee profile not found.', 'warning')
        return redirect(url_for('login'))
    leave_count = db.execute(
        "SELECT COUNT(*) as c FROM leaves WHERE employee_id=? AND status='pending'", (emp['id'],)
    ).fetchone()['c']
    total_leaves = db.execute("SELECT COUNT(*) as c FROM leaves WHERE employee_id=?", (emp['id'],)).fetchone()['c']
    recent_salary = db.execute(
        "SELECT * FROM salaries WHERE employee_id=? ORDER BY year DESC, id DESC LIMIT 1", (emp['id'],)
    ).fetchone()
    
    # HR Extensions Additions
    ctc = db.execute("SELECT * FROM ctc WHERE employee_id=?", (emp['id'],)).fetchone()
    leave_balance_info = db.execute("SELECT * FROM leave_balances WHERE employee_id=?", (emp['id'],)).fetchone()
    
    # Initialize if missing
    if not leave_balance_info:
        db.execute("INSERT OR IGNORE INTO leave_balances (employee_id, total_leaves, leaves_taken, leave_balance) VALUES (?, 20, 0, 20)", (emp['id'],))
        db.commit()
        leave_balance_info = db.execute("SELECT * FROM leave_balances WHERE employee_id=?", (emp['id'],)).fetchone()
        
    holidays = db.execute("SELECT * FROM holidays ORDER BY date ASC LIMIT 3").fetchall()
    
    db.close()
    return render_template('employee/dashboard.html', emp=emp, leave_count=leave_count,
                           total_leaves=total_leaves, recent_salary=recent_salary,
                           ctc=ctc, leave_balance_info=leave_balance_info, holidays=holidays)


@app.route('/employee/profile')
@login_required
def employee_profile():
    db = get_db()
    emp = db.execute(
        "SELECT e.*, u.username, u.email as user_email, u.role FROM employees e "
        "LEFT JOIN users u ON e.user_id=u.id WHERE e.user_id=?",
        (session['user_id'],)
    ).fetchone()
    db.close()
    if not emp:
        flash('Profile not found.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('employee/profile.html', emp=emp)


@app.route('/employee/leave/apply', methods=['GET', 'POST'])
@login_required
@role_required('employee', 'hr', 'admin')
def employee_apply_leave():
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        flash('Profile not found.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason', '').strip()
        if not start_date or not end_date or not reason:
            flash('All fields are required.', 'danger')
        else:
            try:
                db.execute(
                    "INSERT INTO leaves (employee_id, start_date, end_date, reason) VALUES (?, ?, ?, ?)",
                    (emp['id'], start_date, end_date, reason)
                )
                db.commit()
                
                # Notify HR
                from email_service import send_email
                from notification_service import add_notification
                hrs = db.execute("SELECT id, email FROM users WHERE role='hr'").fetchall()
                for hr in hrs:
                    if hr['email']:
                        send_email(hr['email'], "New Leave Application", f"Employee {emp['name']} applied for leave from {start_date} to {end_date}.")
                    add_notification(hr['id'], f"New leave applied by {emp['name']}", "info")
                flash('Leave application submitted successfully!', 'success')
                return redirect(url_for('employee_leave_status'))
            except Exception as e:
                flash(f'Error: {str(e)}', 'danger')

    db.close()
    return render_template('employee/leave_apply.html', emp=emp)


@app.route('/employee/leave/status')
@login_required
def employee_leave_status():
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        flash('Profile not found.', 'danger')
        return redirect(url_for('dashboard'))
    leaves = db.execute(
        "SELECT * FROM leaves WHERE employee_id=? ORDER BY applied_at DESC", (emp['id'],)
    ).fetchall()
    db.close()
    return render_template('employee/leave_status.html', leaves=leaves, emp=emp)


@app.route('/employee/salary')
@login_required
def employee_salary():
    db = get_db()
    emp = db.execute("SELECT * FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        flash('Profile not found.', 'danger')
        return redirect(url_for('dashboard'))
    salaries = db.execute(
        "SELECT * FROM salaries WHERE employee_id=? ORDER BY year DESC, id DESC", (emp['id'],)
    ).fetchall()
    db.close()
    return render_template('employee/salary.html', salaries=salaries, emp=emp)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route('/api/stats')
@login_required
@role_required('admin')
def api_stats():
    db = get_db()
    data = {
        'employees': db.execute("SELECT COUNT(*) as c FROM employees").fetchone()['c'],
        'pending_leaves': db.execute("SELECT COUNT(*) as c FROM leaves WHERE status='pending'").fetchone()['c'],
        'approved_leaves': db.execute("SELECT COUNT(*) as c FROM leaves WHERE status='approved'").fetchone()['c'],
    }
    db.close()
    return jsonify(data)


from extra_routes import extra_bp
app.register_blueprint(extra_bp)

from hr_extensions import hr_extensions_bp
app.register_blueprint(hr_extensions_bp)

from ai_service import ai_service_bp
app.register_blueprint(ai_service_bp)

from chatbot_service import chatbot_service_bp
app.register_blueprint(chatbot_service_bp)

from skill_service import skill_service_bp
app.register_blueprint(skill_service_bp)

if __name__ == '__main__':
    init_db()
    from skill_service import init_skill_db
    init_skill_db()
    app.run(debug=True, port=5001)
