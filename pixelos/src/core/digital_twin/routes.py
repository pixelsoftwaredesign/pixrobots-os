# Pixel Software Design — Copyright 2026
from flask import Blueprint, request, jsonify, render_template
from .twin import DigitalTwin

twin_bp = Blueprint("digital_twin", __name__, url_prefix="/api/twin")
_dt = DigitalTwin()


def register_twin_routes(app):
    app.register_blueprint(twin_bp)

    @app.route("/digital-twin")
    def twin_page():
        return render_template("digital_twin.html", title="Digital Twin")


@twin_bp.route("/list")
def api_twin_list():
    return jsonify(_dt.list())


@twin_bp.route("/<twin_id>")
def api_twin_get(twin_id):
    t = _dt.get(twin_id)
    if not t:
        return jsonify({"error": "not found"}), 404
    return jsonify(t)


@twin_bp.route("/create", methods=["POST"])
def api_twin_create():
    data = request.get_json(force=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name required"}), 400
    return jsonify(_dt.create(
        data["name"], data.get("type", "equipment"), data.get("metadata", {})))


@twin_bp.route("/<twin_id>/delete", methods=["POST"])
def api_twin_delete(twin_id):
    return jsonify(_dt.delete(twin_id))


@twin_bp.route("/<twin_id>/sync-sensor", methods=["POST"])
def api_twin_sync_sensor(twin_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dt.sync_sensor(
        twin_id, data.get("sensor_id", ""),
        data.get("value", 0), data.get("unit", "")))


@twin_bp.route("/<twin_id>/sync-actuator", methods=["POST"])
def api_twin_sync_actuator(twin_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dt.sync_actuator(
        twin_id, data.get("actuator_id", ""), data.get("state", "off")))


@twin_bp.route("/<twin_id>/sync-state", methods=["POST"])
def api_twin_sync_state(twin_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dt.sync_state(twin_id, data.get("state", {})))


@twin_bp.route("/<twin_id>/simulate", methods=["POST"])
def api_twin_simulate(twin_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dt.simulate(
        twin_id, data.get("scenario", "normal"), data.get("params", {})))


@twin_bp.route("/<twin_id>/health")
def api_twin_health(twin_id):
    return jsonify(_dt.health_check(twin_id))


@twin_bp.route("/<twin_id>/history")
def api_twin_history(twin_id):
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_dt.history(twin_id, limit))


@twin_bp.route("/<twin_id>/thresholds", methods=["POST"])
def api_twin_thresholds(twin_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dt.set_threshold(
        twin_id, data.get("sensor_id", ""),
        data.get("min"), data.get("max")))


@twin_bp.route("/stats")
def api_twin_stats():
    return jsonify(_dt.stats())
