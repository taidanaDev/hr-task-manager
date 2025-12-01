import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity, get_jwt
from werkzeug.security import check_password_hash
from backend.models import db, User
from backend.api._auth_helpers import role_required

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
@jwt_required()
@role_required('admin')
def register():
    data = request.get_json()
    if not data or not all(key in data for key in ['email', 'password', 'role', 'manager_id']):
        return jsonify({"message": "Missing required fields"}), 400

    email = data['email']
    password = data['password']
    role = data['role']
    manager_id = data.get('manager_id')

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"}), 409

    try:
        new_user = User(email=email, password=password, role=role, manager_id=manager_id)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered successfully", "user_id": new_user.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Error registering user: {e}"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"message": "Missing email or password in request"}), 400

    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and check_password_hash(user.password_hash, password):
        # normalize role to a plain string
        try:
            role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        except Exception:
            role_str = str(user.role)

        expires = datetime.timedelta(hours=1)
        additional_claims = {"user_id": str(user.id), "role": role_str,"name":user.name}

        access_token = create_access_token(
            identity=str(user.id),
            expires_delta=expires,
            additional_claims=additional_claims
        )

        return jsonify({
            "message": "Login successful",
            "access_token": access_token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": role_str,
                "name": user.name
            }
        }), 200

    return jsonify({"message": "Invalid credentials"}), 401


@auth_bp.route('/verify_role', methods=['GET'])
@jwt_required()
def verify_role():
    claims = get_jwt()
    user_id = claims.get("user_id")
    role = claims.get("role")
    
    if user_id and role:
        return jsonify({"is_authenticated": True, "user_id": user_id, "role": role}), 200
    
    return jsonify({"message": "Authentication token invalid or expired"}), 401

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    data = request.get_json() or {}
    old_pw = data.get("old_password")
    new_pw = data.get("new_password")

    user = User.query.get(int(get_jwt_identity()))

    if not user or not check_password_hash(user.password_hash, old_pw):
        return jsonify({"msg": "incorrect current password"}), 400

    from werkzeug.security import generate_password_hash
    user.password_hash = generate_password_hash(new_pw)
    user.change_password = False
    db.session.commit()

    return jsonify({"msg": "password updated"}), 200


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    return jsonify({"message": "Logout successful (token invalidated client-side)"}), 200