import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.models import db, Task, User, TaskDependency, PriorityEnum, StatusEnum, RoleEnum
from backend.api._auth_helpers import role_required
from backend.api._utils import create_notification

from backend.api.dsa_utils import TaskGraph, TaskPriorityQueue, find_best_assignee

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

MAX_WORKLOAD = int(os.getenv("MAX_WORKLOAD", "3"))


def priority_value(priority):
    mapping = {PriorityEnum.HIGH.value: 0, PriorityEnum.MEDIUM.value: 1, PriorityEnum.LOW.value: 2}
    return mapping.get(str(priority).lower(), 1)


@bp.route("/batch-schedule", methods=["POST"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value)
def batch_schedule():
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    # gather employees (for admin: all employees, for manager: direct reports)
    q_employees = db.session.query(User).filter(User.role == RoleEnum.EMPLOYEE.value)
    if role == RoleEnum.MANAGER.value:
        q_employees = q_employees.filter_by(supervisor_id=caller_id)
    available_employees = q_employees.all()
    if not available_employees:
        return jsonify({"msg": "No employees available for scheduling."}), 400

    # gather pending tasks
    pending_tasks = db.session.query(Task).filter(Task.status == StatusEnum.PENDING).all()
    if not pending_tasks:
        return jsonify({"msg": "No pending tasks to schedule.", "scheduled_count": 0}), 200

    all_task_ids = [t.id for t in pending_tasks]

    # dependencies among pending tasks
    deps = []
    try:
        raw_deps = db.session.query(TaskDependency).filter(
            TaskDependency.prereq_id.in_(all_task_ids),
            TaskDependency.dependent_id.in_(all_task_ids)
        ).all()
        deps = [(d.prereq_id, d.dependent_id) for d in raw_deps]
    except Exception:
        deps = []

    # build task graph and check for cycles
    task_graph = TaskGraph(pending_tasks, deps)
    valid_schedule_order = task_graph.topological_sort()
    if valid_schedule_order is None:
        return jsonify({
            "msg": "Schedule failed: A circular dependency (cycle) was detected among pending tasks.",
            "scheduled_count": 0
        }), 400

    # priority queue & map
    ready_to_schedule_queue = TaskPriorityQueue()
    task_map = {t.id: t for t in pending_tasks}
    current_in_degrees = dict(task_graph.in_degree)

    for tid in valid_schedule_order:
        if current_in_degrees.get(tid, 0) == 0 and tid in task_map:
            ready_to_schedule_queue.push(task_map[tid], priority_value)

    scheduled_tasks = []

    # Scheduling loop (greedy)
    while not ready_to_schedule_queue.is_empty():
        task_to_assign = ready_to_schedule_queue.pop()
        if task_to_assign is None:
            break

        chosen_employee = find_best_assignee(available_employees, MAX_WORKLOAD)
        if not chosen_employee:
            break

        # assign
        task_to_assign.assignee_id = chosen_employee.id
        task_to_assign.status = StatusEnum.ASSIGNED
        chosen_employee.workload = (chosen_employee.workload or 0) + 1
        db.session.commit()
        try:
            create_notification(chosen_employee.id, f"New task assigned (Batch): {task_to_assign.title} (id={task_to_assign.id})")
        except Exception:
            pass

        scheduled_tasks.append(task_to_assign)

        for dependent_id in task_graph.adj.get(task_to_assign.id, []):
            current_in_degrees[dependent_id] -= 1
            if current_in_degrees[dependent_id] == 0 and dependent_id in task_map:
                ready_to_schedule_queue.push(task_map[dependent_id], priority_value)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({
        "msg": "Batch scheduling complete.",
        "scheduled_count": len(scheduled_tasks),
        "tasks_scheduled": [t.id for t in scheduled_tasks]
    }), 200


@bp.route("", methods=["GET"])
@jwt_required()
def list_all_tasks():
    """
    Role-aware listing:
      - admin: all tasks
      - manager: tasks assigned to direct reports OR created by the manager
      - employee: tasks assigned to self
    Each returned task will include a 'blocked' boolean (True if any prereq not completed).
    """
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    q = db.session.query(Task)

    if role == RoleEnum.MANAGER.value:
        direct = db.session.query(User.id).filter_by(supervisor_id=caller_id).subquery()
        q = q.filter((Task.assignee_id.in_(direct)) | (Task.creator_id == caller_id))
    elif role == RoleEnum.EMPLOYEE.value:
        q = q.filter(Task.assignee_id == caller_id)


    tasks = q.order_by(Task.id.desc()).all()


    deps = db.session.query(TaskDependency).all()
    prereq_map = {}
    for d in deps:
        prereq_map.setdefault(d.dependent_id, []).append(d.prereq_id)

    out = []
    for t in tasks:
        blocked = False
        prereqs = prereq_map.get(t.id, [])
        if prereqs:
            for pid in prereqs:
                ptask = db.session.get(Task, int(pid))
                if ptask and ptask.status != StatusEnum.COMPLETED:
                    blocked = True
                    break
        if blocked:
            status_str = StatusEnum.BLOCKED.value if hasattr(StatusEnum, 'BLOCKED') else 'blocked'
        else:
            try:
                status_str = t.status.value if hasattr(t.status, 'value') else str(t.status)
            except Exception:
                status_str = str(t.status or StatusEnum.PENDING.value)
        out.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority.value if t.priority else None,
            "status": status_str,
            "blocked": blocked,
            "assignee_id": t.assignee_id,
            "assignee_name": (t.assignee.name if t.assignee else None),
            "creator_id": t.creator_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "prerequisites": prereqs
        })

    return jsonify(out), 200


@bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json() or {}
    title = data.get("title")
    description = data.get("description")
    priority = data.get("priority", PriorityEnum.MEDIUM.value)
    assignee_id = data.get("assignee_id")
    due_date = data.get("due_date")

    if not title:
        return jsonify({"msg": "title required"}), 400

    claims = get_jwt() or {}
    role = claims.get("role")
    if role not in {RoleEnum.ADMIN.value, RoleEnum.MANAGER.value}:
        return jsonify({"msg": "forbidden - only admin/manager may create tasks"}), 403

    creator_id = int(get_jwt_identity())

    try:
        task = Task(
            title=title,
            description=description,
            priority=PriorityEnum(priority),
            status=StatusEnum.PENDING,
            creator_id=creator_id,
            assignee_id=assignee_id
        )
    except Exception:
        try:
            task = Task(title=title, description=description, priority=PriorityEnum(priority.lower()), status=StatusEnum.PENDING, creator_id=creator_id, assignee_id=assignee_id)
        except Exception:
            task = Task(title=title, description=description, status=StatusEnum.PENDING, creator_id=creator_id, assignee_id=assignee_id)

    if data.get("due_date"):
        try:
            from datetime import datetime
            task.due_date = datetime.fromisoformat(data.get("due_date"))
        except Exception:
            pass

    db.session.add(task)
    db.session.commit()

    if assignee_id:
        assignee = db.session.get(User, int(assignee_id))
        if assignee:
            if (assignee.workload or 0) >= MAX_WORKLOAD:
                # rollback created task
                db.session.delete(task)
                db.session.commit()
                return jsonify({"msg": f"assignee has reached MAX_WORKLOAD ({MAX_WORKLOAD})"}), 400
            assignee.workload = (assignee.workload or 0) + 1
            task.status = StatusEnum.ASSIGNED
            db.session.commit()
            try:
                create_notification(assignee.id, f"New task assigned: {task.title} (id={task.id})")
            except Exception:
                pass

    return jsonify({"msg": "task created", "task_id": task.id}), 201


@bp.route("/auto-assign/<int:task_id>", methods=["POST"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value)
def auto_assign(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"msg": "task not found"}), 404
    if task.status != StatusEnum.PENDING:
        return jsonify({"msg": "only pending tasks can be auto-assigned"}), 400

    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    q = db.session.query(User).filter(User.role == RoleEnum.EMPLOYEE.value)
    if role == RoleEnum.MANAGER.value:
        q = q.filter_by(supervisor_id=caller_id)

    candidates = q.all()
    if not candidates:
        return jsonify({"msg": "no employees available to assign"}), 400

    chosen = find_best_assignee(candidates, MAX_WORKLOAD)
    if chosen is None:
        return jsonify({"msg": f"no available employees under MAX_WORKLOAD ({MAX_WORKLOAD})"}), 400

    task.assignee_id = chosen.id
    task.status = StatusEnum.ASSIGNED
    chosen.workload = (chosen.workload or 0) + 1
    db.session.commit()
    try:
        create_notification(chosen.id, f"New task assigned: {task.title} (id={task.id})")
    except Exception:
        pass

    return jsonify({"msg": "task auto-assigned", "task_id": task.id, "assignee_id": chosen.id}), 200


@bp.route("/assign", methods=["POST"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value)
def assign_manual():
    data = request.get_json() or {}
    task_id = data.get("task_id")
    assignee_id = data.get("assignee_id")
    if not task_id or not assignee_id:
        return jsonify({"msg": "task_id and assignee_id required"}), 400

    task = db.session.get(Task, int(task_id))
    if not task:
        return jsonify({"msg": "task not found"}), 404

    assignee = db.session.get(User, int(assignee_id))
    if not assignee:
        return jsonify({"msg": "assignee not found"}), 404

    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())
    if role == RoleEnum.MANAGER.value and assignee.supervisor_id != caller_id:
        return jsonify({"msg": "forbidden - can assign only to your direct reports"}), 403

    if (assignee.workload or 0) >= MAX_WORKLOAD:
        return jsonify({"msg": f"assignee has reached MAX_WORKLOAD ({MAX_WORKLOAD})"}), 400

    if task.assignee_id:
        prev = db.session.get(User, int(task.assignee_id))
        if prev and prev.workload:
            prev.workload = max(0, prev.workload - 1)

    task.assignee_id = assignee.id
    task.status = StatusEnum.ASSIGNED
    assignee.workload = (assignee.workload or 0) + 1
    db.session.commit()
    try:
        create_notification(assignee.id, f"New task assigned: {task.title} (id={task.id})")
    except Exception:
        pass

    return jsonify({"msg": "task assigned", "task_id": task.id, "assignee_id": assignee.id}), 200


@bp.route("/reassign", methods=["POST"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value)
def reassign_task():
    data = request.get_json() or {}
    task_id = data.get("task_id")
    new_assignee_id = data.get("new_assignee_id")
    force = bool(data.get("force", False))

    if not task_id or not new_assignee_id:
        return jsonify({"msg": "task_id and new_assignee_id required"}), 400

    task = db.session.get(Task, int(task_id))
    if not task:
        return jsonify({"msg": "task not found"}), 404

    new_assignee = db.session.get(User, int(new_assignee_id))
    if not new_assignee:
        return jsonify({"msg": "new assignee not found"}), 404

    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    if role == RoleEnum.MANAGER.value:
        if new_assignee.supervisor_id != caller_id:
            return jsonify({"msg": "forbidden - can reassign only to your direct reports"}), 403
        if task.assignee_id:
            prev = db.session.get(User, int(task.assignee_id))
            if prev and prev.supervisor_id != caller_id:
                return jsonify({"msg": "forbidden - cannot reassign tasks not under your team"}), 403

    if force and role != RoleEnum.ADMIN.value:
        return jsonify({"msg": "forbidden - only admin may force override"}), 403

    if task.assignee_id == new_assignee.id:
        return jsonify({"msg": "task already assigned to this user"}), 400

    if (new_assignee.workload or 0) >= MAX_WORKLOAD and not (force and role == RoleEnum.ADMIN.value):
        return jsonify({"msg": f"new assignee has reached MAX_WORKLOAD ({MAX_WORKLOAD})"}), 400

    prev_assignee = None
    if task.assignee_id:
        prev_assignee = db.session.get(User, int(task.assignee_id))
        if prev_assignee and prev_assignee.workload:
            prev_assignee.workload = max(0, prev_assignee.workload - 1)

    task.assignee_id = new_assignee.id
    if task.status == StatusEnum.PENDING:
        task.status = StatusEnum.ASSIGNED
    new_assignee.workload = (new_assignee.workload or 0) + 1
    db.session.commit()

    try:
        create_notification(new_assignee.id, f"Task {task.id} reassigned to you: {task.title}")
        if prev_assignee:
            create_notification(prev_assignee.id, f"Task {task.id} was reassigned from you to user {new_assignee.id}")
    except Exception:
        pass

    return jsonify({"msg": "task reassigned", "task_id": task.id, "new_assignee_id": new_assignee.id}), 200


@bp.route("/<int:user_id>", methods=["GET"])
@jwt_required()
def list_tasks_for_user(user_id):
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    if role == RoleEnum.MANAGER.value:
        candidate = db.session.get(User, user_id)
        if user_id != caller_id and (candidate is None or candidate.supervisor_id != caller_id):
            return jsonify({"msg": "forbidden"}), 403
    elif role == RoleEnum.EMPLOYEE.value:
        if user_id != caller_id:
            return jsonify({"msg": "forbidden"}), 403

    tasks = db.session.query(Task).filter_by(assignee_id=user_id).order_by(Task.id.desc()).all()
    out = []
    for t in tasks:
        out.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "priority": t.priority.value if t.priority else None,
            "status": t.status.value if t.status else None,
            "creator_id": t.creator_id,
            "assignee_id": t.assignee_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "due_date": t.due_date.isoformat() if t.due_date else None
        })
    return jsonify(out), 200


@bp.route("/start/<int:task_id>", methods=["POST"])
@jwt_required()
def start_task(task_id):
    caller_id = int(get_jwt_identity())
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"msg": "task not found"}), 404

    claims = get_jwt() or {}
    role = claims.get("role")
    if task.assignee_id != caller_id and role != RoleEnum.ADMIN.value:
        return jsonify({"msg": "forbidden - only assignee or admin can start task"}), 403

    if task.status not in {StatusEnum.ASSIGNED, StatusEnum.PENDING}:
        return jsonify({"msg": "task cannot be started from current status"}), 400

    task.status = StatusEnum.IN_PROGRESS
    db.session.commit()
    return jsonify({"msg": "task started", "task_id": task.id}), 200


@bp.route("/mark-complete/<int:task_id>", methods=["POST"])
@jwt_required()
def mark_complete(task_id):
    caller_id = int(get_jwt_identity())
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"msg": "task not found"}), 404
    if task.assignee_id != caller_id:
        return jsonify({"msg": "forbidden - only assignee can mark complete"}), 403
    if task.status == StatusEnum.COMPLETED:
        return jsonify({"msg": "task already completed"}), 400

    task.status = StatusEnum.COMPLETED
    assignee = db.session.get(User, caller_id)
    if assignee and assignee.workload:
        assignee.workload = max(0, assignee.workload - 1)

    dependents = db.session.query(TaskDependency).filter_by(prereq_id=task.id).all()

    unblocked = []
    for d in dependents:
        dep_task = db.session.get(Task, d.dependent_id)
        if not dep_task:
            continue


        prereq_edges = db.session.query(TaskDependency).filter_by(dependent_id=dep_task.id).all()
        still_blocked = False
        for pe in prereq_edges:
            ptask = db.session.get(Task, pe.prereq_id)
            if not ptask or ptask.status != StatusEnum.COMPLETED:
                still_blocked = True
                break


        if not still_blocked:

            try:
                is_blocked = (dep_task.status == StatusEnum.BLOCKED)
            except Exception:
                is_blocked = (str(dep_task.status).lower() == 'blocked')

            if is_blocked:
                dep_task.status = StatusEnum.PENDING
                unblocked.append(dep_task.id)
    db.session.commit()

    resp = {"msg": "task completed", "task_id": task.id}
    if unblocked:
        resp["unblocked"] = unblocked

    return jsonify(resp), 200


@bp.route("/by-priority", methods=["GET"])
@jwt_required()
def tasks_by_priority():
    q_status = request.args.get("status")
    claims = get_jwt() or {}
    role = claims.get("role")
    caller_id = int(get_jwt_identity())

    q = db.session.query(Task)
    if q_status:
        try:
            q = q.filter(Task.status == StatusEnum(q_status))
        except Exception:
            pass

    if role == RoleEnum.MANAGER.value:
        direct = db.session.query(User.id).filter_by(supervisor_id=caller_id).subquery()
        q = q.filter((Task.assignee_id.in_(direct)) | (Task.creator_id == caller_id))
    elif role == RoleEnum.EMPLOYEE.value:
        q = q.filter(Task.assignee_id == caller_id)

    tasks = q.all()
    tasks_sorted = sorted(tasks, key=lambda t: priority_value(t.priority.value if t.priority else None))
    out = [{
        "id": t.id,
        "title": t.title,
        "priority": t.priority.value if t.priority else None,
        "status": t.status.value if t.status else None,
        "assignee_id": t.assignee_id
    } for t in tasks_sorted]
    return jsonify(out), 200


@bp.route("/dependencies", methods=["POST"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value, RoleEnum.MANAGER.value)
def create_dependency():
    data = request.get_json() or {}
    prereq_id = data.get("prereq_id")
    dependent_id = data.get("dependent_id")
    if not prereq_id or not dependent_id:
        return jsonify({"msg": "prereq_id and dependent_id required"}), 400
    if int(prereq_id) == int(dependent_id):
        return jsonify({"msg": "prereq and dependent cannot be same"}), 400

    t_pr = db.session.get(Task, int(prereq_id))
    t_dep = db.session.get(Task, int(dependent_id))
    if not t_pr or not t_dep:
        return jsonify({"msg": "one or both tasks not found"}), 404

    exists_dep = db.session.query(TaskDependency).filter_by(prereq_id=prereq_id, dependent_id=dependent_id).first()
    if exists_dep:
        return jsonify({"msg": "dependency already exists"}), 409

    # gather pending tasks and existing dependencies, include new edge for cycle check
    pending_tasks = db.session.query(Task).filter(Task.status == StatusEnum.PENDING).all()
    all_deps = db.session.query(TaskDependency).all()
    deps_pairs = [(d.prereq_id, d.dependent_id) for d in all_deps]
    deps_pairs.append((int(prereq_id), int(dependent_id)))

    tg = TaskGraph(pending_tasks, deps_pairs)
    topo = tg.topological_sort()
    if topo is None:
        return jsonify({"msg": "adding this dependency would create a cycle"}), 400

    dep = TaskDependency(prereq_id=int(prereq_id), dependent_id=int(dependent_id))
    db.session.add(dep)
    try:
            # Check if any prerequisite for the dependent is not completed.
            prereq_edges = db.session.query(TaskDependency).filter_by(dependent_id=t_dep.id).all()
            still_blocked = False
            for pe in prereq_edges:
                ptask = db.session.get(Task, pe.prereq_id)
                if not ptask or ptask.status != StatusEnum.COMPLETED:
                    still_blocked = True
                    break

            # If any prereq is outstanding, mark the dependent as BLOCKED.
            if still_blocked:
                try:
                    t_dep.status = StatusEnum.BLOCKED
                except Exception:
                    # fallback if status is stored as plain string
                    t_dep.status = StatusEnum.BLOCKED

            db.session.commit()
    except Exception as e:
            db.session.rollback()
            return jsonify({"msg": "failed to persist dependency", "err": str(e)}), 500

    return jsonify({"msg": "dependency created", "prereq_id": prereq_id, "dependent_id": dependent_id}), 201

@bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
@role_required(RoleEnum.ADMIN.value)
def delete_task(task_id):
    
    """
    Admin-only: delete a task safely.
    - prevents deleting tasks that are already completed or in-progress (safety).
    - removes related TaskDependency rows.
    - adjusts assignee workload if applicable.
    """
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"msg": "task not found"}), 404

    # Prevent deletion of active/completed tasks (adjust if you want different policy)
    try:
        status_val = task.status if not hasattr(task.status, 'value') else task.status.value
    except Exception:
        status_val = str(task.status or '')
    if status_val in {StatusEnum.IN_PROGRESS.value, StatusEnum.COMPLETED.value}:
        return jsonify({"msg": f"cannot delete task with status '{status_val}'"}), 400

    try:
        # adjust assignee workload if currently assigned
        if task.assignee_id:
            assignee = db.session.get(User, int(task.assignee_id))
            if assignee and assignee.workload:
                assignee.workload = max(0, assignee.workload - 1)

        # delete dependencies that reference this task (both as prereq or dependent)
        db.session.query(TaskDependency).filter(
            (TaskDependency.prereq_id == task.id) | (TaskDependency.dependent_id == task.id)
        ).delete(synchronize_session=False)

        # finally delete the task
        db.session.delete(task)
        db.session.commit()
        return jsonify({"msg": "task deleted", "task_id": task_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "failed to delete task", "err": str(e)}), 500
