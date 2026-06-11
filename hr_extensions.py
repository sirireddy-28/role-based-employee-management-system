from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from datetime import datetime, date
from hr_extensions_db import get_db

hr_extensions_bp = Blueprint('hr_extensions', __name__)

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

def init_employee_balances(emp_id):
    db = get_db()
    
    # Initialize CTC if not present
    ctc = db.execute("SELECT id FROM ctc WHERE employee_id=?", (emp_id,)).fetchone()
    if not ctc:
        db.execute("INSERT INTO ctc (employee_id) VALUES (?)", (emp_id,))
    
    # Initialize leave balance if not present
    lb = db.execute("SELECT id FROM leave_balances WHERE employee_id=?", (emp_id,)).fetchone()
    if not lb:
        db.execute("INSERT INTO leave_balances (employee_id, total_leaves, leaves_taken, leave_balance) VALUES (?, 20, 0, 20)", (emp_id,))
    
    db.commit()
    db.close()

# ── 1. CTC (Cost to Company) ──────────────────────────────────────────────────
@hr_extensions_bp.route('/hr/ctc', methods=['GET'])
@login_required
@role_required('hr', 'admin')
def admin_ctc():
    db = get_db()
    
    # Initialize CTC records for any employee that doesn't have one
    db.execute("INSERT OR IGNORE INTO ctc (employee_id) SELECT id FROM employees")
    db.commit()

    records = db.execute(
        "SELECT c.*, e.name, e.department FROM ctc c "
        "JOIN employees e ON c.employee_id=e.id "
        "ORDER BY e.name"
    ).fetchall()
    employees = db.execute("SELECT id, name FROM employees").fetchall()
    db.close()
    return render_template('hr_extensions/admin_ctc.html', records=records, employees=employees)

@hr_extensions_bp.route('/hr/ctc/update', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def admin_ctc_update():
    emp_id = request.form.get('employee_id')
    base = float(request.form.get('base_salary', 0))
    bonus = float(request.form.get('bonus', 0))
    deductions = float(request.form.get('deductions', 0))
    total = base + bonus - deductions
    
    db = get_db()
    existing = db.execute("SELECT id FROM ctc WHERE employee_id=?", (emp_id,)).fetchone()
    if existing:
        db.execute("UPDATE ctc SET base_salary=?, bonus=?, deductions=?, total_ctc=? WHERE employee_id=?",
                   (base, bonus, deductions, total, emp_id))
    else:
        db.execute("INSERT INTO ctc (employee_id, base_salary, bonus, deductions, total_ctc) VALUES (?,?,?,?,?)",
                   (emp_id, base, bonus, deductions, total))
    db.commit()
    db.close()
    flash('CTC updated explicitly.', 'success')
    return redirect(url_for('hr_extensions.admin_ctc'))

# ── 2. Leave Enhancements ─────────────────────────────────────────────────────
@hr_extensions_bp.route('/hr/leave_balances', methods=['GET'])
@login_required
@role_required('hr', 'admin')
def admin_leave_balances():
    db = get_db()
    
    # Initialize leave balances for any employee that doesn't have one (default to 20 leaves)
    db.execute(
        "INSERT OR IGNORE INTO leave_balances (employee_id, total_leaves, leaves_taken, leave_balance) "
        "SELECT id, 20, 0, 20 FROM employees"
    )
    db.commit()

    records = db.execute(
        "SELECT l.*, e.name FROM leave_balances l "
        "JOIN employees e ON l.employee_id=e.id "
        "ORDER BY e.name"
    ).fetchall()
    db.close()
    return render_template('hr_extensions/leave_balances.html', records=records)

@hr_extensions_bp.route('/hr/leave_balances/update/<int:lb_id>', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def admin_leave_balances_update(lb_id):
    total = int(request.form.get('total_leaves', 0))
    db = get_db()
    lb = db.execute("SELECT * FROM leave_balances WHERE id=?", (lb_id,)).fetchone()
    if lb:
        new_balance = total - lb['leaves_taken']
        db.execute("UPDATE leave_balances SET total_leaves=?, leave_balance=? WHERE id=?", (total, new_balance, lb_id))
        db.commit()
        flash('Leave balance updated.', 'success')
    db.close()
    return redirect(url_for('hr_extensions.admin_leave_balances'))

# ── 3. Attendance ─────────────────────────────────────────────────────────────
@hr_extensions_bp.route('/attendance/clock', methods=['GET', 'POST'])
@login_required
@role_required('employee')
def employee_clock():
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        return redirect(url_for('dashboard'))
    
    today = date.today().isoformat()
    log = db.execute("SELECT * FROM attendance_logs WHERE employee_id=? AND date=?", (emp['id'], today)).fetchone()

    if request.method == 'POST':
        action = request.form.get('action')
        now_time = datetime.now().strftime("%H:%M:%S")

        if action == 'clock_in':
            if not log:
                db.execute("INSERT INTO attendance_logs (employee_id, date, clock_in) VALUES (?, ?, ?)", (emp['id'], today, now_time))
                flash('Clocked In successfully.', 'success')
                
        elif action == 'clock_out':
            if log and not log['clock_out']:
                # calculate working hours based on stored strftime "%H:%M:%S"
                fmt = "%H:%M:%S"
                tdelta = datetime.strptime(now_time, fmt) - datetime.strptime(log['clock_in'], fmt)
                working_hours = round(tdelta.total_seconds() / 3600.0, 2)
                
                db.execute("UPDATE attendance_logs SET clock_out=?, working_hours=? WHERE id=?", (now_time, working_hours, log['id']))
                flash(f'Clocked Out! Working Hours: {working_hours} hours.', 'success')
        
        db.commit()
        db.close()
        return redirect(url_for('hr_extensions.employee_clock'))

    # Refresh log for template
    log = db.execute("SELECT * FROM attendance_logs WHERE employee_id=? AND date=?", (emp['id'], today)).fetchone()
    db.close()
    return render_template('hr_extensions/employee_clock.html', log=log)

@hr_extensions_bp.route('/hr/attendance_logs', methods=['GET'])
@login_required
@role_required('hr', 'admin')
def admin_attendance_logs():
    db = get_db()
    logs = db.execute(
        "SELECT a.*, e.name FROM attendance_logs a "
        "JOIN employees e ON a.employee_id=e.id "
        "ORDER BY a.date DESC, a.id DESC"
    ).fetchall()
    db.close()
    return render_template('hr_extensions/attendance_logs.html', logs=logs)

# ── 4. Compensations ──────────────────────────────────────────────────────────
@hr_extensions_bp.route('/hr/compensations', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'hr')
def admin_compensations():
    db = get_db()
    if request.method == 'POST':
        emp_id = request.form.get('employee_id')
        comp_type = request.form.get('comp_type')
        amount = request.form.get('amount')
        date_earned = request.form.get('date')
        reason = request.form.get('reason')
        
        db.execute("INSERT INTO compensations (employee_id, comp_type, amount, date, reason) VALUES (?, ?, ?, ?, ?)",
                   (emp_id, comp_type, amount, date_earned, reason))
        db.commit()
        flash('Compensation logged successfully.', 'success')
        return redirect(url_for('hr_extensions.admin_compensations'))
        
    records = db.execute(
        "SELECT c.*, e.name FROM compensations c "
        "JOIN employees e ON c.employee_id=e.id "
        "ORDER BY c.date DESC"
    ).fetchall()
    employees = db.execute("SELECT id, name FROM employees").fetchall()
    db.close()
    return render_template('hr_extensions/compensations.html', records=records, employees=employees)

# ── 5. Holidays ───────────────────────────────────────────────────────────────
@hr_extensions_bp.route('/holidays', methods=['GET'])
@login_required
def view_holidays():
    db = get_db()
    holidays = db.execute("SELECT * FROM holidays ORDER BY date ASC").fetchall()
    db.close()
    return render_template('hr_extensions/holidays.html', holidays=holidays, role=session.get('role'))

@hr_extensions_bp.route('/hr/holidays/add', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def add_holiday():
    name = request.form.get('holiday_name')
    h_date = request.form.get('date')
    desc = request.form.get('description')
    
    db = get_db()
    db.execute("INSERT INTO holidays (holiday_name, date, description) VALUES (?, ?, ?)", (name, h_date, desc))
    db.commit()
    db.close()
    flash('Holiday added successfully.', 'success')
    return redirect(url_for('hr_extensions.view_holidays'))

@hr_extensions_bp.route('/hr/holidays/delete/<int:h_id>', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def delete_holiday(h_id):
    db = get_db()
    db.execute("DELETE FROM holidays WHERE id=?", (h_id,))
    db.commit()
    db.close()
    flash('Holiday completely removed.', 'info')
    return redirect(url_for('hr_extensions.view_holidays'))


# ── 6. Helpdesk ───────────────────────────────────────────────────────────────
@hr_extensions_bp.route('/helpdesk', methods=['GET'])
@login_required
def helpdesk():
    db = get_db()
    if session.get('role') in ['admin', 'hr']:
        tickets = db.execute(
            "SELECT t.*, e.name FROM helpdesk_tickets t "
            "JOIN employees e ON t.employee_id=e.id "
            "ORDER BY t.created_at DESC"
        ).fetchall()
        db.close()
        return render_template('hr_extensions/admin_helpdesk.html', tickets=tickets)
    else:
        emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
        if not emp:
            db.close()
            return redirect(url_for('dashboard'))
            
        tickets = db.execute(
            "SELECT * FROM helpdesk_tickets WHERE employee_id=? ORDER BY created_at DESC", 
            (emp['id'],)
        ).fetchall()
        db.close()
        return render_template('hr_extensions/employee_helpdesk.html', tickets=tickets)

@hr_extensions_bp.route('/helpdesk/create', methods=['POST'])
@login_required
@role_required('employee')
def create_ticket():
    title = request.form.get('title')
    desc = request.form.get('description')
    
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if emp:
        db.execute("INSERT INTO helpdesk_tickets (employee_id, title, description) VALUES (?, ?, ?)", (emp['id'], title, desc))
        db.commit()
        flash('Support ticket raised.', 'success')
    db.close()
    return redirect(url_for('hr_extensions.helpdesk'))

@hr_extensions_bp.route('/helpdesk/respond/<int:t_id>', methods=['POST'])
@login_required
@role_required('hr', 'admin')
def respond_ticket(t_id):
    status = request.form.get('status')
    response = request.form.get('response')
    
    db = get_db()
    db.execute("UPDATE helpdesk_tickets SET status=?, response=? WHERE id=?", (status, response, t_id))
    db.commit()
    db.close()
    flash('Ticket adequately updated.', 'success')
    return redirect(url_for('hr_extensions.helpdesk'))
