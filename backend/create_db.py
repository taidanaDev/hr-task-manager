from backend.app import create_app
from models import db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created.")