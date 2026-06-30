# Pixel OS � Copyright 2026
# Free License � Verifiable and Reliable for Internet Users
# Pixel Software Design � Copyright 2026
"""Routes API Web3/Pixel Pay pour l'interface Flask PixelOS."""

from flask import Blueprint, jsonify, request, render_template

web3_bp = Blueprint("web3", __name__, url_prefix="/api/web3")

# ── Wallet ──────────────────────────────────────────────

@web3_bp.route("/wallet/create", methods=["POST"])
def wallet_create():
    from .wallet import wallet_manager
    data = request.get_json(silent=True) or {}
    result = wallet_manager.create_wallet(
        label=data.get("label", ""),
        password=data.get("password", "pixelos_default"),
        make_default=data.get("make_default", False),
    )
    return jsonify(result), 201

@web3_bp.route("/wallet/import", methods=["POST"])
def wallet_import():
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("private_key"):
        return jsonify({"error": "private_key required"}), 400
    result = wallet_manager.import_wallet(
        data["private_key"],
        label=data.get("label", ""),
        password=data.get("password", "pixelos_default"),
        make_default=data.get("make_default", False),
    )
    if not result:
        return jsonify({"error": "Clé privée invalide"}), 400
    return jsonify(result), 201

@web3_bp.route("/wallet/list", methods=["GET"])
def wallet_list():
    from .wallet import wallet_manager
    return jsonify(wallet_manager.list_wallets())

@web3_bp.route("/wallet/<address>", methods=["GET"])
def wallet_get(address):
    from .wallet import wallet_manager
    w = wallet_manager.get_wallet(address)
    if not w:
        return jsonify({"error": "not found"}), 404
    return jsonify(w)

@web3_bp.route("/wallet/<address>/balance", methods=["PUT"])
def wallet_set_balance(address):
    from .wallet import wallet_manager
    data = request.get_json(silent=True) or {}
    w = wallet_manager._wallets.get(address)
    if not w:
        return jsonify({"error": "not found"}), 404
    if "balance_brt" in data:
        w.balance_brt = float(data["balance_brt"])
    if "balance_wei" in data:
        w.balance_wei = int(data["balance_wei"])
    wallet_manager._save()
    return jsonify(w.to_dict())

@web3_bp.route("/wallet/<address>/default", methods=["POST"])
def wallet_set_default(address):
    from .wallet import wallet_manager
    if wallet_manager.set_default(address):
        return jsonify({"status": "ok", "default": address})
    return jsonify({"error": "not found"}), 404

@web3_bp.route("/wallet/<address>", methods=["DELETE"])
def wallet_delete(address):
    from .wallet import wallet_manager
    if wallet_manager.delete_wallet(address):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "not found"}), 404

@web3_bp.route("/wallet/<address>/sign", methods=["POST"])
def wallet_sign(address):
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("message"):
        return jsonify({"error": "message required"}), 400
    result = wallet_manager.sign_message(
        address, data["message"],
        password=data.get("password", "pixelos_default"),
    )
    if not result:
        return jsonify({"error": "signature failed"}), 400
    return jsonify(result)

@web3_bp.route("/wallet/<address>/private-key", methods=["POST"])
def wallet_export_key(address):
    from .wallet import wallet_manager
    data = request.get_json(silent=True) or {}
    pk = wallet_manager.get_private_key(
        address, password=data.get("password", "pixelos_default"))
    if not pk:
        return jsonify({"error": "Accès refusé ou portefeuille introuvable"}), 403
    return jsonify({"private_key": pk, "warning": "Ne partagez jamais cette clé"})

# ── Transactions ────────────────────────────────────────

@web3_bp.route("/tx/create", methods=["POST"])
def tx_create():
    from .payment import payment_engine, wallet_manager
    data = request.get_json()
    if not data or not data.get("to") or data.get("amount_brt") is None:
        return jsonify({"error": "to and amount_brt required"}), 400
    from_addr = data.get("from", "")
    if not from_addr:
        default = wallet_manager.get_default_wallet()
        if not default:
            return jsonify({"error": "Aucun portefeuille par défaut"}), 400
        from_addr = default.address
    tx = payment_engine.create_transaction(
        from_addr, data["to"], data["amount_brt"],
        memo=data.get("memo", ""), category=data.get("category", "autre"),
    )
    return jsonify(tx), 201

@web3_bp.route("/tx/send", methods=["POST"])
def tx_send():
    from .payment import payment_engine
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("from") or not data.get("to") or data.get("amount_brt") is None:
        return jsonify({"error": "from, to, amount_brt required"}), 400
    tx = payment_engine.create_transaction(
        data["from"], data["to"], data["amount_brt"],
        memo=data.get("memo", ""), category=data.get("category", "autre"),
    )
    password = data.get("password", "pixelos_default")
    rpc = data.get("rpc_url", "https://rpc.gnosis.gateway.fm")
    pk = wallet_manager.get_private_key(data["from"], password)
    if not pk:
        return jsonify({"error": "Portefeuille verrouillé ou introuvable"}), 403
    result = payment_engine.sign_and_send(tx, pk, rpc)
    return jsonify(result)

@web3_bp.route("/tx/send-offline", methods=["POST"])
def tx_send_offline():
    from .payment import payment_engine
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("to") or data.get("amount_brt") is None:
        return jsonify({"error": "to and amount_brt required"}), 400
    from_addr = data.get("from", "")
    if not from_addr:
        default = wallet_manager.get_default_wallet()
        if not default:
            return jsonify({"error": "Aucun portefeuille"}), 400
        from_addr = default.address
    tx = payment_engine.create_transaction(
        from_addr, data["to"], data["amount_brt"],
        memo=data.get("memo", ""), category=data.get("category", "autre"),
    )
    result = payment_engine.send_offline(tx)
    return jsonify(result), 201

@web3_bp.route("/tx/queue", methods=["GET"])
def tx_queue():
    from .payment import payment_engine
    return jsonify(payment_engine.queue)

@web3_bp.route("/tx/queue/process", methods=["POST"])
def tx_process_queue():
    from .payment import payment_engine
    data = request.get_json(silent=True) or {}
    results = payment_engine.process_queue(
        rpc_url=data.get("rpc_url", "https://rpc.gnosis.gateway.fm"),
        password=data.get("password", "pixelos_default"),
    )
    return jsonify({"processed": len(results), "results": results})

@web3_bp.route("/tx/history", methods=["GET"])
def tx_history():
    from .wallet import wallet_manager
    address = request.args.get("address")
    limit = request.args.get("limit", 50, type=int)
    return jsonify(wallet_manager.get_transactions(address, limit))

@web3_bp.route("/tx/<tx_hash>/confirm", methods=["POST"])
def tx_confirm(tx_hash):
    from .payment import payment_engine
    data = request.get_json(silent=True) or {}
    result = payment_engine.confirm_transaction(
        tx_hash, data.get("rpc_url", "https://rpc.gnosis.gateway.fm"))
    if not result:
        return jsonify({"status": "pending", "tx_hash": tx_hash})
    return jsonify(result)

# ── Factures ───────────────────────────────────────────

@web3_bp.route("/invoice/create", methods=["POST"])
def invoice_create():
    from .payment import payment_engine
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or data.get("amount_brt") is None or not data.get("to"):
        return jsonify({"error": "to and amount_brt required"}), 400
    from_addr = data.get("from", "")
    if not from_addr:
        default = wallet_manager.get_default_wallet()
        if not default:
            return jsonify({"error": "Aucun portefeuille"}), 400
        from_addr = default.address
    inv = payment_engine.create_invoice(
        from_addr, data["to"], data["amount_brt"],
        label=data.get("label", ""), description=data.get("description", ""),
        due_date=data.get("due_date", ""),
    )
    from .matrix_pay import matrix_pay_bridge
    matrix_pay_bridge.notify_invoice(inv)
    return jsonify(inv), 201

@web3_bp.route("/invoice/list", methods=["GET"])
def invoice_list():
    from .payment import payment_engine
    return jsonify(payment_engine.list_invoices(
        address=request.args.get("address"),
        status=request.args.get("status"),
    ))

@web3_bp.route("/invoice/<invoice_id>/qr", methods=["GET"])
def invoice_qr(invoice_id):
    from .payment import payment_engine
    data = payment_engine.invoice_qr_data(invoice_id)
    if not data:
        return jsonify({"error": "not found"}), 404
    return jsonify({"qr_data": data, "invoice_id": invoice_id})

# ── Taux de change ────────────────────────────────────

@web3_bp.route("/rates", methods=["GET"])
def rates_get():
    from .payment import payment_engine
    return jsonify(payment_engine.get_rates())

@web3_bp.route("/rates", methods=["PUT"])
def rates_set():
    from .payment import payment_engine
    data = request.get_json()
    if not data or data.get("brt_per_eur") is None:
        return jsonify({"error": "brt_per_eur required"}), 400
    payment_engine.set_rate(data["brt_per_eur"])
    return jsonify(payment_engine.get_rates())

# ── Exchange / Marché ──────────────────────────────────

@web3_bp.route("/exchange/listing", methods=["POST"])
def exchange_listing_create():
    from .exchange import exchange_market
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("product_name") or data.get("price_brt") is None:
        return jsonify({"error": "product_name and price_brt required"}), 400
    seller = data.get("seller", "")
    if not seller:
        default = wallet_manager.get_default_wallet()
        if not default:
            return jsonify({"error": "Aucun portefeuille"}), 400
        seller = default.address
    listing = exchange_market.create_listing(
        seller, data["product_name"], data["price_brt"],
        quantity_kg=data.get("quantity_kg", 1.0),
        category=data.get("category", "legume"),
        listing_type=data.get("type", "vente"),
        description=data.get("description", ""),
        location=data.get("location", ""),
        images=data.get("images"),
        organic=data.get("organic", False),
        variety=data.get("variety", ""),
    )
    from .matrix_pay import matrix_pay_bridge
    matrix_pay_bridge.notify_new_listing(listing)
    return jsonify(listing), 201

@web3_bp.route("/exchange/listings", methods=["GET"])
def exchange_listings():
    from .exchange import exchange_market
    listings = exchange_market.search_listings(
        query=request.args.get("q"),
        category=request.args.get("category"),
        listing_type=request.args.get("type"),
        min_price=request.args.get("min_price", type=float),
        max_price=request.args.get("max_price", type=float),
        organic=request.args.get("organic", type=bool),
        seller=request.args.get("seller"),
        location=request.args.get("location"),
    )
    return jsonify(listings)

@web3_bp.route("/exchange/listing/<listing_id>", methods=["GET"])
def exchange_listing_get(listing_id):
    from .exchange import exchange_market
    l = exchange_market.get_listing(listing_id)
    if not l:
        return jsonify({"error": "not found"}), 404
    return jsonify(l)

@web3_bp.route("/exchange/listing/<listing_id>", methods=["PUT"])
def exchange_listing_update(listing_id):
    from .exchange import exchange_market
    data = request.get_json(silent=True) or {}
    l = exchange_market.update_listing(listing_id, **data)
    if not l:
        return jsonify({"error": "not found"}), 404
    return jsonify(l)

@web3_bp.route("/exchange/my-listings", methods=["GET"])
def exchange_my_listings():
    from .exchange import exchange_market
    seller = request.args.get("seller", "")
    if not seller:
        return jsonify([])
    return jsonify(exchange_market.my_listings(seller))

@web3_bp.route("/exchange/order", methods=["POST"])
def exchange_order_create():
    from .exchange import exchange_market
    from .wallet import wallet_manager
    data = request.get_json()
    if not data or not data.get("listing_id"):
        return jsonify({"error": "listing_id required"}), 400
    buyer = data.get("buyer", "")
    if not buyer:
        default = wallet_manager.get_default_wallet()
        if not default:
            return jsonify({"error": "Aucun portefeuille"}), 400
        buyer = default.address
    order = exchange_market.create_order(
        data["listing_id"], buyer,
        quantity_kg=data.get("quantity_kg"),
    )
    if not order:
        return jsonify({"error": "Annonce non disponible"}), 400
    if "error" in order:
        return jsonify(order), 400
    from .matrix_pay import matrix_pay_bridge
    matrix_pay_bridge.notify_new_order(order)
    return jsonify(order), 201

@web3_bp.route("/exchange/order/<order_id>/confirm", methods=["POST"])
def exchange_order_confirm(order_id):
    from .exchange import exchange_market
    data = request.get_json(silent=True) or {}
    if not data.get("tx_hash"):
        return jsonify({"error": "tx_hash required"}), 400
    order = exchange_market.confirm_order(order_id, data["tx_hash"])
    if not order:
        return jsonify({"error": "not found"}), 404
    return jsonify(order)

@web3_bp.route("/exchange/order/<order_id>/status", methods=["PUT"])
def exchange_order_status(order_id):
    from .exchange import exchange_market
    data = request.get_json(silent=True) or {}
    if not data.get("status"):
        return jsonify({"error": "status required"}), 400
    order = exchange_market.update_order(
        order_id, data["status"], notes=data.get("notes"))
    if not order:
        return jsonify({"error": "not found"}), 400
    return jsonify(order)

@web3_bp.route("/exchange/my-orders", methods=["GET"])
def exchange_my_orders():
    from .exchange import exchange_market
    address = request.args.get("address", "")
    if not address:
        return jsonify({"as_buyer": [], "as_seller": []})
    return jsonify(exchange_market.my_orders(address))

@web3_bp.route("/exchange/catalog", methods=["GET"])
def exchange_catalog():
    from .exchange import exchange_market
    return jsonify(exchange_market.search_catalog(
        query=request.args.get("q"),
        category=request.args.get("category"),
    ))

@web3_bp.route("/exchange/catalog", methods=["POST"])
def exchange_catalog_add():
    from .exchange import exchange_market
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name required"}), 400
    item = exchange_market.add_to_catalog(
        data["name"], data.get("category", "legume"),
        description=data.get("description", ""),
        unit=data.get("unit", "kg"),
        default_price_brt=data.get("default_price_brt", 0),
        variety=data.get("variety", ""),
    )
    return jsonify(item), 201

# ── IPFS Web3 ──────────────────────────────────────────

@web3_bp.route("/ipfs/status", methods=["GET"])
def ipfs_status():
    from .ipfs_web3 import web3_ipfs
    return jsonify(web3_ipfs.stats())

@web3_bp.route("/ipfs/publish", methods=["POST"])
def ipfs_publish():
    from .ipfs_web3 import web3_ipfs
    data = request.get_json()
    if not data or not data.get("data") and not data.get("file"):
        return jsonify({"error": "data or file required"}), 400
    if data.get("file"):
        return jsonify(web3_ipfs.publish_file(data["file"], data.get("pin", True)))
    if isinstance(data.get("data"), dict):
        result = web3_ipfs.publish_json(
            data["data"], data.get("name", "data"), pin=data.get("pin", True))
        return jsonify(result) if result else (jsonify({"error": "publish failed"}), 500)
    return jsonify({"error": "invalid data"}), 400

@web3_bp.route("/ipfs/fetch", methods=["POST"])
def ipfs_fetch():
    from .ipfs_web3 import web3_ipfs
    data = request.get_json()
    if not data or not data.get("cid"):
        return jsonify({"error": "cid required"}), 400
    content = web3_ipfs.fetch(data["cid"])
    if content is None:
        return jsonify({"error": "fetch failed"}), 404
    try:
        decoded = json.loads(content.decode())
        return jsonify(decoded)
    except Exception:
        return content, 200, {"Content-Type": "application/octet-stream"}

@web3_bp.route("/ipfs/dnslink", methods=["GET"])
def ipfs_dnslink():
    from .ipfs_web3 import web3_ipfs
    return jsonify(web3_ipfs.list_dnslink())

@web3_bp.route("/ipfs/dnslink", methods=["POST"])
def ipfs_dnslink_set():
    from .ipfs_web3 import web3_ipfs
    data = request.get_json()
    if not data or not data.get("subdomain") or not data.get("cid"):
        return jsonify({"error": "subdomain and cid required"}), 400
    entry = web3_ipfs.publish_dnslink(data["subdomain"], data["cid"])
    return jsonify(entry), 201

@web3_bp.route("/ipfs/publish-site", methods=["POST"])
def ipfs_publish_site():
    from .ipfs_web3 import web3_ipfs
    data = request.get_json()
    if not data or not data.get("source_dir"):
        return jsonify({"error": "source_dir required"}), 400
    result = web3_ipfs.publish_site(data["source_dir"], data.get("site_name", "pixelos"))
    return jsonify(result)

# ── Stats ──────────────────────────────────────────────

@web3_bp.route("/stats", methods=["GET"])
def web3_stats():
    from .wallet import wallet_manager
    from .payment import payment_engine
    from .exchange import exchange_market
    from .ipfs_web3 import web3_ipfs
    from .matrix_pay import matrix_pay_bridge
    return jsonify({
        "wallet": wallet_manager.stats(),
        "payment": payment_engine.stats(),
        "exchange": exchange_market.stats(),
        "ipfs": web3_ipfs.stats(),
        "matrix_pay": matrix_pay_bridge.status(),
    })


def register_web3_routes(app):
    """Enregistre les routes Web3 sur l'application Flask."""
    app.register_blueprint(web3_bp)

    @app.route("/wallet")
    def wallet_page():
        return render_template("wallet.html", title="Pixel Wallet - BITROOT")

    @app.route("/exchange")
    def exchange_page():
        return render_template("exchange.html", title="Marché PixelOS - BITROOT")
