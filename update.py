"""
Met à jour data/ranking.json pour le SoloQ Challenge.
Pour chaque joueur de players.json :
  - rang solo/duo actuel (tier, division, LP, victoires, défaites)
  - 10 dernières parties classées (champion + victoire/défaite)
Lancé automatiquement par GitHub Actions (voir .github/workflows/update.yml).
"""
import json, os, time, requests
from pathlib import Path

KEY = os.environ["RIOT_API_KEY"]
H = {"X-Riot-Token": KEY}
REGION = "https://euw1.api.riotgames.com"      # rang (plateforme)
ROUTING = "https://europe.api.riotgames.com"   # comptes + matchs
SOLO_QUEUE = 420
D = Path("data"); D.mkdir(exist_ok=True)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def get(url, **params):
    """GET avec pause anti rate-limit et gestion du 429."""
    for _ in range(5):
        time.sleep(1.3)  # reste sous 100 requêtes / 2 min
        r = requests.get(url, headers=H, params=params, timeout=20)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)) + 1)
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    raise RuntimeError("trop de requêtes (429) : réessai au prochain passage")


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


# players.json : [{"name": "Kaori", "riot": "Kaori#EUW33"}, ...]
errors = []   # problèmes affichés sur le site


def read_players():
    try:
        data = json.loads(Path("players.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERREUR dans players.json (ligne {e.lineno}) : {e.msg}. "
                         "Vérifie qu'il y a une virgule à la fin de chaque ligne sauf la dernière.")
    out, seen = [], set()
    for n, p in enumerate(data, 1):
        riot = str(p.get("riot", "")).strip() if isinstance(p, dict) else ""
        if "#" not in riot:
            errors.append({"riot": riot or f"joueur n°{n}", "msg": "il manque le #tag (format Pseudo#TAG)"})
            continue
        if riot.lower() in seen:
            continue
        seen.add(riot.lower())
        out.append({"name": str(p.get("name") or riot.split("#")[0]), "riot": riot})
    return out[:20]


players = read_players()
matches = load(D / "matches.json", {})    # matchId -> infos déjà téléchargées
old = {p["riot"]: p for p in load(D / "ranking.json", {}).get("players", [])}

result, fresh, key_ok = [], 0, True
for p in players:
    riot = p["riot"]
    try:
        # 1. PUUID (toujours recalculé : il dépend de la clé API)
        name, tag = riot.rsplit("#", 1)
        acc = get(f"{ROUTING}/riot/account/v1/accounts/by-riot-id/{name}/{tag}")
        if not acc:
            print(f"! compte introuvable : {riot}")
            errors.append({"riot": riot, "msg": "compte introuvable, vérifie le pseudo et le tag"})
            continue
        puuid = acc["puuid"]

        # 2. Rang solo/duo
        entries = get(f"{REGION}/lol/league/v4/entries/by-puuid/{puuid}") or []
        solo = next((e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"), None)
        unranked = solo is None
        if solo:
            tier = solo["tier"]
            div = 1 if tier in ("MASTER", "GRANDMASTER", "CHALLENGER") else ROMAN[solo["rank"]]
            lp, w, l = solo["leaguePoints"], solo["wins"], solo["losses"]
        else:  # joueur non classé
            tier, div, lp, w, l = "IRON", 4, 0, 0, 0

        # 3. 10 dernières parties classées solo/duo
        ids = get(f"{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids",
                  queue=SOLO_QUEUE, start=0, count=10) or []
        champs, last10 = [], ""
        for mid in ids:
            if mid not in matches:
                m = get(f"{ROUTING}/lol/match/v5/matches/{mid}")
                if not m:
                    continue
                matches[mid] = {x["puuid"]: {"win": x["win"], "champ": x["championName"]}
                                for x in m["info"]["participants"]}
            me = matches[mid].get(puuid)
            if me:
                champs.append(me["champ"])
                last10 += "W" if me["win"] else "L"

        result.append({"name": p["name"], "riot": riot, "tier": tier, "div": div,
                       "lp": lp, "w": w, "l": l, "champs": champs, "last10": last10,
                       "unranked": unranked})
        fresh += 1
        print(f"ok {riot} : {tier} {div} {lp} LP")
    except Exception as e:
        print(f"! erreur sur {riot} : {e}")
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (401, 403):
            key_ok = False
        if riot in old:   # erreur passagère : on garde la dernière valeur connue
            result.append({**old[riot], "name": p["name"]})
        else:
            errors.append({"riot": riot, "msg": "données indisponibles pour l'instant, réessai au prochain passage"})

# On ne garde en cache que les 200 derniers matchs (le fichier reste léger)
for mid in list(matches)[:-200]:
    del matches[mid]
(D / "matches.json").write_text(json.dumps(matches), encoding="utf-8")

# Le classement reflète toujours players.json (ajouts ET retraits).
# Seule exception : si tout a échoué on garde l'ancien fichier plutôt que d'afficher un site vide.
if result or not players:
    prev_updated = load(D / "ranking.json", {}).get("updated", 0)
    (D / "ranking.json").write_text(json.dumps(
        {"updated": int(time.time()) if fresh else prev_updated,
         "key_ok": key_ok, "errors": errors, "players": result},
        indent=1, ensure_ascii=False), encoding="utf-8")
