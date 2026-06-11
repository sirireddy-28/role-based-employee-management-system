from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
import csv
from io import StringIO
from datetime import datetime

from functools import wraps

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
from database import get_db
from email_service import send_email
from notification_service import add_notification

extra_bp = Blueprint('extra', __name__)

# ── Notifications Route ───────────────────────────────────────────────────────

@extra_bp.route('/notifications')
@login_required
def notifications():
    db = get_db()
    notifs = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", 
        (session['user_id'],)
    ).fetchall()
    
    # Mark as read
    db.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND is_read=0", (session['user_id'],))
    db.commit()
    db.close()
    
    return render_template('extra/notifications.html', notifications=notifs)


# ── Attendance ───────────────────────────────────────────────────────────────

@extra_bp.route('/employee/attendance/mark', methods=['POST'])
@login_required
@role_required('employee', 'hr', 'admin')
def mark_attendance():
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        flash("Employee profile not found.", "danger")
        return redirect(url_for('employee_dashboard'))
    
    today = datetime.now().strftime('%Y-%m-%d')
    now_time = datetime.now().strftime('%H:%M:%S')
    
    existing = db.execute(
        "SELECT id FROM attendance WHERE employee_id=? AND date=?", 
        (emp['id'], today)
    ).fetchone()
    
    if existing:
        flash("Attendance already marked for today.", "warning")
    else:
        status = 'present' if datetime.now().hour < 10 else 'late' # example logic
        try:
            db.execute(
                "INSERT INTO attendance (employee_id, date, check_in_time, status) VALUES (?, ?, ?, ?)",
                (emp['id'], today, now_time, status)
            )
            db.commit()
            flash("Attendance marked successfully.", "success")
        except Exception as e:
            flash(f"Error marking attendance: {e}", "danger")
    db.close()
    return redirect(url_for('extra.employee_attendance'))

@extra_bp.route('/employee/attendance')
@login_required
@role_required('employee', 'hr', 'admin')
def employee_attendance():
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        return redirect(url_for('employee_dashboard'))
        
    records = db.execute(
        "SELECT * FROM attendance WHERE employee_id=? ORDER BY date DESC", 
        (emp['id'],)
    ).fetchall()
    db.close()
    return render_template('extra/attendance.html', records=records, role='employee')

@extra_bp.route('/hr/attendance')
@login_required
@role_required('hr', 'admin')
def hr_attendance():
    db = get_db()
    records = db.execute(
        "SELECT a.*, e.name FROM attendance a JOIN employees e ON a.employee_id=e.id ORDER BY a.date DESC"
    ).fetchall()
    db.close()
    return render_template('extra/attendance.html', records=records, role='hr')


# ── Meetings ─────────────────────────────────────────────────────────────────

@extra_bp.route('/hr/meetings', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_meetings():
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        date = request.form.get('date')
        time = request.form.get('time')
        desc = request.form.get('description', '')
        link = request.form.get('google_meet_link', '')
        
        try:
            db.execute(
                "INSERT INTO meetings (title, date, time, description, google_meet_link, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (title, date, time, desc, link, session['user_id'])
            )
            db.commit()
            
            # Send Email and Notification to ALL employees
            employees = db.execute("SELECT u.email, u.id FROM employees e JOIN users u ON e.user_id = u.id WHERE e.status='active'").fetchall()
            for e in employees:
                if e['email']:
                    send_email(
                        e['email'], 
                        f"New Meeting Scheduled: {title}", 
                        f"A new meeting has been scheduled on {date} at {time}.\nDescription: {desc}\nLink: {link}"
                    )
                add_notification(e['id'], f"New Meeting: {title} on {date} at {time}", "info")
                
            flash("Meeting scheduled and notified successfully.", "success")
        except Exception as e:
            flash(f"Error scheduling meeting: {e}", "danger")
        return redirect(url_for('extra.hr_meetings'))
        
    meetings = db.execute("SELECT m.*, u.username as creator FROM meetings m JOIN users u ON m.created_by=u.id ORDER BY m.date DESC, m.time DESC").fetchall()
    db.close()
    return render_template('extra/meetings.html', meetings=meetings, role='hr')

@extra_bp.route('/employee/meetings')
@login_required
def employee_meetings():
    db = get_db()
    meetings = db.execute("SELECT m.*, u.username as creator FROM meetings m JOIN users u ON m.created_by=u.id WHERE m.date >= DATE('now', '-1 day') ORDER BY m.date ASC, m.time ASC").fetchall()
    db.close()
    return render_template('extra/meetings.html', meetings=meetings, role='employee')


# ── Tasks ────────────────────────────────────────────────────────────────────

@extra_bp.route('/hr/tasks', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_tasks():
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        assigned_to = request.form.get('assigned_to')
        deadline = request.form.get('deadline')
        
        try:
            db.execute(
                "INSERT INTO tasks (title, description, assigned_to, assigned_by, deadline) VALUES (?, ?, ?, ?, ?)",
                (title, desc, assigned_to, session['user_id'], deadline)
            )
            db.commit()
            
            # Notify the user
            emp = db.execute("SELECT user_id, email FROM employees e JOIN users u ON e.user_id = u.id WHERE e.id=?", (assigned_to,)).fetchone()
            if emp:
                add_notification(emp['user_id'], f"New Task Assigned: {title}", "info")
                
            flash("Task assigned successfully.", "success")
        except Exception as e:
            flash(f"Error assigning task: {e}", "danger")
        return redirect(url_for('extra.hr_tasks'))
        
    tasks = db.execute("SELECT t.*, e.name as assigned_to_name FROM tasks t JOIN employees e ON t.assigned_to=e.id ORDER BY t.deadline ASC").fetchall()
    employees = db.execute("SELECT id, name FROM employees WHERE status='active'").fetchall()
    db.close()
    return render_template('extra/tasks.html', tasks=tasks, employees=employees, role='hr')

@extra_bp.route('/employee/tasks')
@login_required
@role_required('employee', 'hr', 'admin')
def employee_tasks():
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        return redirect(url_for('employee_dashboard'))
    
    tasks = db.execute("SELECT t.*, u.username as assigned_by_name FROM tasks t JOIN users u ON t.assigned_by=u.id WHERE t.assigned_to=? ORDER BY t.status DESC, t.deadline ASC", (emp['id'],)).fetchall()
    db.close()
    return render_template('extra/tasks.html', tasks=tasks, role='employee')

@extra_bp.route('/employee/tasks/update/<int:task_id>', methods=['POST'])
@login_required
def update_task_status(task_id):
    status = request.form.get('status')
    db = get_db()
    try:
        db.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
        db.commit()
        flash(f"Task marked as {status}.", "success")
    except Exception as e:
        flash(f"Error updating task: {e}", "danger")
    db.close()
    return redirect(url_for('extra.employee_tasks'))


# ── Performance ───────────────────────────────────────────────────────────────

@extra_bp.route('/hr/performance', methods=['GET', 'POST'])
@login_required
@role_required('hr', 'admin')
def hr_performance():
    db = get_db()
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        rating = int(request.form.get('rating'))
        feedback = request.form.get('feedback')
        
        try:
            db.execute(
                "INSERT INTO performance (employee_id, rating, feedback, reviewer_id) VALUES (?, ?, ?, ?)",
                (employee_id, rating, feedback, session['user_id'])
            )
            db.commit()
            # Notify employee
            emp = db.execute("SELECT user_id FROM employees WHERE id=?", (employee_id,)).fetchone()
            if emp:
                add_notification(emp['user_id'], f"New performance review added. Rating: {rating}/5", "info")
            flash("Review added successfully.", "success")
        except Exception as e:
            flash(f"Error adding review: {e}", "danger")
        return redirect(url_for('extra.hr_performance'))
        
    reviews = db.execute("""
        SELECT p.*, e.name as employee_name, u.username as reviewer_name 
        FROM performance p 
        JOIN employees e ON p.employee_id=e.id 
        JOIN users u ON p.reviewer_id=u.id 
        ORDER BY p.review_date DESC
    """).fetchall()
    employees = db.execute("SELECT id, name FROM employees WHERE status='active'").fetchall()
    db.close()
    return render_template('extra/performance.html', reviews=reviews, employees=employees, role='hr')

@extra_bp.route('/employee/performance')
@login_required
@role_required('employee', 'hr', 'admin')
def employee_performance():
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        return redirect(url_for('employee_dashboard'))
    
    reviews = db.execute("""
        SELECT p.*, u.username as reviewer_name 
        FROM performance p 
        JOIN users u ON p.reviewer_id=u.id 
        WHERE p.employee_id=? 
        ORDER BY p.review_date DESC
    """, (emp['id'],)).fetchall()
    db.close()
    return render_template('extra/performance.html', reviews=reviews, role='employee')


# ── Report Export ────────────────────────────────────────────────────────────

@extra_bp.route('/admin/reports/employees/export')
@login_required
@role_required('admin', 'hr')
def export_employees():
    db = get_db()
    employees = db.execute("SELECT * FROM employees").fetchall()
    db.close()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Email', 'Phone', 'Department', 'Designation', 'Joining Date', 'Status'])
    for e in employees:
        cw.writerow([e['id'], e['name'], e['email'], e['phone'], e['department'], e['designation'], e['joining_date'], e['status']])
    
    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = f"attachment; filename=employees_export_{datetime.now().strftime('%Y%m%d')}.csv"
    return output

@extra_bp.route('/admin/reports/leaves/export')
@login_required
@role_required('admin', 'hr')
def export_leaves():
    db = get_db()
    leaves = db.execute("SELECT l.*, e.name FROM leaves l JOIN employees e ON l.employee_id = e.id").fetchall()
    db.close()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Employee Name', 'Start Date', 'End Date', 'Reason', 'Status', 'Applied At'])
    for l in leaves:
        cw.writerow([l['id'], l['name'], l['start_date'], l['end_date'], l['reason'], l['status'], l['applied_at']])
    
    output = Response(si.getvalue(), mimetype="text/csv")
    output.headers["Content-Disposition"] = f"attachment; filename=leaves_export_{datetime.now().strftime('%Y%m%d')}.csv"
    return output

@extra_bp.route('/hr/reports')
@login_required
@role_required('hr', 'admin')
def reports():
    return render_template('extra/reports.html')

