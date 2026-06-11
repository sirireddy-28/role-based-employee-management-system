from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, flash
from database import get_db

skill_service_bp = Blueprint('skill_service', __name__)

def init_skill_db():
    db = get_db()
    cursor = db.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS employee_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            proficiency TEXT DEFAULT 'Beginner',
            source TEXT DEFAULT 'Manual',
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS training_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            recommended_skill TEXT NOT NULL,
            reason TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );

        CREATE TABLE IF NOT EXISTS project_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            description TEXT
        );
    """)
    db.commit()
    db.close()

@skill_service_bp.route('/employee/skills', methods=['GET', 'POST'])
def employee_skills():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    if not emp:
        db.close()
        flash("Employee profile not found.", "danger")
        return redirect(url_for('dashboard'))

    emp_id = emp['id']

    if request.method == 'POST':
        skill_name = request.form.get('skill_name', '').strip()
        proficiency = request.form.get('proficiency', 'Beginner')
        if skill_name:
            # Check if skill exists
            existing = db.execute("SELECT id FROM employee_skills WHERE employee_id=? AND LOWER(skill_name)=?", 
                                  (emp_id, skill_name.lower())).fetchone()
            if not existing:
                db.execute("INSERT INTO employee_skills (employee_id, skill_name, proficiency) VALUES (?, ?, ?)",
                           (emp_id, skill_name, proficiency))
                db.commit()
                flash("Skill added successfully!", "success")
            else:
                flash("You already added this skill.", "warning")
        return redirect(url_for('skill_service.employee_skills'))

    skills = db.execute("SELECT * FROM employee_skills WHERE employee_id=?", (emp_id,)).fetchall()
    trainings = db.execute("SELECT * FROM training_recommendations WHERE employee_id=?", (emp_id,)).fetchall()
    db.close()
    
    return render_template('skills/employee_skills.html', skills=skills, trainings=trainings)


@skill_service_bp.route('/hr/talent_marketplace', methods=['GET', 'POST'])
def talent_marketplace():
    if 'user_id' not in session or session.get('role') not in ['admin', 'hr']:
        return redirect(url_for('dashboard'))
        
    db = get_db()
    
    if request.method == 'POST':
        project_name = request.form.get('project_name', '').strip()
        required_skills = request.form.get('required_skills', '').strip()
        description = request.form.get('description', '').strip()
        if project_name and required_skills:
            db.execute("INSERT INTO project_recommendations (project_name, required_skills, description) VALUES (?, ?, ?)",
                       (project_name, required_skills, description))
            db.commit()
            flash("Project added successfully!", "success")
        return redirect(url_for('skill_service.talent_marketplace'))

    projects = db.execute("SELECT * FROM project_recommendations ORDER BY id DESC").fetchall()
    
    # Calculate skill matches for projects
    project_matches = []
    employees = db.execute("SELECT e.id, e.name, e.department FROM employees e").fetchall()
    
    # Prefetch all skills grouped by employee for performance
    all_skills = db.execute("SELECT employee_id, LOWER(skill_name) as sn FROM employee_skills").fetchall()
    emp_skills_map = {}
    for row in all_skills:
        emp_skills_map.setdefault(row['employee_id'], set()).add(row['sn'])

    for proj in projects:
        req_skills_list = [s.strip().lower() for s in proj['required_skills'].split(',') if s.strip()]
        matches = []
        for e in employees:
            e_skills_set = emp_skills_map.get(e['id'], set())
            overlap = set(req_skills_list).intersection(e_skills_set)
            
            if overlap:
                matches.append({
                    "name": e['name'],
                    "department": e['department'],
                    "matched_skills": ", ".join([s.title() for s in overlap]),
                    "match_count": len(overlap)
                })
        
        # Sort matches by number of matching skills (descending)
        matches.sort(key=lambda x: x['match_count'], reverse=True)
        
        project_matches.append({
            "project": proj,
            "matches": matches
        })
        
    db.close()
    return render_template('skills/talent_marketplace.html', project_matches=project_matches)
