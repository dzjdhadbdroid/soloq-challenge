"""
Détecte qui est en partie (Spectator-V5) et écrit data/live.json.
Pour chaque partie en cours : les 10 joueurs, leur champion, leurs sorts et leur rang solo/duo.
Lancé toutes les 5 minutes par .github/workflows/live.yml
"""
import json, os, time, requests
from pathlib import Path

KEY = os.environ["RIOT_API_KEY"]
H = {"X-Riot-Token": KEY}
REGION = "https://euw1.api.riotgames.com"
ROUTING = "https://europe.api.riotgames.com"
D = Path("data"); D.mkdir(exist_ok=True)
RANK_TTL = 3600  # on ne redemande le rang d'un joueur qu'une fois par heure
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def get(url):
    """Renvoie (code, json). 404 = pas de résultat. Autre erreur = code != 200/404."""
    for _ in range(4):
        time.sleep(1.3)
        try:
            r = requests.get(url, headers=H, timeout=20)
        except requests.RequestException:
            return 0, None
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)) + 1)
            continue
        if r.status_code == 200:
            return 200, r.json()
        return r.status_code, None
    return 429, None


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


players = json.loads(Path("players.json").read_text(encoding="utf-8"))[:20]
puuids = load(D / "puuids.json", {})
rank_cache = load(D / "rank_cache.json", {})
old = load(D / "live.json", {"games": {}, "players": {}})

# 1. Qui est en partie ?
in_game = {}   # riot -> données de la partie
failed = False
for p in players:
    riot = p["riot"]
    if riot not in puuids:
        name, tag = riot.rsplit("#", 1)
        code, acc = get(f"{ROUTING}/riot/account/v1/accounts/by-riot-id/{name}/{tag}")
        if code == 200:
            puuids[riot] = acc["puuid"]
        else:
            print(f"! compte introuvable ou erreur {code} : {riot}")
            continue
    code, g = get(f"{REGION}/lol/spectator/v5/active-games/by-summoner/{puuids[riot]}")
    if code == 200:
        in_game[riot] = g
    elif code != 404:
        print(f"! erreur {code} pour {riot}")
        failed = True

if failed:  # en cas de doute on ne touche à rien (évite de faire disparaître une partie à tort)
    print("Erreur API : live.json inchangé")
    raise SystemExit(0)


def rank_of(puuid):
    c = rank_cache.get(puuid)
    if c and time.time() - c["t"] < RANK_TTL:
        return c["rank"]
    code, entries = get(f"{REGION}/lol/league/v4/entries/by-puuid/{puuid}")
    rank = None
    if code == 200:
        solo = next((e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"), None)
        if solo:
            t = solo["tier"]
            rank = {"tier": t,
                    "div": 1 if t in ("MASTER", "GRANDMASTER", "CHALLENGER") else ROMAN[solo["rank"]],
                    "lp": solo["leaguePoints"]}
        rank_cache[puuid] = {"t": time.time(), "rank": rank}
    return rank


# 2. Détails de chaque partie (une seule fois même si plusieurs potes y sont)
games, by_player = {}, {}
for riot, g in in_game.items():
    gid = str(g["gameId"])
    by_player[riot] = gid
    if gid in games:
        continue
    mine = {puuids[r] for r, x in in_game.items() if str(x["gameId"]) == gid}
    friends = {puuids[r]: r for r in in_game if str(in_game[r]["gameId"]) == gid}
    parts = []
    for x in g["participants"]:
        parts.append({
            "name": x.get("riotId") or x.get("summonerName", "?"),
            "champ": x["championId"],
            "spells": [x["spell1Id"], x["spell2Id"]],
            "team": x["teamId"],
            "friend": friends.get(x["puuid"]),
            "rank": rank_of(x["puuid"]),
        })
    games[gid] = {"id": gid, "queue": g.get("gameQueueConfigId", 0),
                  "start": g.get("gameStartTime", 0), "players": parts}

new = {"games": games, "players": by_player}
# On n'écrit que si quelque chose a changé (sinon GitHub se remplirait de commits inutiles)
if new != {"games": old.get("games"), "players": old.get("players")}:
    new["checked"] = int(time.time())
    (D / "live.json").write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    print("live.json mis à jour :", list(by_player) or "personne en partie")
else:
    print("rien de changé")

(D / "puuids.json").write_text(json.dumps(puuids, indent=1), encoding="utf-8")
(D / "rank_cache.json").write_text(json.dumps(rank_cache), encoding="utf-8")
