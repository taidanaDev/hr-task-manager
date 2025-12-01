from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.models import db, User, Task, RoleEnum
from backend.api._auth_helpers import role_required

bp = Blueprint("manager", __name__, url_prefix="/api/manager")

@bp.route("/workload", methods=["GET"])
@bp.route("/workload/", methods=["GET"])
@jwt_required()
@role_required(RoleEnum.MANAGER.value, RoleEnum.ADMIN.value)
def manager_workload():
    caller_id = int(get_jwt_identity())

    direct_q = db.session.query(User).filter_by(supervisor_id=caller_id)
    direct = direct_q.all()

    team = []
    for u in direct:
        task_count = db.session.query(Task).filter(Task.assignee_id == u.id).count()
        team.append({
            "user_id": u.id,
            "name": u.name,
            "email": u.email,
            "workload": task_count
        })

    return jsonify({"team_workload": team}), 200


@bp.route("/tasks", methods=["GET"])
@bp.route("/tasks/", methods=["GET"])
@jwt_required()
@role_required(RoleEnum.MANAGER.value, RoleEnum.ADMIN.value)
def manager_tasks():
    caller_id = int(get_jwt_identity())

    direct_reports = db.session.query(User).filter_by(supervisor_id=caller_id).all()
    direct_ids = [r.id for r in direct_reports]
    
    all_assigned_ids = direct_ids + [caller_id]
    if not all_assigned_ids:
        return jsonify({"tasks": []}), 200

    q = db.session.query(Task).filter(Task.assignee_id.in_(all_assigned_ids)).order_by(Task.id.desc())
    tasks = q.all()
    out = []
    for t in tasks:
        out.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": (t.priority.value if getattr(t,'priority',None) else None),
            "status": (t.status.value if getattr(t,'status',None) else None),
            "assignee_id": t.assignee_id,
            "assignee_name": (t.assignee.name if getattr(t,'assignee',None) else None),
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })

    return jsonify({"tasks": out}), 200
