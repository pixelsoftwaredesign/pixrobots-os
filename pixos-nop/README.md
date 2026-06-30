# PixOS NOP

Navigateur Web3 décentralisé pour Pixel OS — résolution IPFS, ENS, et navigation sécurisée.

## Fonctionnalités

- Barre d'adresse : `http://`, `https://`, `ipfs://`, `ens://`, `ipns://`
- Résolution IPFS via gateways (ipfs.io, dweb.link, localhost)
- Résolution ENS via contrat Ethereum (Web3j)
- Mode JavaScript on/off

## Architecture

```
BrowserScreen (AddressBar + WebView)
  ├── IpfsResolver.kt    # CID → gateway HTTP
  ├── EnsResolver.kt     # nom.eth → adresse → contenu
  └── Web3Signer.kt      # Signature de transactions
```

## Build

```bash
./gradlew assembleDebug
```

## Licence

MIT
