from flask import Blueprint, request, jsonify, session
from database import get_db
import re

chatbot_service_bp = Blueprint('chatbot_service', __name__)

@chatbot_service_bp.route('/api/chat', methods=['POST'])
def chat():
    if 'user_id' not in session:
        return jsonify({"reply": "Please log in to use the chatbot."})
        
    data = request.get_json()
    message = data.get('message', '').lower()
    
    db = get_db()
    reply = "I'm a basic AI Assistant. Try asking me about your 'salary', 'leaves', 'attendance', 'meetings', 'tasks', or to 'update my phone number to X'!"
    
    emp = db.execute("SELECT id FROM employees WHERE user_id=?", (session['user_id'],)).fetchone()
    
    if not emp:
        db.close()
        return jsonify({"reply": "You are not mapped to an employee record."})

    emp_id = emp['id']

    # 1. Update Phone Number Intent
    if 'update my phone number' in message or 'change my phone number' in message:
        match = re.search(r'to\s+(\d+)', message)
        if match:
            new_phone = match.group(1)
            try:
                db.execute("UPDATE employees SET phone=? WHERE id=?", (new_phone, emp_id))
                db.commit()
                reply = f"Your phone number has been updated to {new_phone}."
            except Exception as e:
                reply = "There was an error updating your phone number."
        else:
            reply = "Please provide the number in the format: 'Update my phone number to 1234567890'."
    
    # 2. Leaves Intent
    elif 'leave' in message or 'balance' in message:
        lb = db.execute("SELECT leave_balance FROM leave_balances WHERE employee_id=?", (emp_id,)).fetchone()
        if lb:
            reply = f"You currently have {lb['leave_balance']} leaves remaining."
        else:
            total_leaves = db.execute("SELECT COUNT(*) as c FROM leaves WHERE employee_id=?", (emp_id,)).fetchone()['c']
            reply = f"You have applied for {total_leaves} leaves in total."
            
    # 3. Salary Intent
    elif 'salary' in message or 'pay' in message:
        salary_record = db.execute("SELECT net_salary, month, year FROM salaries WHERE employee_id=? ORDER BY year DESC, id DESC LIMIT 1", (emp_id,)).fetchone()
        if salary_record:
            reply = f"Your most recent net salary was ₹{salary_record['net_salary']:,.0f} for {salary_record['month']} {salary_record['year']}."
        else:
            reply = "I couldn't find your latest salary records."
            
    # 4. Attendance Intent
    elif 'attendance' in message or 'present' in message:
        # Assuming attendance table exists
        att = db.execute("SELECT date, status, check_in_time FROM attendance WHERE employee_id=? ORDER BY date DESC LIMIT 3", (emp_id,)).fetchall()
        if att:
            a_list = "\n".join([f"- {a['date']}: {a['status']} at {a['check_in_time']}" for a in att])
            reply = f"Here is your recent attendance:\n{a_list}"
        else:
            reply = "No attendance records found."

    # 5. Meetings Intent
    elif 'meeting' in message:
        meetings = db.execute("SELECT title, date, time FROM meetings WHERE date >= CURRENT_DATE ORDER BY date ASC, time ASC LIMIT 3").fetchall()
        if meetings:
            m_list = "\n".join([f"- {m['title']} on {m['date']} at {m['time']}" for m in meetings])
            reply = f"Upcoming meetings:\n{m_list}"
        else:
            reply = "You have no upcoming meetings."

    # 6. Tasks Intent
    elif 'task' in message or 'assignment' in message or 'work' in message:
        tasks = db.execute("SELECT title, deadline FROM tasks WHERE assigned_to=? AND status='pending' ORDER BY deadline ASC LIMIT 3", (emp_id,)).fetchall()
        if tasks:
            t_list = "\n".join([f"- {t['title']} (Due: {t['deadline']})" for t in tasks])
            reply = f"Here are your upcoming pending tasks:\n{t_list}"
        else:
            reply = "You have no pending tasks assigned at the moment! Good job."
            
    db.close()
    return jsonify({"reply": reply})
