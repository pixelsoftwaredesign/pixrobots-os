# Pixel Software Design — Copyright 2026
from flask import Blueprint, request, jsonify, render_template

from .pixauto import PixAuto

pixauto_bp = Blueprint("pixauto", __name__, url_prefix="/api/pixauto")
_pa = PixAuto()


def register_pixauto_routes(app):
    app.register_blueprint(pixauto_bp)

    @app.route("/pixauto")
    def pixauto_page():
        return render_template("pixauto.html", title="PixAuto")


@pixauto_bp.route("/parse", methods=["POST"])
def api_parse():
    data = request.get_json(force=True) or {}
    return jsonify(_pa.parse_natural_language(data.get("text", "")))


@pixauto_bp.route("/compile", methods=["POST"])
def api_compile():
    data = request.get_json(force=True) or {}
    return jsonify(_pa.compile(data.get("text", "")))


@pixauto_bp.route("/execute-nl", methods=["POST"])
def api_execute_nl():
    data = request.get_json(force=True) or {}
    text = data.get("nl", data.get("text", ""))
    if not text:
        return jsonify({"error": "text required"}), 400
    result = _pa.add_rule(text)
    if result.get("status") == "added":
        rule = result["rule"]
        exec_result = _pa.execute_rule(rule["id"])
        return jsonify({"parsed": rule["parsed"], "compiled": rule, "execution": exec_result})
    return jsonify(result)


@pixauto_bp.route("/recipes")
def api_recipes():
    return jsonify(_pa.get_rules())


@pixauto_bp.route("/execute", methods=["POST"])
def api_execute_by_name():
    data = request.get_json(force=True) or {}
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "name required"}), 400
    results = []
    for r in _pa.get_rules():
        if r.get("id") == name or r.get("original", "").lower() == name.lower():
            results.append(_pa.execute_rule(r["id"]))
    return jsonify({"executed": len(results), "results": results})


@pixauto_bp.route("/logs")
def api_logs():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(_pa.get_history(limit))


@pixauto_bp.route("/logs/clear", methods=["POST"])
def api_logs_clear():
    return jsonify(_pa.clear_history())


@pixauto_bp.route("/rule/add", methods=["POST"])
def api_rule_add():
    data = request.get_json(force=True) or {}
    return jsonify(_pa.add_rule(data.get("text", "")))


@pixauto_bp.route("/rules")
def api_rules():
    return jsonify(_pa.get_rules())


@pixauto_bp.route("/rule/<rule_id>")
def api_rule_get(rule_id):
    r = _pa.get_rule(rule_id)
    if not r:
        return jsonify({"error": "not found"}), 404
    return jsonify(r)


@pixauto_bp.route("/rule/<rule_id>/toggle", methods=["POST"])
def api_rule_toggle(rule_id):
    return jsonify(_pa.toggle_rule(rule_id))


@pixauto_bp.route("/rule/<rule_id>/delete", methods=["POST"])
def api_rule_delete(rule_id):
    return jsonify(_pa.delete_rule(rule_id))


@pixauto_bp.route("/rule/<rule_id>", methods=["PUT"])
def api_rule_update(rule_id):
    data = request.get_json(force=True) or {}
    return jsonify(_pa.update_rule(rule_id, data))


@pixauto_bp.route("/execute/<rule_id>", methods=["POST"])
def api_execute(rule_id):
    data = request.get_json(force=True) or {}
    sensors = data.get("sensor_values", {})
    return jsonify(_pa.execute_rule(rule_id, sensors))


@pixauto_bp.route("/execute-all", methods=["POST"])
def api_execute_all():
    results = {}
    for r in _pa.get_rules():
        if r.get("enabled", True):
            results[r["id"]] = _pa.execute_rule(r["id"])
    return jsonify({"triggered_count": sum(1 for v in results.values() if v.get("triggered")),
                     "results": results})


@pixauto_bp.route("/stats")
def api_stats():
    return jsonify(_pa.stats())


@pixauto_bp.route("/sensors", methods=["GET"])
def api_sensors():
    return jsonify(_pa._read_real_sensors())


@pixauto_bp.route("/export")
def api_export():
    fmt = request.args.get("format", "json")
    rules = _pa.export_rules()
    if fmt == "json":
        return jsonify({"count": len(rules), "rules": rules})
    return jsonify({"error": "unsupported format"}), 400


@pixauto_bp.route("/import", methods=["POST"])
def api_import():
    data = request.get_json(force=True) or {}
    rules_data = data.get("rules", [])
    if isinstance(rules_data, str):
        try:
            import json
            rules_data = json.loads(rules_data)
        except Exception:
            return jsonify({"error": "invalid JSON"}), 400
    return jsonify(_pa.import_rules(rules_data))


@pixauto_bp.route("/webhooks", methods=["POST"])
def api_webhook():
    """
    Generic webhook receiver for external services to trigger PixAuto rules.
    POST a JSON body; matching rules will be evaluated against the payload.
    """
    data = request.get_json(force=True) or {}
    results = []
    for r in _pa.get_rules():
        if r.get("enabled", True):
            # Pass the webhook data as sensor_values
            exec_result = _pa.execute_rule(r["id"], data)
            results.append({"rule_id": r["id"], "triggered": exec_result.get("triggered")})
    return jsonify({"results": results})
