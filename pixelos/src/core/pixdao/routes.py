# Pixel Software Design — Copyright 2026
from flask import Blueprint, request, jsonify, render_template
from .pixdao import PixDAO

pixdao_bp = Blueprint("pixdao", __name__, url_prefix="/api/pixdao")
_dao = PixDAO()


def register_pixdao_routes(app):
    app.register_blueprint(pixdao_bp)

    @app.route("/pixdao")
    def pixdao_page():
        return render_template("pixdao.html", title="PixDAO")


@pixdao_bp.route("/proposals")
def api_proposals():
    return jsonify(_dao.list_proposals(request.args.get("status", "")))


@pixdao_bp.route("/proposals/<int:proposal_id>")
def api_proposal(proposal_id):
    p = _dao.get_proposal(proposal_id)
    if p is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(p)


@pixdao_bp.route("/proposals", methods=["POST"])
def api_proposal_create():
    data = request.get_json(force=True) or {}
    if not data.get("title"):
        return jsonify({"error": "title required"}), 400
    return jsonify(_dao.create_proposal(
        data["title"], data.get("description", ""),
        data.get("type", "general"), data.get("metadata", {})))


@pixdao_bp.route("/proposals/<int:proposal_id>/vote", methods=["POST"])
def api_proposal_vote(proposal_id):
    data = request.get_json(force=True) or {}
    return jsonify(_dao.vote(
        proposal_id, data.get("voter", "anonymous"),
        data.get("choice", "abstain"), data.get("weight", 1.0)))


@pixdao_bp.route("/close-expired", methods=["POST"])
def api_close_expired():
    return jsonify({"closed": _dao.close_expired()})


@pixdao_bp.route("/members")
def api_members():
    return jsonify(_dao.list_members())


@pixdao_bp.route("/members", methods=["POST"])
def api_member_add():
    data = request.get_json(force=True) or {}
    return jsonify(_dao.add_member(
        data.get("address", ""), data.get("role", "member"),
        data.get("weight", 1.0), data.get("label", "")))


@pixdao_bp.route("/members/<address>/remove", methods=["POST"])
def api_member_remove(address):
    return jsonify(_dao.remove_member(address))


@pixdao_bp.route("/treasury")
def api_treasury():
    return jsonify({
        "balance": _dao.treasury["balance"],
        "token": _dao.treasury["token"],
        "history": _dao.treasury_history(50),
    })


@pixdao_bp.route("/treasury/deposit", methods=["POST"])
def api_treasury_deposit():
    data = request.get_json(force=True) or {}
    return jsonify(_dao.deposit(data.get("amount", 0), data.get("source", "")))


@pixdao_bp.route("/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        return jsonify(_dao.update_config(data))
    return jsonify(_dao.config)


@pixdao_bp.route("/stats")
def api_stats():
    return jsonify(_dao.stats())
