from backend.app import create_app
from backend.models import db, User, RoleEnum
from werkzeug.security import generate_password_hash

# --- Configuration ---
MANAGER_EMAIL = 'jenni.kim@dsacompany.com'
MANAGER_NAME = 'Jennie Kim'
MANAGER_POSITION = 'Recruitment Manager'
MANAGER_PASSWORD = 'TempPass123!'

app = create_app()
with app.app_context():
    # 1. DELETE the old user
    old_u = db.session.query(User).filter_by(email=MANAGER_EMAIL).first()
    if old_u:
        db.session.delete(old_u)
        db.session.commit()
        print(f"? User {MANAGER_EMAIL} (ID: {old_u.id}) deleted.")

    # 2. CREATE the new user
    pw_hash = generate_password_hash(MANAGER_PASSWORD)
    new_manager = User(
        name=MANAGER_NAME,
        email=MANAGER_EMAIL,
        password_hash=pw_hash,
        role=RoleEnum.MANAGER,
        position=MANAGER_POSITION,
        change_password=True
    )
    db.session.add(new_manager)
    db.session.commit()
    print(f"? Jennie Kim successfully recreated with password: {MANAGER_PASSWORD}. ID: {new_manager.id}")

