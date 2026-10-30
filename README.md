# SoloQ Challenge

Site automatique de classement League of Legends (EUW, solo/duo) entre amis.

## Ajouter / retirer un joueur
- **Mode admin** : clique 10 fois vite sur le logo, colle ta clé GitHub (Contents : lecture/écriture sur ce dépôt), puis modifie joueurs, photos et dates.
- **À la main** : édite `players.json` (`{"name": "Kuro", "riot": "Pseudo#TAG"}`) et dépose la photo dans `avatars/`.

## Dates
`config.json` : `start` et `end` (AAAA-MM-JJ).

## Fonctionnement
- `update.yml` met à jour classement et stats (GitHub Actions), `live.yml` suit les parties en direct.
- Clé Riot : secret `RIOT_API_KEY` du dépôt.
- Si le site ne se met plus à jour : onglet Actions du dépôt, puis « Run workflow ».
