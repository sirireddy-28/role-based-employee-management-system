from database import get_db

def add_notification(user_id, message, notif_type='info'):
    db = get_db()
    try:
        db.execute(
            "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
            (user_id, message, notif_type)
        )
        db.commit()
    except Exception as e:
        print(f"Failed to add notification: {e}")
    finally:
        db.close()
