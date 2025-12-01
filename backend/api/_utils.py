from backend.models import db, Notification, User

def create_notification(user_id, message):
    n = Notification(user_id=user_id, message=message, read=False)
    db.session.add(n)
    db.session.commit()
    return n

def update_user_workload(user_id: int, delta: int):
    user = db.session.get(User, user_id)
    if user:
        new_workload = (user.workload or 0) + delta
        user.workload = max(0, new_workload)
        db.session.commit()
        return True
    return False