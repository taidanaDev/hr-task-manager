from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash
import secrets, string
from backend.api.tree_utils import build_forest_from_db_rows, get_subtree_ids, serialize_forest, serialize_node



from backend.models import db, User, RoleEnum

bp = Blueprint("users", __name__, url_prefix="/api/users")

def gen_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def require_roles(*allowed_roles):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            claims = get_jwt() or {}
            role = claims.get("role")
            if role not in allowed_roles:
                return jsonify({"msg":"forbidden - insufficient role"}), 403
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator

@bp.route("", methods=["POST"])
@jwt_required()
def create_user():
    claims = get_jwt() or {}
    caller_role = claims.get("role")
    caller_id = int(get_jwt_identity())

    data = request.get_json() or {}
    name = data.get("name")
    email = data.get("email")
    position = data.get("position")
    requested_role = data.get("role", RoleEnum.EMPLOYEE.value)
    supervisor_id = data.get("supervisor_id")
    supplied_password = data.get("password")

    if not name or not email or not supplied_password:
        return jsonify({"msg":"name, email, and password are required"}), 400

    if caller_role == RoleEnum.ADMIN.value:
        if requested_role not in {r.value for r in RoleEnum}:
            return jsonify({"msg":"invalid role"}), 400
    elif caller_role == RoleEnum.MANAGER.value:
        if requested_role != RoleEnum.EMPLOYEE.value:
            return jsonify({"msg":"forbidden - managers can only create employees"}), 403
        if not supervisor_id:
            supervisor_id = caller_id
    else:
        return jsonify({"msg":"forbidden - only admin or manager can create users"}), 403


    if db.session.query(User).filter_by(email=email).first():
        return jsonify({"msg":"email already exists"}), 409

    pw_hash = generate_password_hash(supplied_password)

    new_user = User(
        name=name,
        email=email,
        password_hash=pw_hash,
        role=RoleEnum(requested_role),
        position=position,
        supervisor_id=supervisor_id,
        workload=0,
        change_password=True   
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "msg":"user created",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role.value,
            "supervisor_id": new_user.supervisor_id
        }
    }), 201


@bp.route("", methods=["GET"])
@jwt_required()
def list_users():
    """
    Admin: returns all users
    Manager: returns users in their subtree
    Employee: returns own record only
    """
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = get_jwt_identity()

    # support ?role=manager to fetch managers (admin-only)
    role_filter = request.args.get("role")
    if role_filter == "manager":
        if role != RoleEnum.ADMIN.value:
            return jsonify({"msg":"forbidden - admin only"}), 403
        users = db.session.query(User).filter(User.role == RoleEnum.MANAGER).order_by(User.id).all()
    else:
        if role == RoleEnum.ADMIN.value:
            users = db.session.query(User).order_by(User.id).all()
        elif role == RoleEnum.MANAGER.value:
            users = db.session.query(User).filter_by(supervisor_id=caller_id).order_by(User.id).all()
        else:
            users = db.session.query(User).filter_by(id=caller_id).all()
    out = []
    for u in users:
        out.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "position": u.position,
            "supervisor_id": u.supervisor_id,
            "workload": u.workload
        })
    return jsonify(out), 200

@bp.route("/team", methods=["GET"])
@jwt_required()
@require_roles(RoleEnum.MANAGER.value, RoleEnum.ADMIN.value)
def my_team():
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = get_jwt_identity()
    query_manager = request.args.get("manager_id")

    if role == RoleEnum.ADMIN.value and query_manager:
        manager_id = int(query_manager)
    elif role == RoleEnum.MANAGER.value:
        manager_id = caller_id
    else:
        return jsonify({"msg":"forbidden"}), 403

    users = db.session.query(User).filter_by(supervisor_id=manager_id).order_by(User.id).all()
    out = [{"id":u.id,"name":u.name,"email":u.email,"role":u.role.value,"position":u.position,"workload":u.workload} for u in users]
    return jsonify(out), 200

@bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = get_jwt_identity()

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"msg":"user not found"}), 404

    if role == RoleEnum.ADMIN.value:
        allowed = True
    elif role == RoleEnum.MANAGER.value:
        allowed = (user.supervisor_id == caller_id) or (user.id == caller_id)
    else:
        allowed = (user.id == caller_id)

    if not allowed:
        return jsonify({"msg":"forbidden"}), 403

    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "position": user.position,
        "supervisor_id": user.supervisor_id,
        "workload": user.workload
    }), 200

@bp.route("/admin-reset-password", methods=["POST"])
@jwt_required()
def admin_reset_password():
    from werkzeug.security import generate_password_hash
    claims = get_jwt() or {}
    if claims.get("role") != RoleEnum.ADMIN.value:
        return jsonify({"msg":"forbidden - admin only"}), 403

    data = request.get_json() or {}
    target_id = data.get("user_id")
    new_pw = data.get("new_password")
    if not target_id or not new_pw:
        return jsonify({"msg":"user_id and new_password required"}), 400

    user = db.session.get(User, int(target_id))
    if not user:
        return jsonify({"msg":"user not found"}), 404

    user.password_hash = generate_password_hash(new_pw)
    user.change_password = True   
    db.session.commit()

    return jsonify({"msg":"password reset", "temporary_password": new_pw}), 200

@bp.route("/<int:manager_id>/subtree-ids", methods=["GET"])
@jwt_required()
def manager_subtree_ids(manager_id):
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    if role == RoleEnum.MANAGER.value and manager_id != caller_id:
        return jsonify({"msg":"forbidden"}), 403
    rows = db.session.query(User.id, User.supervisor_id, User.name, User.email, User.role).all()
    nodes = build_forest_from_db_rows(rows)
    subtree_ids = get_subtree_ids(nodes.get(int(manager_id))) if nodes.get(int(manager_id)) else []
    return jsonify({"manager_id": manager_id, "subtree_ids": subtree_ids}), 200

@bp.route("/org-chart", methods=["GET"])
@jwt_required()
def org_chart_json():
    """
    Query param: ?scope=full or ?scope=self
    - scope=full  -> return full organization for everyone (admin/manager/employee)
    - scope=self  -> admin: full, manager: subtree, employee: own record (or forbidden)
    - default     -> behaves as scope=self
    """
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())
    scope = (request.args.get("scope") or "self").lower()

    rows = db.session.query(User.id, User.name, User.supervisor_id, User.role, User.position).all()
    nodes = build_forest_from_db_rows(rows)


    if scope == "full":
        out = serialize_forest(nodes)
        return jsonify(out), 200

    if role == RoleEnum.ADMIN.value:
        out = serialize_forest(nodes)
        return jsonify(out), 200

    if role == RoleEnum.MANAGER.value:
        root = nodes.get(caller_id)
        out = [serialize_node(root, include_children=True)] if root else []
        return jsonify(out), 200

    user_node = nodes.get(caller_id)
    if user_node:
        out = [serialize_node(user_node, include_children=True)]
        return jsonify(out), 200

    return jsonify({"msg": "forbidden"}), 403
