"""
Devine le poste (top, jungle, mid, bot, support) de chaque joueur d'une partie en cours.
Riot ne fournit pas cette information pour une partie en direct : on l'estime à partir
  1. des postes où chaque champion est le plus joué (données Meraki Analytics),
  2. du sort Châtiment (le jungler le prend presque toujours),
  3. à défaut de données, des catégories du champion (Tireur, Soutien, Assassin...).
On choisit ensuite, pour chaque équipe, la répartition des 5 postes la plus probable.
"""
import itertools, json, time, requests
from pathlib import Path

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
SMITE = 11
MERAKI = "https://cdn.merakianalytics.com/riot/lol/resources/latest/en-US/championrates.json"
TTL = 86400  # on rafraîchit les données une fois par jour

# Secours quand on n'a pas les statistiques de poste : catégorie du champion -> postes probables
TAG_ROLES = {
    "Marksman": {"BOTTOM": 1.0},
    "Support": {"UTILITY": 1.0},
    "Assassin": {"MIDDLE": .6, "JUNGLE": .4},
    "Mage": {"MIDDLE": .8, "UTILITY": .2},
    "Fighter": {"TOP": .7, "JUNGLE": .3},
    "Tank": {"TOP": .4, "UTILITY": .3, "JUNGLE": .3},
}


def _fetch():
    """Télécharge les données (appelé depuis GitHub Actions, qui a accès à Internet).
    Aucune clé Riot n'est envoyée à ces sites."""
    v = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=20).json()[0]
    dd = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/champion.json",
                      timeout=30).json()["data"]
    tags = {str(c["key"]): c["tags"] for c in dd.values()}
    rates = {}
    try:
        mr = requests.get(MERAKI, timeout=30).json()
        for cid, per_role in (mr.get("data") or {}).items():
            d = {}
            for role, val in per_role.items():
                x = val.get("playRate") if isinstance(val, dict) else val
                if role in ROLES and isinstance(x, (int, float)) and x > 0:
                    d[role] = float(x)
            if d:
                rates[str(cid)] = d
    except Exception as e:
        print("! statistiques de poste indisponibles, on utilise les catégories :", e)
    return {"t": int(time.time()), "tags": tags, "rates": rates}


def load_roles(path):
    """Données en cache (valables 24 h). En cas d'échec réseau on garde l'ancien cache."""
    path = Path(path)
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    if cache.get("t", 0) > time.time() - TTL:
        return cache
    try:
        cache = _fetch()
        path.write_text(json.dumps(cache), encoding="utf-8")
    except Exception as e:
        print("! données de poste non rafraîchies :", e)
    return cache


def _weights(champ, data):
    """Poids de chaque poste pour un champion, normalisés (somme = 1)."""
    cid = str(champ)
    w = dict(data.get("rates", {}).get(cid, {}))
    if not w:
        for tag in data.get("tags", {}).get(cid, []):
            for role, x in TAG_ROLES.get(tag, {}).items():
                w[role] = w.get(role, 0) + x
    total = sum(w.values())
    return {r: x / total for r, x in w.items()} if total else {}


def assign_roles(team, data):
    """Ajoute p['role'] à chacun des 5 joueurs d'une équipe, et renvoie la liste triée
    top, jungle, mid, bot, support. Si on ne peut pas décider, l'ordre d'origine est gardé."""
    if len(team) != 5 or not (data.get("rates") or data.get("tags")):
        return team
    scores = []
    for p in team:
        w = _weights(p["champ"], data)
        row = {}
        for r in ROLES:
            s = w.get(r, 0.0)
            if SMITE in p["spells"]:
                s += 2.0 if r == "JUNGLE" else -0.5   # Châtiment = quasi toujours jungle
            elif r == "JUNGLE":
                s -= 0.3                              # sans Châtiment, rarement jungle
            row[r] = s
        scores.append(row)
    best, best_total = None, None
    for perm in itertools.permutations(ROLES):
        total = sum(scores[i][perm[i]] for i in range(5))
        if best_total is None or total > best_total:
            best, best_total = perm, total
    for p, role in zip(team, best):
        p["role"] = role
    return sorted(team, key=lambda p: ROLES.index(p["role"]))
