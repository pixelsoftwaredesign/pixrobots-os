from flask import Blueprint, request, jsonify, render_template
from .pixkey import PixKey

pixkey_bp = Blueprint("pixkey", __name__, url_prefix="/api/pixkey")
_pk = PixKey()


def register_pixkey_routes(app):
    app.register_blueprint(pixkey_bp)

    @app.route("/pixkey")
    def pixkey_page():
        return render_template("pixkey.html", title="PixKey")


@pixkey_bp.route("/status")
def api_status():
    return jsonify({"authenticated": _pk.is_authenticated(), **__import__("copy").deepcopy(_pk.stats())})


@pixkey_bp.route("/authenticate", methods=["POST"])
def api_authenticate():
    data = request.get_json(force=True) or {}
    return jsonify(_pk.authenticate(
        method=data.get("method", "yubikey"),
        password=data.get("password", ""),
        key_id=data.get("key_id", ""),
        token=data.get("token", ""),
    ))


@pixkey_bp.route("/logout", methods=["POST"])
def api_logout():
    return jsonify(_pk.logout())


@pixkey_bp.route("/sign", methods=["POST"])
def api_sign():
    data = request.get_json(force=True) or {}
    return jsonify(_pk.sign(data.get("data", {})))


@pixkey_bp.route("/register/yubikey", methods=["POST"])
def api_register_yubikey():
    data = request.get_json(force=True) or {}
    return jsonify(_pk.register_yubikey(data.get("serial", ""), data.get("label", "")))


@pixkey_bp.route("/register/recovery", methods=["POST"])
def api_register_recovery():
    data = request.get_json(force=True) or {}
    return jsonify(_pk.register_recovery_key(data.get("password", ""), data.get("label", "")))


@pixkey_bp.route("/register/token", methods=["POST"])
def api_register_token():
    data = request.get_json(force=True) or {}
    return jsonify(_pk.register_token(data.get("token_id", ""), data.get("label", "")))


@pixkey_bp.route("/keys")
def api_keys():
    return jsonify(_pk.list_keys())


@pixkey_bp.route("/key/<key_id>/remove", methods=["POST"])
def api_key_remove(key_id):
    return jsonify(_pk.remove_key(key_id))


@pixkey_bp.route("/stats")
def api_stats():
    return jsonify(_pk.stats())
