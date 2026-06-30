# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Routes API Pixel Comms — Communication Matrix."""

from flask import Blueprint, jsonify, request, render_template

comms_bp = Blueprint("comms", __name__, url_prefix="/api/comms")


# ── Salles ──

@comms_bp.route("/rooms", methods=["GET"])
def rooms_list():
    from .matrix_comms import matrix_comms_bridge
    return jsonify({
        "rooms": matrix_comms_bridge.list_rooms(
            filter_public=request.args.get("public", type=bool),
            filter_iot=request.args.get("iot", type=bool),
        )
    })


@comms_bp.route("/rooms", methods=["POST"])
def rooms_create():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    room = matrix_comms_bridge.create_room(
        data["name"],
        topic=data.get("topic", ""),
        purpose=data.get("purpose", ""),
        is_public=data.get("is_public", True),
        encrypted=data.get("encrypted", True),
        auto_iot=data.get("auto_iot", False),
    )
    return jsonify(room), 201


@comms_bp.route("/rooms/<room_id>", methods=["GET"])
def rooms_get(room_id):
    from .matrix_comms import matrix_comms_bridge
    room = matrix_comms_bridge.get_room(room_id)
    if not room:
        return jsonify({"error": "not found"}), 404
    return jsonify(room)


@comms_bp.route("/rooms/<room_id>", methods=["PUT"])
def rooms_update(room_id):
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json(silent=True) or {}
    room = matrix_comms_bridge.update_room(room_id, **data)
    if not room:
        return jsonify({"error": "not found"}), 404
    return jsonify(room)


@comms_bp.route("/rooms/<room_id>", methods=["DELETE"])
def rooms_delete(room_id):
    from .matrix_comms import matrix_comms_bridge
    if matrix_comms_bridge.delete_room(room_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404


@comms_bp.route("/rooms/<room_id>/members/<user_id>", methods=["POST"])
def rooms_add_member(room_id, user_id):
    from .matrix_comms import matrix_comms_bridge
    if matrix_comms_bridge.add_member(room_id, user_id):
        return jsonify({"status": "added"})
    return jsonify({"error": "room not found"}), 404


@comms_bp.route("/rooms/<room_id>/members/<user_id>", methods=["DELETE"])
def rooms_remove_member(room_id, user_id):
    from .matrix_comms import matrix_comms_bridge
    if matrix_comms_bridge.remove_member(room_id, user_id):
        return jsonify({"status": "removed"})
    return jsonify({"error": "room not found"}), 404


# ── Utilisateurs ──

@comms_bp.route("/users", methods=["GET"])
def users_list():
    from .matrix_comms import matrix_comms_bridge
    return jsonify({
        "users": matrix_comms_bridge.list_users(
            role=request.args.get("role"),
        )
    })


@comms_bp.route("/users", methods=["POST"])
def users_register():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("matrix_id"):
        return jsonify({"error": "matrix_id required"}), 400
    user = matrix_comms_bridge.register_user(
        data["matrix_id"],
        display_name=data.get("display_name", ""),
        role=data.get("role", "member"),
        is_bot=data.get("is_bot", False),
    )
    return jsonify(user), 201


@comms_bp.route("/users/<matrix_id>", methods=["GET"])
def users_get(matrix_id):
    from .matrix_comms import matrix_comms_bridge
    user = matrix_comms_bridge.get_user(matrix_id)
    if not user:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)


# ── Notifications ──

@comms_bp.route("/notify", methods=["POST"])
def notify_send():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("room_id") or not data.get("title"):
        return jsonify({"error": "room_id and title required"}), 400
    ok = matrix_comms_bridge.notify_all(
        data["room_id"], data["title"],
        data.get("message", ""),
        icon=data.get("icon", "📢"),
    )
    return jsonify({"status": "sent" if ok else "failed"})


@comms_bp.route("/notify/node", methods=["POST"])
def notify_node():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("node_id"):
        return jsonify({"error": "node_id required"}), 400
    matrix_comms_bridge.notify_new_node(
        data["node_id"], data.get("nickname", ""), data.get("country", ""))
    return jsonify({"status": "sent"})


@comms_bp.route("/notify/species", methods=["POST"])
def notify_species():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("species_name"):
        return jsonify({"error": "species_name required"}), 400
    matrix_comms_bridge.notify_new_species(
        data["species_name"], data.get("node_id", ""))
    return jsonify({"status": "sent"})


@comms_bp.route("/notify/vote", methods=["POST"])
def notify_vote():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("proposal"):
        return jsonify({"error": "proposal required"}), 400
    matrix_comms_bridge.notify_governance_vote(
        data["proposal"], data.get("deadline", ""))
    return jsonify({"status": "sent"})


@comms_bp.route("/notify/payment", methods=["POST"])
def notify_payment():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or data.get("amount") is None:
        return jsonify({"error": "amount required"}), 400
    matrix_comms_bridge.notify_payment(
        data.get("from", ""), data.get("to", ""),
        data["amount"], data.get("memo", ""))
    return jsonify({"status": "sent"})


# ── Pont IoT ──

@comms_bp.route("/iot/alert", methods=["POST"])
def iot_alert():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("room_id") or not data.get("sensor_id"):
        return jsonify({"error": "room_id and sensor_id required"}), 400
    ok = matrix_comms_bridge.send_iot_alert(
        data["room_id"], data["sensor_id"],
        data.get("metric", "unknown"),
        data.get("value", 0),
        unit=data.get("unit", ""),
        severity=data.get("severity", "info"),
    )
    return jsonify({"status": "sent" if ok else "ignored"})


@comms_bp.route("/iot/mqtt-forward", methods=["POST"])
def iot_mqtt_forward():
    from .matrix_comms import matrix_comms_bridge
    data = request.get_json()
    if not data or not data.get("topic") or not data.get("payload"):
        return jsonify({"error": "topic and payload required"}), 400
    ok = matrix_comms_bridge.forward_mqtt_to_matrix(
        data["topic"], data["payload"])
    return jsonify({"status": "forwarded" if ok else "ignored"})


# ── Stats ──

@comms_bp.route("/stats", methods=["GET"])
def comms_stats():
    from .matrix_comms import matrix_comms_bridge
    return jsonify(matrix_comms_bridge.stats())


def register_comms_routes(app):
    """Enregistre les routes Comms sur l'application Flask."""
    app.register_blueprint(comms_bp)

    @app.route("/comms")
    def comms_page():
        return render_template("comms.html", title="Pixel Comms")
