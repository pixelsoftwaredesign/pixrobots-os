from flask import Blueprint, request, jsonify, render_template
from .pixdht import PixDHTQueryEngine

pixdht_bp = Blueprint("pixdht", __name__, url_prefix="/api/pixdht")
_dht_qe = PixDHTQueryEngine()


def register_pixdht_routes(app):
    app.register_blueprint(pixdht_bp)

    @app.route("/pixdht")
    def pixdht_page():
        return render_template("pixdht.html", title="PixDHT Query Engine")


@pixdht_bp.route("/query", methods=["POST"])
def api_query():
    data = request.get_json(force=True) or {}
    stmt = data.get("statement", "")
    if not stmt:
        return jsonify({"error": "statement required"}), 400
    return jsonify(_dht_qe.query(stmt))


@pixdht_bp.route("/index", methods=["POST"])
def api_index():
    data = request.get_json(force=True) or {}
    ns = data.get("namespace", "default")
    key = data.get("key", "")
    value = data.get("data", {})
    if not key:
        return jsonify({"error": "key required"}), 400
    return jsonify(_dht_qe.index_data(ns, key, value))


@pixdht_bp.route("/index/<namespace>")
def api_index_list(namespace):
    return jsonify(_dht_qe.list_indexed(namespace))


@pixdht_bp.route("/index/<namespace>/<key>", methods=["DELETE"])
def api_index_delete(namespace, key):
    return jsonify(_dht_qe.delete_index(namespace, key))


@pixdht_bp.route("/namespaces")
def api_namespaces():
    return jsonify(_dht_qe.list_namespaces())


@pixdht_bp.route("/bulk-index", methods=["POST"])
def api_bulk_index():
    data = request.get_json(force=True) or {}
    ns = data.get("namespace", "default")
    entries = data.get("entries", [])
    return jsonify(_dht_qe.bulk_index(ns, entries))


@pixdht_bp.route("/export/<namespace>")
def api_export(ns):
    return jsonify(_dht_qe.export_namespace(ns))


@pixdht_bp.route("/import/<namespace>", methods=["POST"])
def api_import(ns):
    data = request.get_json(force=True) or {}
    return jsonify(_dht_qe.import_namespace(ns, data.get("data", {})))


@pixdht_bp.route("/dht/identity")
def api_dht_identity():
    return jsonify(_dht_qe.dht_identity())


@pixdht_bp.route("/dht/store", methods=["POST"])
def api_dht_store():
    data = request.get_json(force=True) or {}
    return jsonify(_dht_qe.dht_store(data.get("key", ""), data.get("value", {})))


@pixdht_bp.route("/dht/get")
def api_dht_get():
    key = request.args.get("key", "")
    return jsonify(_dht_qe.dht_get(key) or {})


@pixdht_bp.route("/dht/find")
def api_dht_find():
    key = request.args.get("key", "")
    count = request.args.get("count", 10, type=int)
    return jsonify(_dht_qe.dht_find_peers(key, count))


@pixdht_bp.route("/resolve/hns")
def api_resolve_hns():
    name = request.args.get("name", "")
    return jsonify(_dht_qe.resolve_hns(name) or {})


@pixdht_bp.route("/resolve/ens")
def api_resolve_ens():
    name = request.args.get("name", "")
    return jsonify(_dht_qe.resolve_ens(name) or {})


@pixdht_bp.route("/resolve/pixel")
def api_resolve_pixel():
    name = request.args.get("name", "")
    return jsonify(_dht_qe.resolve_pixel(name) or {})


@pixdht_bp.route("/stats")
def api_stats():
    return jsonify(_dht_qe.stats())
