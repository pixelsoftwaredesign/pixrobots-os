from flask import Blueprint, request, jsonify, render_template
from .pixbackup import PixBackup

backup_bp = Blueprint("backup", __name__, url_prefix="/api/backup")
_b = PixBackup()


def register_backup_routes(app):
    app.register_blueprint(backup_bp)

    @app.route("/backup")
    def backup_page():
        return render_template("backup.html", title="PixBackup")


@backup_bp.route("/backup", methods=["POST"])
def api_backup():
    data = request.get_json(force=True) or {}
    source = data.get("path", "")
    label = data.get("label", "")
    if not source:
        return jsonify({"error": "path required"}), 400
    return jsonify(_b.backup(source, label))


@backup_bp.route("/restore", methods=["POST"])
def api_restore():
    data = request.get_json(force=True) or {}
    bid = data.get("backup_id", "")
    out = data.get("output", "")
    if not bid:
        return jsonify({"error": "backup_id required"}), 400
    return jsonify(_b.restore(bid, out))


@backup_bp.route("/distribute", methods=["POST"])
def api_distribute():
    data = request.get_json(force=True) or {}
    bid = data.get("backup_id", "")
    peers = data.get("peers", [])
    return jsonify(_b.distribute(bid, peers))


@backup_bp.route("/list")
def api_list():
    return jsonify(_b.list_backups())


@backup_bp.route("/get/<backup_id>")
def api_get(backup_id):
    b = _b.get_backup(backup_id)
    if not b:
        return jsonify({"error": "not found"}), 404
    return jsonify(b)


@backup_bp.route("/delete/<backup_id>", methods=["POST"])
def api_delete(backup_id):
    return jsonify(_b.delete_backup(backup_id))


@backup_bp.route("/key")
def api_key():
    return jsonify(_b.get_key())


@backup_bp.route("/key/export", methods=["POST"])
def api_key_export():
    data = request.get_json(force=True) or {}
    out = data.get("output", "")
    return jsonify({"path": _b.export_key(out)})


@backup_bp.route("/key/import", methods=["POST"])
def api_key_import():
    data = request.get_json(force=True) or {}
    return jsonify(_b.import_key(data.get("path", "")))


@backup_bp.route("/stats")
def api_stats():
    return jsonify(_b.stats())
