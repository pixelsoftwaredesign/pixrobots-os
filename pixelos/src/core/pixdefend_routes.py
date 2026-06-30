from flask import Blueprint, request, jsonify, render_template
from .pixdefend import PixDefend

pixdefend_bp = Blueprint("pixdefend", __name__, url_prefix="/api/pixdefend")
_pd = PixDefend()


def register_pixdefend_routes(app):
    app.register_blueprint(pixdefend_bp)

    @app.route("/pixdefend")
    def pixdefend_page():
        return render_template("pixdefend.html", title="PixDefend")


@pixdefend_bp.route("/status")
def api_status():
    return jsonify(_pd.stats())


@pixdefend_bp.route("/pf")
def api_pf():
    return jsonify({"info": _pd.get_pf_status(), "rules": _pd.get_pf_rules()})


@pixdefend_bp.route("/blocked")
def api_blocked():
    return jsonify(_pd.list_blocked())


@pixdefend_bp.route("/block", methods=["POST"])
def api_block():
    data = request.get_json(force=True) or {}
    ip = data.get("ip", "")
    if not ip:
        return jsonify({"error": "ip required"}), 400
    return jsonify(_pd.block_ip(ip))


@pixdefend_bp.route("/unblock", methods=["POST"])
def api_unblock():
    data = request.get_json(force=True) or {}
    ip = data.get("ip", "")
    if not ip:
        return jsonify({"error": "ip required"}), 400
    return jsonify(_pd.unblock_ip(ip))


@pixdefend_bp.route("/unblock-all", methods=["POST"])
def api_unblock_all():
    return jsonify(_pd.unblock_all())


@pixdefend_bp.route("/reload", methods=["POST"])
def api_reload():
    return jsonify(_pd.reload_pf())


@pixdefend_bp.route("/check", methods=["POST"])
def api_check():
    data = request.get_json(silent=True) or {}
    stats_by_ip = data.get("stats", {})
    return jsonify({"alerts": _pd.check_and_block(stats_by_ip)})


@pixdefend_bp.route("/rate-limits")
def api_rate_limits():
    return jsonify(_pd.get_rate_limit_rules())


@pixdefend_bp.route("/generate")
def api_generate():
    return jsonify(_pd.apply_rate_limits())


@pixdefend_bp.route("/write-conf", methods=["POST"])
def api_write_conf():
    data = request.get_json(silent=True) or {}
    path = data.get("path", "")
    return jsonify(_pd.write_pf_conf(path))


@pixdefend_bp.route("/rule-files")
def api_rule_files():
    return jsonify(_pd.list_rule_files())


@pixdefend_bp.route("/rule-file/save", methods=["POST"])
def api_rule_file_save():
    data = request.get_json(force=True) or {}
    name = data.get("name", "custom.conf")
    content = data.get("content", "")
    return jsonify(_pd.save_rule_file(name, content))


@pixdefend_bp.route("/generate-conf")
def api_generate_conf():
    return jsonify({"conf": _pd.generate_pf_conf()})
