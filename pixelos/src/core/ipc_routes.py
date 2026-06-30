# Pixel Software Design — Copyright 2026
from flask import Blueprint, request, jsonify, render_template
from .ipc import MessageBus, Message, MSG_TYPE_COMMAND, MODULE_STATUSES

ipc_bp = Blueprint("ipc", __name__, url_prefix="/api/ipc")
_bus = MessageBus()


def register_ipc_routes(app):
    app.register_blueprint(ipc_bp)

    @app.route("/ipc")
    def ipc_page():
        return render_template("ipc.html", title="IPC Bus")


@ipc_bp.route("/status")
def api_ipc_status():
    return jsonify(_bus.stats())


@ipc_bp.route("/modules")
def api_ipc_modules():
    return jsonify(_bus.get_modules())


@ipc_bp.route("/module/<name>")
def api_ipc_module(name):
    m = _bus.get_module(name)
    if not m:
        return jsonify({"error": "not found"}), 404
    return jsonify(m)


@ipc_bp.route("/send", methods=["POST"])
def api_ipc_send():
    data = request.get_json(force=True) or {}
    target = data.get("target", "")
    command = data.get("command", "")
    params = data.get("params", {})
    if not target or not command:
        return jsonify({"error": "target and command required"}), 400
    ok = _bus.send_command(target, command, params)
    return jsonify({"sent": ok, "target": target, "command": command})


@ipc_bp.route("/publish", methods=["POST"])
def api_ipc_publish():
    data = request.get_json(force=True) or {}
    msg = Message(
        msg_type=data.get("type", "event"),
        source=data.get("source", "api"),
        target=data.get("target", ""),
        payload=data.get("payload", {}),
    )
    _bus.publish(msg)
    return jsonify({"published": True, "msg_id": msg.msg_id})


@ipc_bp.route("/module-statuses")
def api_ipc_statuses():
    return jsonify(MODULE_STATUSES)
