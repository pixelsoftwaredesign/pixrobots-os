from flask import Blueprint, request, jsonify, render_template
from .pixhal import PixHAL

pixhal_bp = Blueprint("pixhal", __name__, url_prefix="/api/pixhal")
_hal = PixHAL()


def register_pixhal_routes(app):
    app.register_blueprint(pixhal_bp)

    @app.route("/pixhal")
    def pixhal_page():
        return render_template("pixhal.html", title="PixHAL")


@pixhal_bp.route("/detect", methods=["POST"])
def api_detect():
    return jsonify(_hal.detect_all())


@pixhal_bp.route("/devices")
def api_devices():
    return jsonify(_hal.list_devices())


@pixhal_bp.route("/sensor/<sensor_id>/read")
def api_sensor_read(sensor_id):
    val = _hal.read_sensor(sensor_id)
    if val is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(val)


@pixhal_bp.route("/actuator/<actuator_id>/write", methods=["POST"])
def api_actuator_write(actuator_id):
    data = request.get_json(force=True) or {}
    return jsonify(_hal.write_actuator(actuator_id, data.get("state", 0)))


@pixhal_bp.route("/system")
def api_system():
    return jsonify(_hal.get_system_info())


@pixhal_bp.route("/stats")
def api_stats():
    return jsonify(_hal.stats())
