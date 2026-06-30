# PixOS

Application mobile principale Pixel OS — dashboard, tâches, wallet, DAO, paramètres.

## Écrans

| Écran | Rôle |
|-------|------|
| Connect | Connexion au serveur PixCore (URL + token PixKey) |
| Dashboard | Statut serveur, résumé capteurs/robots/alertes |
| Tasks | Liste des missions agricoles |
| Wallet | Solde BITROOT, import clé, historique |
| DAO | Propositions, votes, résultats |
| Settings | Déconnexion, mode nœud, infos compte |

## Build

```bash
./gradlew assembleDebug
```

## Dépendances

- `pixcore-android` (SDK)
- Jetpack Compose
- Material3
- Navigation Compose

## Licence

MIT
