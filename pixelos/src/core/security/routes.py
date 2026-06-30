# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
from flask import jsonify, request, render_template
from .pixstat import PixStat
from .pixdefend import PixDefend
from .pixscudo import PixScudo
from .pixprobe import PixProbe
from .traffic_profiler import TrafficProfiler


pixstat = PixStat()
pixdefend = PixDefend()
pixscudo = PixScudo()
pixprobe = PixProbe()
traffic_profiler = TrafficProfiler()


def register_security_routes(app):

    @app.route("/security")
    def security_page():
        return render_template("security.html", title="Sécurité & Défense")

    # ── PixStat ──────────────────────────────────────────────

    @app.route("/api/security/stats")
    def api_security_stats():
        return jsonify(pixstat.summary())

    @app.route("/api/security/connections")
    def api_security_connections():
        return jsonify(pixstat.get_connections())

    @app.route("/api/security/interfaces")
    def api_security_interfaces():
        return jsonify(pixstat.get_interfaces())

    @app.route("/api/security/routes")
    def api_security_routes():
        return jsonify(pixstat.get_routes())

    @app.route("/api/security/bandwidth")
    def api_security_bandwidth():
        iface = request.args.get("iface", "vio0")
        return jsonify(pixstat.get_bandwidth(iface))

    # ── PixDefend ────────────────────────────────────────────

    @app.route("/api/security/defend/status")
    def api_defend_status():
        return jsonify(pixdefend.stats())

    @app.route("/api/security/defend/pf")
    def api_defend_pf():
        return jsonify({"info": pixdefend.get_pf_status(), "rules": pixdefend.get_pf_rules()})

    @app.route("/api/security/defend/blocked")
    def api_defend_blocked():
        return jsonify(pixdefend.list_blocked())

    @app.route("/api/security/defend/block", methods=["POST"])
    def api_defend_block():
        data = request.get_json()
        if not data or not data.get("ip"):
            return jsonify({"error": "ip required"}), 400
        return jsonify(pixdefend.block_ip(data["ip"]))

    @app.route("/api/security/defend/unblock", methods=["POST"])
    def api_defend_unblock():
        data = request.get_json()
        if not data or not data.get("ip"):
            return jsonify({"error": "ip required"}), 400
        return jsonify(pixdefend.unblock_ip(data["ip"]))

    @app.route("/api/security/defend/reload", methods=["POST"])
    def api_defend_reload():
        return jsonify(pixdefend.reload_pf())

    @app.route("/api/security/defend/check", methods=["POST"])
    def api_defend_check():
        data = request.get_json(silent=True) or {}
        stats_by_ip = data.get("stats", {})
        return jsonify({"alerts": pixdefend.check_and_block(stats_by_ip)})

    # ── PixScudo ─────────────────────────────────────────────

    @app.route("/api/security/scudo/summary")
    def api_scudo_summary():
        return jsonify(pixscudo.summary())

    @app.route("/api/security/scudo/audit", methods=["POST"])
    def api_scudo_audit():
        return jsonify(pixscudo.run_full_audit())

    @app.route("/api/security/scudo/patches")
    def api_scudo_patches():
        return jsonify(pixscudo.check_syspatch())

    @app.route("/api/security/scudo/packages")
    def api_scudo_packages():
        return jsonify(pixscudo.check_packages())

    @app.route("/api/security/scudo/integrity")
    def api_scudo_integrity():
        return jsonify(pixscudo.verify_integrity())

    @app.route("/api/security/scudo/ssh")
    def api_scudo_ssh():
        return jsonify(pixscudo.check_ssh())

    @app.route("/api/security/scudo/permissions")
    def api_scudo_permissions():
        return jsonify(pixscudo.check_permissions())

    @app.route("/api/security/scudo/ports")
    def api_scudo_ports():
        return jsonify(pixscudo.check_open_ports())

    # ── PixProbe ─────────────────────────────────────────────

    @app.route("/api/security/probe/summary")
    def api_probe_summary():
        return jsonify(pixprobe.summary())

    @app.route("/api/security/probe/connections", methods=["POST"])
    def api_probe_connections():
        data = request.get_json(silent=True) or {}
        conns = data.get("connections", [])
        return jsonify(pixprobe.analyze_connections(conns))

    @app.route("/api/security/probe/tcpdump")
    def api_probe_tcpdump():
        count = request.args.get("count", 50, type=int)
        iface = request.args.get("iface", "vio0")
        return jsonify(pixprobe.analyze_by_tcpdump(count, iface))

    @app.route("/api/security/probe/lsof")
    def api_probe_lsof():
        return jsonify(pixprobe.analyze_by_lsof())

    @app.route("/api/security/probe/classify")
    def api_probe_classify():
        port = request.args.get("port", type=int)
        if not port:
            return jsonify({"error": "port required"}), 400
        proto = pixprobe.classify_by_port(port)
        info = pixprobe.get_protocol_info(proto)
        return jsonify({"port": port, "protocol": proto, "info": info})

    # ── TrafficProfiler ──────────────────────────────────────

    @app.route("/api/security/profiler/status")
    def api_profiler_status():
        return jsonify(traffic_profiler.status())

    @app.route("/api/security/profiler/start", methods=["POST"])
    def api_profiler_start():
        data = request.get_json(silent=True) or {}
        hours = data.get("hours", 24)
        return jsonify(traffic_profiler.start_learning(hours))

    @app.route("/api/security/profiler/stop", methods=["POST"])
    def api_profiler_stop():
        return jsonify(traffic_profiler.stop_learning())

    @app.route("/api/security/profiler/sample", methods=["POST"])
    def api_profiler_sample():
        data = request.get_json(silent=True) or {}
        proto = data.get("protocol_data", {})
        return jsonify(traffic_profiler.collect_sample(proto))

    @app.route("/api/security/profiler/anomalies", methods=["GET"])
    def api_profiler_anomalies():
        return jsonify(traffic_profiler.detect_anomalies())

    @app.route("/api/security/profiler/progress")
    def api_profiler_progress():
        return jsonify(traffic_profiler.learning_progress())

    @app.route("/api/security/profiler/reset", methods=["POST"])
    def api_profiler_reset():
        return jsonify(traffic_profiler.reset_profile())
