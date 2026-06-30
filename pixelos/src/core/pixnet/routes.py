from flask import Blueprint, request, jsonify, render_template
from .pixcrawler import PixCrawler
from .pixsearch import PixSearch
from .pixtrust import PixTrust
from .pixmesh import PixMesh
from .pixdht import PixDHT

pixnet_bp = Blueprint("pixnet", __name__, url_prefix="/api/pixnet")

_crawler = PixCrawler()
_trust = PixTrust()
_mesh = PixMesh()
_dht = PixDHT()
_search = PixSearch(crawler=_crawler, trust=_trust, mesh=_mesh)


def register_pixnet_routes(app):
    app.register_blueprint(pixnet_bp)

    @app.route("/pixnet")
    def pixnet_page():
        return render_template("pixnet.html", title="PixNet — Internet Souverain")


# ── Crawler ────────────────────────────────────────────────

@pixnet_bp.route("/crawl", methods=["POST"])
def api_crawl():
    data = request.get_json(force=True) or {}
    cid = data.get("cid", "")
    depth = data.get("depth", 2)
    if cid:
        return jsonify(_crawler.crawl(cid, depth))
    return jsonify(_crawler.crawl_seeds(depth))


@pixnet_bp.route("/crawler/start", methods=["POST"])
def api_crawler_start():
    data = request.get_json(force=True) or {}
    return jsonify(_crawler.start(
        interval=data.get("interval", 3600),
        depth=data.get("depth", 2),
    ))


@pixnet_bp.route("/crawler/stop", methods=["POST"])
def api_crawler_stop():
    return jsonify(_crawler.stop())


@pixnet_bp.route("/crawler/stats")
def api_crawler_stats():
    return jsonify(_crawler.stats())


@pixnet_bp.route("/crawler/index")
def api_crawler_index():
    q = request.args.get("q", "")
    ctype = request.args.get("type", "")
    limit = request.args.get("limit", 100, type=int)
    if q:
        return jsonify(_crawler.get_by_keyword(q, limit))
    if ctype:
        return jsonify(_crawler.get_by_type(ctype, limit))
    return jsonify(_crawler.get_recent(limit))


@pixnet_bp.route("/crawler/clear", methods=["POST"])
def api_crawler_clear():
    return jsonify(_crawler.clear_index())


# ── Search ─────────────────────────────────────────────────

@pixnet_bp.route("/search")
def api_search():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 30, type=int)
    peers = request.args.get("peers", "true").lower() == "true"
    if not q:
        return jsonify({"error": "query required"}), 400
    return jsonify(_search.search(q, limit=limit, include_peers=peers))


@pixnet_bp.route("/search/local")
def api_search_local():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 30, type=int)
    if not q:
        return jsonify({"error": "query required"}), 400
    return jsonify({"results": _search.search_local(q, limit)})


@pixnet_bp.route("/search/trending")
def api_search_trending():
    return jsonify(_search.trending(20))


@pixnet_bp.route("/search/stats")
def api_search_stats():
    return jsonify(_search.stats())


@pixnet_bp.route("/search/clear-cache", methods=["POST"])
def api_search_clear():
    return jsonify(_search.clear_cache())


# ── Trust ──────────────────────────────────────────────────

@pixnet_bp.route("/trust/node/<node_id>")
def api_trust_node(node_id):
    return jsonify(_trust.get_reputation(node_id))


@pixnet_bp.route("/trust/node/<node_id>/certify", methods=["POST"])
def api_trust_certify(node_id):
    data = request.get_json(force=True) or {}
    level = data.get("level", 1)
    certifier = data.get("certifier", "")
    return jsonify(_trust.set_certification(node_id, level, certifier))


@pixnet_bp.route("/trust/node/<node_id>/vouch", methods=["POST"])
def api_trust_vouch(node_id):
    data = request.get_json(force=True) or {}
    voter = data.get("voter", _dht.node_id[:16])
    return jsonify(_trust.vouch(voter, node_id))


@pixnet_bp.route("/trust/score-content", methods=["POST"])
def api_trust_score():
    data = request.get_json(force=True) or {}
    return jsonify({"score": _trust.score_content(data)})


@pixnet_bp.route("/trust/stats")
def api_trust_stats():
    return jsonify(_trust.stats())


@pixnet_bp.route("/trust/peers/rank", methods=["POST"])
def api_trust_rank():
    data = request.get_json(force=True) or {}
    peers = data.get("peers", [])
    return jsonify({"ranked": _trust.rank_peers(peers)})


# ── Mesh ───────────────────────────────────────────────────

@pixnet_bp.route("/mesh/status")
def api_mesh_status():
    return jsonify(_mesh.stats())


@pixnet_bp.route("/mesh/peers")
def api_mesh_peers():
    return jsonify(_mesh.get_all_peers())


@pixnet_bp.route("/mesh/peers/connected")
def api_mesh_peers_connected():
    return jsonify(_mesh.get_connected_peers())


@pixnet_bp.route("/mesh/peers/<peer_id>/remove", methods=["POST"])
def api_mesh_remove_peer(peer_id):
    return jsonify(_mesh.remove_peer(peer_id))


@pixnet_bp.route("/mesh/discover", methods=["POST"])
def api_mesh_discover():
    return jsonify({"peers": _mesh.discover_peers()})


@pixnet_bp.route("/mesh/start", methods=["POST"])
def api_mesh_start():
    data = request.get_json(force=True) or {}
    interval = data.get("interval", 300)
    return jsonify(_mesh.start_discovery(interval))


@pixnet_bp.route("/mesh/stop", methods=["POST"])
def api_mesh_stop():
    return jsonify(_mesh.stop_discovery())


@pixnet_bp.route("/mesh/health")
def api_mesh_health():
    return jsonify(_mesh.health_check())


@pixnet_bp.route("/mesh/register", methods=["POST"])
def api_mesh_register():
    data = request.get_json(force=True) or {}
    api_url = data.get("api_url", "http://127.0.0.1:9999")
    caps = data.get("capabilities", None)
    _mesh.register_self(api_url, caps)
    return jsonify({"status": "registered", "node_id": _mesh.node_id})


@pixnet_bp.route("/mesh/config", methods=["GET", "POST"])
def api_mesh_config():
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        return jsonify(_mesh.update_config(data))
    return jsonify(_mesh.config)


# ── DHT ────────────────────────────────────────────────────

@pixnet_bp.route("/dht/identity")
def api_dht_identity():
    return jsonify(_dht.get_identity())


@pixnet_bp.route("/dht/routing")
def api_dht_routing():
    return jsonify({"table": _dht.routing_table, "size": len(_dht.routing_table)})


@pixnet_bp.route("/dht/store", methods=["POST"])
def api_dht_store():
    data = request.get_json(force=True) or {}
    key = data.get("key", "")
    value = data.get("value", {})
    if not key:
        return jsonify({"error": "key required"}), 400
    return jsonify(_dht.store_value(key, value))


@pixnet_bp.route("/dht/get")
def api_dht_get():
    key = request.args.get("key", "")
    if not key:
        return jsonify({"error": "key required"}), 400
    val = _dht.get_value(key)
    if val is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(val)


@pixnet_bp.route("/dht/find")
def api_dht_find():
    key = request.args.get("key", "")
    count = request.args.get("count", 10, type=int)
    return jsonify({"peers": _dht.find_peers(key, count)})


@pixnet_bp.route("/dht/stats")
def api_dht_stats():
    return jsonify(_dht.stats())


@pixnet_bp.route("/dht/refresh", methods=["POST"])
def api_dht_refresh():
    return jsonify(_dht.refresh_routing())


@pixnet_bp.route("/dht/clear", methods=["POST"])
def api_dht_clear():
    return jsonify(_dht.clear_routing())


@pixnet_bp.route("/dht/resolve/hns")
def api_dht_resolve_hns():
    name = request.args.get("name", "")
    result = _dht.resolve_hns(name)
    if result:
        return jsonify(result)
    return jsonify({"error": "not found"}), 404


@pixnet_bp.route("/dht/resolve/ens")
def api_dht_resolve_ens():
    name = request.args.get("name", "")
    result = _dht.resolve_ens(name)
    if result:
        return jsonify(result)
    return jsonify({"error": "not found"}), 404


@pixnet_bp.route("/dht/resolve/pixel")
def api_dht_resolve_pixel():
    name = request.args.get("name", "")
    result = _dht.resolve_pixel(name)
    if result:
        return jsonify(result)
    return jsonify({"error": "not found"}), 404


# ── Global ─────────────────────────────────────────────────

@pixnet_bp.route("/ping")
def api_ping():
    return jsonify({
        "status": "pong",
        "node_id": _mesh.node_id,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    })


@pixnet_bp.route("/stats")
def api_pixnet_stats():
    return jsonify({
        "crawler": _crawler.stats(),
        "search": _search.stats(),
        "trust": _trust.stats(),
        "mesh": _mesh.stats(),
        "dht": _dht.stats(),
    })
