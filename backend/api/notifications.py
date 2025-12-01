from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.models import db, Notification
from backend.api._auth_helpers import role_required  

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

@bp.route("", methods=["GET"])
@jwt_required()
def list_notifications():
    uid = int(get_jwt_identity())
    unread_only = request.args.get("unread_only", None)
    q = db.session.query(Notification).filter_by(user_id=uid)
    if unread_only:
        q = q.filter_by(read=False)
    notifs = q.order_by(Notification.created_at.desc()).all()
    out = [{
        "id": n.id,
        "message": n.message,
        "read": n.read,
        "created_at": n.created_at.isoformat() if n.created_at else None
    } for n in notifs]
    return jsonify(out), 200

@bp.route("/mark-read", methods=["POST"])
@jwt_required()
def mark_read():
    uid = int(get_jwt_identity())
    data = request.get_json() or {}
    ids = data.get("ids")
    single = data.get("id")
    if single:
        ids = [single]
    if not ids:
        return jsonify({"msg":"id or ids required"}), 400

    updated = db.session.query(Notification).filter(Notification.user_id==uid, Notification.id.in_(ids)).update({"read": True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"msg":"marked", "count": updated}), 200
