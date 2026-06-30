"""Module Web3 PixelOS — BITROOT (BRT), Wallet, Paiement P2P, Échange, IPFS Web3.

Architecture:
  PixelToken.sol  →  Smart Contract ERC-20 BITROOT (Solidity)
  WalletManager   →  Gestion portefeuille (clés, soldes, historique transactions)
  PaymentEngine   →  Moteur de paiement P2P avec signature locale
  ExchangeMarket  →  Marché P2P entre membres (annonces, achats, ventes)
  Web3IPFS        →  Pont IPFS + DNSLink pour souveraineté Web3
  MatrixPayBridge →  Bridge Matrix pour notifications de paiement
"""

from .wallet import WalletManager, wallet_manager
from .payment import PaymentEngine, payment_engine
from .exchange import ExchangeMarket, exchange_market
from .ipfs_web3 import Web3IPFS, web3_ipfs
from .matrix_pay import MatrixPayBridge, matrix_pay_bridge
from .routes import register_web3_routes
