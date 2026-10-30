# SoloQ Challenge

Site gratuit et automatique pour un challenge League of Legends entre amis : classement, statistiques, parties en direct et cartes de joueur à partager.

- Serveur : EUW, file **solo/duo classée uniquement** (queue 420). Flex, ARAM et normales ne comptent pas.
- Jusqu'à 20 joueurs, un challenge de 30 jours.
- Tout tourne sur GitHub (Actions + Pages) avec l'API Riot. Aucun serveur à payer.

## Ce que fait le site

| Page | Contenu |
|---|---|
| **Classement** | Podium, tableau (rang, LP, victoires, défaites, winrate, derniers LP gagnés/perdus, 10 dernières parties), courbe de LP au clic sur un joueur, parties en direct, carte de joueur à télécharger/partager |
| **Statistiques** | Records (pire/meilleur KDA, séries, kills, morts, pentakills, premier sang, farm, dégâts, vision), stats par joueur, comparateur de deux joueurs, vis-à-vis |
| **Partie en cours** | Équipes, champions et rôles d'une partie en direct |

Un bouton 🌙 / ☀ change entre mode clair et mode sombre.

## Comment ça marche

Deux workflows GitHub Actions (dossier `.github/workflows/`) :

- **`update.yml`** : récupère rangs et parties via l'API Riot, calcule les stats et enregistre le résultat dans `data/`. Il se lance aussi dès que `players.json`, `config.json` ou `avatars/` changent, ou à la main.
- **`live.yml`** : surveille les parties en cours (solo/duo seulement), à la minute près pendant ~25 minutes à chaque passage.

GitHub retarde souvent les tâches planifiées : le classement se met à jour environ toutes les 45 à 60 minutes, pas toutes les 5. Pour forcer une mise à jour : onglet **Actions** → **update-ranking** → **Run workflow**.

| Fichier | Rôle |
|---|---|
| `players.json` | Liste des joueurs |
| `config.json` | Dates du challenge |
| `avatars/` | Photos de profil |
| `update.py`, `stats.py`, `live.py`, `roles.py` | Récupération Riot et calculs |
| `index.html`, `stats.html`, `game.html`, `theme.css`, `theme.js`, `card.js`, `admin.js` | Le site |
| `data/` | Résultats, écrits par le robot (ne pas modifier à la main) |

## Installation (une seule fois)

1. **Clé Riot** : crée une clé sur le [portail développeur Riot](https://developer.riotgames.com). Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**, nom `RIOT_API_KEY`.
2. **GitHub Pages** : **Settings → Pages**, source « Deploy from a branch », branche `main`, dossier `/ (root)`.
3. **Actions** : **Settings → Actions → General → Workflow permissions** → « Read and write permissions ».
4. Adapte `players.json` et `config.json` (voir ci-dessous).

## Gérer les joueurs

### Avec le mode admin (le plus simple)

1. Sur le site, clique **10 fois vite sur le logo** en haut à gauche.
2. Colle ta clé GitHub (voir ci-dessous), puis **Se connecter**.
3. Ajoute ou retire des joueurs, change les photos et les dates, puis **Enregistrer les changements**.

Le formulaire modifie directement les fichiers du dépôt : `players.json`, `config.json` et le dossier `avatars/` (la photo d'un joueur retiré est supprimée). Le site se met à jour 1 à 3 minutes après.

**Créer la clé GitHub** : GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.
- Repository access : **Only select repositories** → ce dépôt uniquement.
- Permissions : **Contents → Read and write** (Metadata en lecture seule se met toute seule). Rien d'autre, surtout pas Administration.
- Copie la clé `github_pat_…` : elle reste dans ton navigateur uniquement. Si elle expire, recrée-en une.

### À la main

`players.json` :

```json
[
  { "name": "Kuro", "riot": "Pseudo#TAG" },
  { "name": "Flo", "riot": "Flozz#176", "avatar": "avatars/flo.png" }
]
```

- `name` : le prénom affiché.
- `riot` : le Riot ID complet (pseudo#tag), tel qu'il apparaît dans le jeu.
- `avatar` (facultatif) : chemin de la photo ; sinon le site cherche `avatars/<prenom>.png|jpg|jpeg|webp|gif`.

Ajoute la photo dans `avatars/` (carrée, ~256 px, moins de 500 Ko).

## Dates du challenge

`config.json` :

```json
{ "start": "2026-10-22", "end": "2026-11-22" }
```

Seules les parties classées jouées entre ces deux dates comptent.

## Comptes sans rang (unranked)

Un joueur qui n'a pas encore de rang apparaît quand même : le tableau affiche ses victoires/défaites du challenge, il est classé sous les joueurs classés et n'entre pas dans le podium. Il rejoint le classement par elo dès qu'il a fini ses parties de placement.

## Règles de calcul

- **Classement** : rang puis LP (Fer → Challenger).
- **LP gagnés/perdus** : déduits quand une seule partie s'est jouée entre deux mises à jour. S'il y en a eu plusieurs, la variation est inconnue et n'est pas affichée.
- **Records** : un minimum de 5 parties classées est demandé pour les moyennes (KDA, morts par partie, farm, vision), pour éviter les records sur 1 ou 2 parties.

## Dépannage

| Problème | Solution |
|---|---|
| Le site n'est pas à jour | Actions → update-ranking → Run workflow, puis Ctrl+F5 |
| « Compte introuvable » | Vérifie le Riot ID (pseudo#tag) dans `players.json` |
| Plus aucune donnée / erreur 403 | La clé Riot a expiré : remplace le secret `RIOT_API_KEY` |
| Une partie en direct n'apparaît pas | Seules les parties solo/duo classées s'affichent |
| Une photo n'apparaît pas | Nom de fichier = prénom (sans accent ni espace), ou champ `avatar` ; attends 1 à 2 minutes |
| Le mode admin refuse d'enregistrer | La clé GitHub est mauvaise, expirée ou n'a pas **Contents : Read and write** |
| Un workflow est rouge | Relance-le à la main ; les erreurs viennent souvent d'un conflit de commit ou de la limite de requêtes Riot |

---

Projet fait entre amis, non affilié à Riot Games. League of Legends est une marque de Riot Games, Inc.
