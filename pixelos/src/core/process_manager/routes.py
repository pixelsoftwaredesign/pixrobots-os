from flask import jsonify, request, render_template
from .pixmanager import PixManager

pm = PixManager()


def register_process_manager_routes(app):

    @app.route("/processes")
    def processes_page():
        return render_template("processes.html", title="Gestionnaire de Processus")

    # ── List ──────────────────────────────────────────────

    @app.route("/api/processes")
    def api_processes_list():
        sort = request.args.get("sort", "cpu")
        limit = request.args.get("limit", 50, type=int)
        return jsonify(pm.list_processes(sort_by=sort, limit=limit))

    @app.route("/api/processes/<int:pid>")
    def api_process_get(pid):
        return jsonify(pm.get_process(pid))

    @app.route("/api/processes/stats")
    def api_processes_stats():
        return jsonify(pm.stats())

    @app.route("/api/processes/resource-summary")
    def api_processes_resource():
        return jsonify(pm.resource_summary())

    # ── Kill ──────────────────────────────────────────────

    @app.route("/api/processes/<int:pid>/kill", methods=["POST"])
    def api_process_kill(pid):
        data = request.get_json(silent=True) or {}
        sig = data.get("signal", 15)
        return jsonify(pm.kill_process(pid, sig))

    @app.route("/api/processes/kill-by-name", methods=["POST"])
    def api_process_kill_name():
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "name required"}), 400
        sig = data.get("signal", 15)
        return jsonify(pm.kill_by_name(data["name"], sig))

    @app.route("/api/processes/kill-low-priority", methods=["POST"])
    def api_process_kill_low():
        data = request.get_json(silent=True) or {}
        max_prio = data.get("max_priority", 20)
        return jsonify(pm.kill_all_by_priority(max_prio))

    @app.route("/api/processes/kill-by-memory", methods=["POST"])
    def api_process_kill_mem():
        data = request.get_json(silent=True) or {}
        threshold = data.get("threshold_mb", 500)
        return jsonify(pm.kill_by_memory(threshold))

    # ── Trace ─────────────────────────────────────────────

    @app.route("/api/processes/<int:pid>/trace", methods=["POST"])
    def api_process_trace(pid):
        data = request.get_json(silent=True) or {}
        duration = data.get("duration", 15)
        return jsonify(pm.trace_process(pid, duration))

    @app.route("/api/processes/<int:pid>/trace-stop", methods=["POST"])
    def api_process_trace_stop(pid):
        return jsonify(pm.trace_stop(pid))

    # ── New process detection ─────────────────────────────

    @app.route("/api/processes/new")
    def api_processes_new():
        since = request.args.get("since")
        return jsonify(pm.get_new_processes(since))

    @app.route("/api/processes/detect", methods=["POST"])
    def api_processes_detect():
        return jsonify(pm.detect_new_processes())

    # ── Monitoring ────────────────────────────────────────

    @app.route("/api/processes/monitor/start", methods=["POST"])
    def api_processes_monitor_start():
        data = request.get_json(silent=True) or {}
        interval = data.get("interval", 5)
        return jsonify(pm.start_monitoring(interval))

    @app.route("/api/processes/monitor/stop", methods=["POST"])
    def api_processes_monitor_stop():
        return jsonify(pm.stop_monitoring())

    @app.route("/api/processes/monitor/status")
    def api_processes_monitor_status():
        return jsonify(pm.monitoring_status())

    # ── Whitelist ─────────────────────────────────────────

    @app.route("/api/processes/whitelist")
    def api_processes_whitelist():
        return jsonify(pm.whitelist_list())

    @app.route("/api/processes/whitelist/add", methods=["POST"])
    def api_processes_whitelist_add():
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "name required"}), 400
        cat = data.get("category", "custom")
        return jsonify(pm.whitelist_add(data["name"], cat))

    @app.route("/api/processes/whitelist/remove", methods=["POST"])
    def api_processes_whitelist_remove():
        data = request.get_json()
        if not data or not data.get("name"):
            return jsonify({"error": "name required"}), 400
        return jsonify(pm.whitelist_remove(data["name"]))
