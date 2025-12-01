from backend.app import create_app
from backend.models import db, User
from werkzeug.security import generate_password_hash

# IMPORTANT: Ensure your FLASK_APP and DATABASE_URL environment variables are set correctly
# as you did previously: $env:DATABASE_URL = "sqlite:///C:/Users/..."

app = create_app()
with app.app_context():
    u = db.session.query(User).filter_by(email='jisoo@company.local').first()
    
    if u:
        u.password_hash = generate_password_hash('TestPass123!')
        db.session.commit()
        print("? Password for jisoo@company.local successfully updated to: TestPass123!")
    else:
        print("? Error: User jisoo@company.local not found in the database.")

