# Pixel OS ó Copyright 2026
# Free License ó Verifiable and Reliable for Internet Users
# Pixel Software Design ó Copyright 2026
"""Routes API Souverainet√© ‚Äî Charte, DDNS, Disclaimer."""

from flask import Blueprint, jsonify, request, render_template

sovereignty_bp = Blueprint("sovereignty", __name__,
                           url_prefix="/api/sovereignty")


@sovereignty_bp.route("/charter", methods=["GET"])
def charter_get():
    from .charter import charter
    return jsonify({
        "text": charter.text,
        "status": charter.status(),
    })


@sovereignty_bp.route("/charter/accept", methods=["POST"])
def charter_accept():
    from .charter import charter
    data = request.get_json(silent=True) or {}
    node_id = data.get("node_id", "")
    return jsonify(charter.accept(node_id))


@sovereignty_bp.route("/charter/status", methods=["GET"])
def charter_status():
    from .charter import charter
    return jsonify(charter.status())


@sovereignty_bp.route("/ddns/disclaimer", methods=["GET"])
def ddns_disclaimer():
    from .ddns import pixel_ddns
    return jsonify(pixel_ddns.disclaimer())


@sovereignty_bp.route("/ddns/register", methods=["POST"])
def ddns_register():
    from .ddns import pixel_ddns
    data = request.get_json()
    if not data or not data.get("subdomain"):
        return jsonify({"error": "subdomain required"}), 400
    result = pixel_ddns.register(
        data["subdomain"],
        ip=data.get("ip", ""),
        node_id=data.get("node_id", ""),
        disclaimer_accepted=data.get("disclaimer_accepted", False),
    )
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


@sovereignty_bp.route("/ddns/update", methods=["POST"])
def ddns_update():
    from .ddns import pixel_ddns
    data = request.get_json()
    if not data or not data.get("subdomain"):
        return jsonify({"error": "subdomain required"}), 400
    result = pixel_ddns.update(data["subdomain"], ip=data.get("ip", ""))
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@sovereignty_bp.route("/ddns/<subdomain>", methods=["GET"])
def ddns_get(subdomain):
    from .ddns import pixel_ddns
    result = pixel_ddns.get(subdomain)
    if not result:
        return jsonify({"error": "not found"}), 404
    return jsonify(result)


@sovereignty_bp.route("/ddns/<subdomain>", methods=["DELETE"])
def ddns_delete(subdomain):
    from .ddns import pixel_ddns
    if pixel_ddns.unregister(subdomain):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404


@sovereignty_bp.route("/ddns/list", methods=["GET"])
def ddns_list():
    from .ddns import pixel_ddns
    return jsonify({
        "registrations": pixel_ddns.list(
            node_id=request.args.get("node_id", ""),
        )
    })


@sovereignty_bp.route("/stats", methods=["GET"])
def sovereignty_stats():
    from .charter import charter
    from .ddns import pixel_ddns
    return jsonify({
        "charter": charter.status(),
        "ddns": pixel_ddns.stats(),
    })


def register_sovereignty_routes(app):
    """Enregistre les routes Souverainet√© sur l'application Flask."""
    app.register_blueprint(sovereignty_bp)

    @app.route("/legal")
    def legal_page():
        return render_template("legal.html", title="Charte de Souverainet√©")

    @app.route("/community/charter")
    def community_charter():
        return render_template("legal.html", title="Charte de Souverainet√©")
