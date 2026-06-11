import sqlite3
import os
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database import get_db
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

ai_service_bp = Blueprint('ai_service', __name__)

def init_ai_schema():
    """Initializes the AI enhancement database tables."""
    db = get_db()
    cursor = db.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS employee_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, skill_name)
        );
    """)
    # Seed some sample skills if table is empty
    count = db.execute("SELECT COUNT(*) as c FROM employee_skills").fetchone()['c']
    if count == 0:
        cursor.executescript("""
            INSERT OR IGNORE INTO employee_skills (employee_id, skill_name) VALUES (1, 'Python');
            INSERT OR IGNORE INTO employee_skills (employee_id, skill_name) VALUES (1, 'SQL');
            INSERT OR IGNORE INTO employee_skills (employee_id, skill_name) VALUES (3, 'JavaScript');
            INSERT OR IGNORE INTO employee_skills (employee_id, skill_name) VALUES (3, 'React');
        """)
    db.commit()
    db.close()


@ai_service_bp.before_app_request
def setup_ai():
    # Only run once using a flag in the application context or a global variable
    if not hasattr(ai_service_bp, 'schema_initialized'):
        init_ai_schema()
        ai_service_bp.schema_initialized = True

@ai_service_bp.route('/ai/insights')
@login_required
@role_required('admin', 'hr')
def ai_insights():
    db = get_db()
    
    # --- 1. Predictive Workforce AI ---
    # Prediction Rule: 
    # High Risk: Performance Rating <= 2 OR Leaves Taken >= 15
    # Medium Risk: Performance Rating == 3 OR Leaves Taken >= 10
    # Low Risk: Everyone else
    employees_query = """
        SELECT e.id, e.name, p.rating, lb.leaves_taken 
        FROM employees e
        LEFT JOIN performance p ON e.id = p.employee_id
        LEFT JOIN leave_balances lb ON e.id = lb.employee_id
    """
    employee_data = db.execute(employees_query).fetchall()
    
    risk_predictions = []
    for emp in employee_data:
        rating = emp['rating'] if emp['rating'] is not None else 5 # Assume 5 if no rating
        leaves = emp['leaves_taken'] if emp['leaves_taken'] is not None else 0
        
        status = "Low Risk"
        badge_class = "badge bg-success"
        reason = []
        
        if rating <= 2 or leaves >= 15:
            status = "High Risk"
            badge_class = "badge bg-danger"
            if rating <= 2: reason.append("Low Performance")
            if leaves >= 15: reason.append("High Leave Usage")
        elif rating == 3 or leaves >= 10:
            status = "Medium Risk"
            badge_class = "badge bg-warning text-dark"
            if rating == 3: reason.append("Satisfactory Performance")
            if leaves >= 10: reason.append("Moderate Leave Usage")
            
        if not reason:
            reason.append("Stable Metrics")
            
        risk_predictions.append({
            'name': emp['name'],
            'status': status,
            'badge': badge_class,
            'reason': ", ".join(reason)
        })
        
    # --- 2. Dynamic Skill Mapping ---
    tasks = db.execute("SELECT id, title, assigned_to FROM tasks WHERE status = 'pending'").fetchall()
    all_skills = db.execute("SELECT e.name, s.skill_name FROM employee_skills s JOIN employees e ON s.employee_id = e.id").fetchall()
    
    # Create employee skill map
    employee_skill_map = {}
    for s in all_skills:
        name = s['name']
        if name not in employee_skill_map:
            employee_skill_map[name] = []
        employee_skill_map[name].append(s['skill_name'].lower())
        
    skill_gaps = []
    for t in tasks:
        title_lower = t['title'].lower()
        # If task title mentions python, sql, react, etc
        needed_skills = []
        if 'python' in title_lower: needed_skills.append('python')
        if 'react' in title_lower: needed_skills.append('react')
        if 'sql' in title_lower or 'database' in title_lower: needed_skills.append('sql')
        if 'js' in title_lower or 'javascript' in title_lower: needed_skills.append('javascript')
        
        suggested_employees = []
        for emp_name, emp_skills in employee_skill_map.items():
            # If intersection of needed skills and employee skills is > 0
            if any(skill in emp_skills for skill in needed_skills):
                suggested_employees.append(emp_name)
                
        if needed_skills:
            skill_gaps.append({
                'task_title': t['title'],
                'needed_skills': ", ".join(needed_skills),
                'suggestions': ", ".join(suggested_employees) if suggested_employees else "Training Recommended! No skilled employee found."
            })

    db.close()
    
    return render_template('ai/ai_insights.html', risk_predictions=risk_predictions, skill_gaps=skill_gaps)
