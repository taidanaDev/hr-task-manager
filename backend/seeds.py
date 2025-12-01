# backend/seeds.py
import os
from werkzeug.security import generate_password_hash
from backend.app import create_app
from backend.models import db, User, RoleEnum, PriorityEnum

def add_user(session, name, email, password, role=RoleEnum.EMPLOYEE, position=None, supervisor_id=None, change_password=True):
    """Helper to create a user and flush to assign an id immediately."""
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        position=position,
        supervisor_id=supervisor_id,
        change_password=change_password,
        workload=0
    )
    session.add(user)
    session.flush() 
    return user

def seed_admin_only():
    app = create_app()
    with app.app_context():

        db.create_all()
        with db.session.begin():
            # Head of HR (top-level manager)
            admin = add_user(
                db.session,
                name="Jovell Punzalan",
                email="admin@dsacompany.com",
                password="admin123",
                role=RoleEnum.ADMIN,
                position="Head of HR",
                supervisor_id=None,
                change_password=False
            )

        print("Seeding complete: admin user created.")
        print("Head of HR (manager) credentials:")
        print("  email: admin@dsacompany.com")
        print("  password: admin123")

if __name__ == "__main__":
    seed_admin_only()
