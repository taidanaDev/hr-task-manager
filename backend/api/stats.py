from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from backend.models import db, User, Task, StatusEnum, PriorityEnum, RoleEnum
from backend.api._auth_helpers import role_required
from sqlalchemy import func

bp = Blueprint("stats", __name__, url_prefix="/api/stats")

@bp.route("", methods=["GET"])
@jwt_required()
def stats_overview():
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())


    user_filter_ids = None

    if role == RoleEnum.ADMIN.value:
        user_filter_ids = None
    elif role == RoleEnum.MANAGER.value:
        user_filter_ids = db.session.query(User.id).filter_by(supervisor_id=caller_id).subquery()
    else:
        return jsonify({"msg":"forbidden - only admin or manager"}), 403

    total_users_q = db.session.query(func.count(User.id))
    if user_filter_ids is not None:
        total_users_q = total_users_q.filter(User.id.in_(user_filter_ids))
    total_users = total_users_q.scalar()

    total_tasks_q = db.session.query(func.count(Task.id))
    if user_filter_ids is not None:
        total_tasks_q = total_tasks_q.filter(Task.assignee_id.in_(user_filter_ids))
    total_tasks = total_tasks_q.scalar()

    # tasks by status
    status_counts = {}
    for s in StatusEnum:
        q = db.session.query(func.count(Task.id)).filter(Task.status == s)
        if user_filter_ids is not None:
            q = q.filter(Task.assignee_id.in_(user_filter_ids))
        status_counts[s.value] = q.scalar() or 0

    # tasks by priority
    priority_counts = {}
    for p in PriorityEnum:
        q = db.session.query(func.count(Task.id)).filter(Task.priority == p)
        if user_filter_ids is not None:
            q = q.filter(Task.assignee_id.in_(user_filter_ids))
        priority_counts[p.value] = q.scalar() or 0

    # top employees by workload
    emp_q = db.session.query(User.id, User.name, User.email, User.workload).filter(User.role == RoleEnum.EMPLOYEE.value)
    if user_filter_ids is not None:
        emp_q = emp_q.filter(User.id.in_(user_filter_ids))
    top_employees = emp_q.order_by(User.workload.desc().nullslast(), User.id).limit(10).all()
    top_employees_out = [{"id": e.id, "name": e.name, "email": e.email, "workload": e.workload or 0} for e in top_employees]

    # per-manager task counts (only for admin)
    managers_out = []
    if role == RoleEnum.ADMIN.value:
        mgr_q = db.session.query(User.id, User.name, func.count(Task.id).label("task_count")).filter(User.role == RoleEnum.MANAGER.value).outerjoin(Task, Task.creator_id == User.id).group_by(User.id).all()
        managers_out = [{"id": m.id, "name": m.name, "created_task_count": int(m.task_count)} for m in mgr_q]

    return jsonify({
        "total_users": int(total_users or 0),
        "total_tasks": int(total_tasks or 0),
        "tasks_by_status": status_counts,
        "tasks_by_priority": priority_counts,
        "top_employees_by_workload": top_employees_out,
        "per_manager_summary": managers_out
    }), 200
