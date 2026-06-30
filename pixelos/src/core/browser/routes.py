from flask import Blueprint, request, jsonify, render_template, Response
import json

browser_bp = Blueprint("browser", __name__, url_prefix="/api/browser")

from .nop_browser import NOPBrowser
_nop = NOPBrowser()


def register_browser_routes(app):
    app.register_blueprint(browser_bp)

    @app.route("/browser")
    def browser_page():
        return render_template("browser.html", title="NOP Browser")


@browser_bp.route("/navigate", methods=["POST"])
def navigate():
    data = request.get_json(force=True) or {}
    url = data.get("url", "")
    result = _nop.navigate(url)
    return jsonify(result)


@browser_bp.route("/resolve", methods=["POST"])
def resolve():
    data = request.get_json(force=True) or {}
    url = data.get("url", "")
    result = _nop.resolve_url(url)
    return jsonify(result)


@browser_bp.route("/render", methods=["POST"])
def render():
    data = request.get_json(force=True) or {}
    url = data.get("url", "")
    mode = data.get("mode", "proxy")
    result = _nop.get_render_url(url, mode)
    return jsonify(result)


@browser_bp.route("/proxy")
def proxy():
    url = request.args.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    result = _nop.proxy_fetch(url)
    if result["status"] == "error":
        return jsonify(result), 502
    return Response(
        result["content"],
        content_type=result.get("content_type", "text/html"),
    )


@browser_bp.route("/tabs", methods=["GET"])
def list_tabs():
    return jsonify(_nop.list_tabs())


@browser_bp.route("/tabs/<int:tab_id>/close", methods=["POST"])
def close_tab(tab_id):
    return jsonify(_nop.close_tab(tab_id))


@browser_bp.route("/history", methods=["GET"])
def get_history():
    limit = request.args.get("limit", 100, type=int)
    search = request.args.get("search")
    return jsonify(_nop.get_history(limit=limit, search=search))


@browser_bp.route("/history/clear", methods=["POST"])
def clear_history():
    return jsonify(_nop.clear_history())


@browser_bp.route("/bookmarks", methods=["GET"])
def get_bookmarks():
    return jsonify(_nop.get_bookmarks())


@browser_bp.route("/bookmarks/add", methods=["POST"])
def add_bookmark():
    data = request.get_json(force=True) or {}
    return jsonify(_nop.add_bookmark(
        url=data.get("url", ""),
        title=data.get("title", ""),
        tags=data.get("tags"),
    ))


@browser_bp.route("/bookmarks/remove", methods=["POST"])
def remove_bookmark():
    data = request.get_json(force=True) or {}
    return jsonify(_nop.remove_bookmark(data.get("url", "")))


@browser_bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(_nop.get_settings())


@browser_bp.route("/settings", methods=["POST"])
def update_settings():
    data = request.get_json(force=True) or {}
    return jsonify(_nop.update_settings(data))


@browser_bp.route("/wallet/check", methods=["POST"])
def wallet_check():
    data = request.get_json(force=True) or {}
    return jsonify(_nop.check_wallet(data.get("url", "")))


@browser_bp.route("/wallet/sign", methods=["POST"])
def wallet_sign():
    data = request.get_json(force=True) or {}
    return jsonify(_nop.sign_tx(data))


@browser_bp.route("/privacy/stats")
def privacy_stats():
    return jsonify(_nop.privacy_stats())


@browser_bp.route("/privacy/update", methods=["POST"])
def privacy_update():
    return jsonify(_nop.update_blocklists())


@browser_bp.route("/resolver/stats")
def resolver_stats():
    return jsonify(_nop.resolver.stats())


@browser_bp.route("/resolver/clear", methods=["POST"])
def resolver_clear():
    return jsonify(_nop.resolver.clear_cache())


@browser_bp.route("/stats")
def stats():
    return jsonify(_nop.stats())
