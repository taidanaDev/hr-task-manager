import os
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from backend.models import db
from flask_cors import CORS


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///backend/database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dsaprojectsecretkey')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])

    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    if uri.startswith("sqlite:///"):
        db_path = Path(uri.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    Migrate(app, db)


    jwt = JWTManager()
    jwt.init_app(app)
    CORS(app)



    from backend.api.auth import auth_bp
    from backend.api.users import bp as users_bp
    from backend.api.tasks import bp as tasks_bp
    from backend.api.notifications import bp as notifications_bp
    from backend.api.stats import bp as stats_bp
    from backend.api.manager import bp as manager_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(manager_bp)

    @app.route('/')
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")
    
    @app.route("/login")
    def serve_login():
        return send_from_directory(app.static_folder, "login.html")
    
        
    # API Health Check (optional sanity check)
    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'ok', 'message': 'HR Task Manager API is running'}), 200
    
    return app

app = create_app()
