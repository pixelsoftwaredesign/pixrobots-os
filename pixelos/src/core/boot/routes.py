from flask import Blueprint, request, jsonify, render_template
from .installer import ZeroTouchInstaller

install_bp = Blueprint("install", __name__, url_prefix="/api/install")
_inst = ZeroTouchInstaller()


def register_install_routes(app):
    app.register_blueprint(install_bp)

    @app.route("/install")
    def install_page():
        return render_template("install.html", title="Zero-Touch Installer")


@install_bp.route("/run", methods=["POST"])
def api_install_run():
    data = request.get_json(force=True) or {}
    return jsonify(_inst.run(skip_deps=data.get("skip_deps", False)))


@install_bp.route("/check")
def api_install_check():
    return jsonify(_inst.check_system())


@install_bp.route("/install-site", methods=["POST"])
def api_install_site():
    data = request.get_json(force=True) or {}
    out = data.get("output_dir", "")
    return jsonify(_inst.generate_install_site(out))


@install_bp.route("/iso/openbsd", methods=["POST"])
def api_iso_openbsd():
    data = request.get_json(force=True) or {}
    out = data.get("output", "")
    return jsonify(_inst.generate_openbsd_iso(out))


@install_bp.route("/iso/debian", methods=["POST"])
def api_iso_debian():
    data = request.get_json(force=True) or {}
    out = data.get("output", "")
    return jsonify(_inst.generate_debian_iso(out))


@install_bp.route("/hooks", methods=["POST"])
def api_hooks():
    return jsonify(_inst.post_install_hooks())
