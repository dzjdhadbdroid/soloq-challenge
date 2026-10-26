"""
Met à jour les données du site SoloQ Challenge.

Pour chaque joueur de players.json :
  - rang solo/duo actuel (tier, division, LP, victoires, défaites)  -> data/ranking.json
  - historique des LP (un point à chaque changement)                  -> data/history.json
  - toutes les parties classées depuis le début du challenge          -> data/games.json
  - statistiques, records et vis-à-vis calculés à partir des parties  -> data/stats.json
Lancé automatiquement par GitHub Actions (voir .github/workflows/update.yml).
"""
import json, os, time, requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from stats import build_stats

KEY = os.environ["RIOT_API_KEY"]
H = {"X-Riot-Token": KEY}
REGION = "https://euw1.api.riotgames.com"      # rang (plateforme)
ROUTING = "https://europe.api.riotgames.com"   # comptes + matchs
SOLO_QUEUE = 420
D = Path("data"); D.mkdir(exist_ok=True)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
MAX_NEW_MATCHES = 80       # parties téléchargées au maximum par passage (le reste au passage suivant)
MAX_SECONDS = 20 * 60      # garde-fou : on s'arrête de télécharger après 20 min
T0 = time.time()


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
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except json.JSONDecodeError:
        return default


def save(name, data, **kw):
    (D / name).write_text(json.dumps(data, ensure_ascii=False, **kw), encoding="utf-8")


# ---------- configuration ----------
config = load(Path("config.json"), {"start": "2026-10-22", "end": "2026-11-22"})
START_TS = int(datetime.fromisoformat(config["start"]).replace(tzinfo=ZoneInfo("Europe/Paris")).timestamp())
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
games = load(D / "games.json", {})        # matchId -> partie (voir stats.py)
history = load(D / "history.json", {})    # joueur -> [[t, tier, div, lp], ...]
old = {p["riot"]: p for p in load(D / "ranking.json", {}).get("players", [])}

# ---------- 1. rang + liste des parties de chaque joueur ----------
result, fresh_riots, key_ok = {}, set(), True
info = {}   # riot -> {"puuid", "last10": [ids], "since": [ids]}
for p in players:
    riot = p["riot"]
    try:
        name, tag = riot.rsplit("#", 1)
        acc = get(f"{ROUTING}/riot/account/v1/accounts/by-riot-id/{name}/{tag}")   # PUUID : dépend de la clé API
        if not acc:
            print(f"! compte introuvable : {riot}")
            errors.append({"riot": riot, "msg": "compte introuvable, vérifie le pseudo et le tag"})
            continue
        puuid = acc["puuid"]

        entries = get(f"{REGION}/lol/league/v4/entries/by-puuid/{puuid}") or []
        solo = next((e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"), None)
        unranked = solo is None
        if solo:
            tier = solo["tier"]
            div = 1 if tier in ("MASTER", "GRANDMASTER", "CHALLENGER") else ROMAN[solo["rank"]]
            lp, w, l = solo["leaguePoints"], solo["wins"], solo["losses"]
        else:
            tier, div, lp, w, l = "IRON", 4, 0, 0, 0

        since = []
        for page in range(5):   # jusqu'à 500 parties depuis le début du challenge
            ids = get(f"{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids",
                      queue=SOLO_QUEUE, startTime=START_TS, start=page * 100, count=100) or []
            since += ids
            if len(ids) < 100:
                break
        last10 = since[:10] if len(since) >= 10 else (
            get(f"{ROUTING}/lol/match/v5/matches/by-puuid/{puuid}/ids",
                queue=SOLO_QUEUE, start=0, count=10) or [])

        info[riot] = {"puuid": puuid, "last10": last10, "since": since}
        result[riot] = {"name": p["name"], "riot": riot, "tier": tier, "div": div,
                        "lp": lp, "w": w, "l": l, "champs": [], "last10": "", "unranked": unranked}
        fresh_riots.add(riot)
        print(f"ok {riot} : {tier} {div} {lp} LP ({len(since)} parties depuis le début)")
    except Exception as e:
        print(f"! erreur sur {riot} : {e}")
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (401, 403):
            key_ok = False
        if riot in old:   # erreur passagère : on garde la dernière valeur connue
            result[riot] = {**old[riot], "name": p["name"]}
        else:
            errors.append({"riot": riot, "msg": "données indisponibles pour l'instant, réessai au prochain passage"})

# ---------- 2. téléchargement des nouvelles parties ----------
friend_by_puuid = {i["puuid"]: r.lower() for r, i in info.items()}


def ingest(mid, m):
    inf = m["info"]
    end_ms = inf.get("gameEndTimestamp")
    t = end_ms // 1000 if end_ms else inf.get("gameCreation", 0) // 1000 + inf.get("gameDuration", 0)
    rows = []
    for x in inf["participants"]:
        pid = friend_by_puuid.get(x["puuid"])
        if not pid:
            pid = f'{x.get("riotIdGameName") or x.get("summonerName") or "?"}#{x.get("riotIdTagline") or ""}'.lower()
        rows.append([pid, x["teamId"], 1 if x["win"] else 0, x["championName"],
                     x["kills"], x["deaths"], x["assists"]])
    g = {"t": t, "d": inf.get("gameDuration", 0), "q": inf.get("queueId", 0), "p": rows}
    if any(x.get("gameEndedInEarlySurrender") for x in inf["participants"]) and g["d"] < 300:
        g["r"] = 1   # remake : ne compte pas
    games[mid] = g


def mid_num(mid):
    return int(mid.rsplit("_", 1)[-1])


priority = [m for i in info.values() for m in i["last10"]]                       # d'abord les 10 dernières parties
rest = sorted({m for i in info.values() for m in i["since"]}, key=mid_num, reverse=True)   # puis les plus récentes
todo, seen = [], set()
for m in priority + rest:
    if m not in games and m not in seen:
        seen.add(m); todo.append(m)

downloaded = failures = 0
for mid in todo:
    if downloaded >= MAX_NEW_MATCHES or time.time() - T0 > MAX_SECONDS or failures >= 3:
        break
    try:
        m = get(f"{ROUTING}/lol/match/v5/matches/{mid}")
        if m:
            ingest(mid, m)
            downloaded += 1
            failures = 0
    except Exception as e:
        failures += 1
        print(f"! partie {mid} : {e}")
        if getattr(getattr(e, "response", None), "status_code", None) in (401, 403):
            key_ok = False
print(f"{downloaded} nouvelles parties téléchargées, {max(0, len(todo) - downloaded)} en attente")

# ---------- 3. 10 dernières parties de chaque joueur ----------
for riot, i in info.items():
    champs, last10 = [], ""
    for mid in i["last10"]:
        g = games.get(mid)
        if not g or g.get("r"):
            continue
        me = next((x for x in g["p"] if x[0] == riot.lower()), None)
        if me:
            champs.append(me[3])
            last10 += "W" if me[2] else "L"
    result[riot]["champs"], result[riot]["last10"] = champs, last10

# ---------- 4. historique des LP ----------
now = int(time.time())
for riot in fresh_riots:
    r = result[riot]
    if r["unranked"]:
        continue
    point = [now, r["tier"], r["div"], r["lp"]]
    h = history.setdefault(riot, [])
    if not h or h[-1][1:] != point[1:]:
        h.append(point)

# ---------- 5. nettoyage + écriture ----------
keep = {m for i in info.values() for m in i["last10"]}
for mid in [m for m, g in games.items() if g["t"] < START_TS and m not in keep]:
    del games[mid]

save("games.json", games, separators=(",", ":"))
save("history.json", history, separators=(",", ":"))
save("stats.json", build_stats(games, players, START_TS, now), separators=(",", ":"))

# Le classement reflète toujours players.json (ajouts ET retraits).
# Seule exception : si tout a échoué on garde l'ancien fichier plutôt que d'afficher un site vide.
ordered = [result[p["riot"]] for p in players if p["riot"] in result]
if ordered or not players:
    prev_updated = load(D / "ranking.json", {}).get("updated", 0)
    save("ranking.json", {"updated": now if fresh_riots else prev_updated, "key_ok": key_ok,
                          "start": config["start"], "end": config["end"],
                          "errors": errors, "players": ordered}, indent=1)
