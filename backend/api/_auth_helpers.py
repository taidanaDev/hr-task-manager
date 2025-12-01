from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


def role_required(*allowed_roles):
    allowed_norm = {str(r).lower() for r in allowed_roles}
    def decorator(fn):
        @wraps(fn)


        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt() or {}
            role_claim = claims.get("role")

            if hasattr(role_claim, "value"):
                role = str(role_claim.value).lower()
            else:
                role = str(role_claim).lower() if role_claim is not None else None

            if role not in allowed_norm:
                return jsonify({"msg": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
