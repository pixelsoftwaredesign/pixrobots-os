from flask import Blueprint, request, jsonify, render_template
from .pixstat import PixStat

pixstat_bp = Blueprint("pixstat", __name__, url_prefix="/api/pixstat")
_ps = PixStat()


def register_pixstat_routes(app):
    app.register_blueprint(pixstat_bp)

    @app.route("/pixstat")
    def pixstat_page():
        return render_template("pixstat.html", title="PixStat / Heartbeat")


@pixstat_bp.route("/summary")
def api_summary():
    return jsonify(_ps.summary())


@pixstat_bp.route("/snapshot")
def api_snapshot():
    return jsonify(_ps.snapshot())


@pixstat_bp.route("/connections")
def api_connections():
    return jsonify(_ps.get_connections())


@pixstat_bp.route("/interfaces")
def api_interfaces():
    return jsonify(_ps.get_interfaces())


@pixstat_bp.route("/bandwidth")
def api_bandwidth():
    iface = request.args.get("iface", "vio0")
    return jsonify(_ps.get_bandwidth(iface))


@pixstat_bp.route("/cpu")
def api_cpu():
    return jsonify(_ps.get_cpu())


@pixstat_bp.route("/memory")
def api_memory():
    return jsonify(_ps.get_memory())


@pixstat_bp.route("/disk")
def api_disk():
    return jsonify(_ps.get_disk())


@pixstat_bp.route("/uptime")
def api_uptime():
    return jsonify(_ps.get_uptime())


@pixstat_bp.route("/temperature")
def api_temperature():
    return jsonify(_ps.get_temp())


@pixstat_bp.route("/heartbeat/send", methods=["POST"])
def api_heartbeat_send():
    return jsonify(_ps.send_heartbeat_now())


@pixstat_bp.route("/history")
def api_history():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_ps.get_history(limit))


@pixstat_bp.route("/history/clear", methods=["POST"])
def api_history_clear():
    return jsonify(_ps.clear_history())


@pixstat_bp.route("/alerts")
def api_alerts():
    return jsonify(_ps.get_alerts())


@pixstat_bp.route("/stats")
def api_stats():
    return jsonify(_ps.stats())
