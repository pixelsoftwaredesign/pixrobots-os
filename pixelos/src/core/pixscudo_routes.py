from flask import Blueprint, request, jsonify, render_template
from .pixscudo import PixScudo

pixscudo_bp = Blueprint("pixscudo", __name__, url_prefix="/api/pixscudo")
_psc = PixScudo()


def register_pixscudo_routes(app):
    app.register_blueprint(pixscudo_bp)

    @app.route("/pixscudo")
    def pixscudo_page():
        return render_template("pixscudo.html", title="PixScudo")


@pixscudo_bp.route("/summary")
def api_summary():
    return jsonify(_psc.summary())


@pixscudo_bp.route("/audit", methods=["POST"])
def api_audit():
    return jsonify(_psc.run_full_audit())


@pixscudo_bp.route("/patches")
def api_patches():
    return jsonify(_psc.check_syspatch())


@pixscudo_bp.route("/packages")
def api_packages():
    return jsonify(_psc.check_packages())


@pixscudo_bp.route("/integrity")
def api_integrity():
    return jsonify(_psc.verify_integrity())


@pixscudo_bp.route("/baseline", methods=["POST"])
def api_baseline():
    return jsonify(_psc.create_baseline())


@pixscudo_bp.route("/ssh")
def api_ssh():
    return jsonify(_psc.check_ssh())


@pixscudo_bp.route("/permissions")
def api_permissions():
    return jsonify(_psc.check_permissions())


@pixscudo_bp.route("/ports")
def api_ports():
    return jsonify(_psc.check_open_ports())


@pixscudo_bp.route("/processes")
def api_processes():
    return jsonify(_psc.check_processes())


@pixscudo_bp.route("/cis")
def api_cis():
    return jsonify(_psc.cis_check())
