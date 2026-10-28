"""
Détecte qui est en partie (Spectator-V5) et écrit data/live.json.
Pour chaque partie en cours : les 10 joueurs, leur champion, leurs sorts et leur rang solo/duo.
Lancé toutes les 5 minutes par .github/workflows/live.yml
"""
import hashlib, json, os, time, requests
from pathlib import Path
from roles import load_roles, assign_roles

KEY = os.environ["RIOT_API_KEY"]
H = {"X-Riot-Token": KEY}
REGION = "https://euw1.api.riotgames.com"
ROUTING = "https://europe.api.riotgames.com"
D = Path("data"); D.mkdir(exist_ok=True)
SOLO_QUEUE = 420  # classée solo/duo
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


try:
    _pl = json.loads(Path("players.json").read_text(encoding="utf-8"))
except json.JSONDecodeError as e:
    raise SystemExit(f"players.json invalide (ligne {e.lineno}) : {e.msg}")
players = [p for p in _pl if isinstance(p, dict) and "#" in str(p.get("riot", ""))][:20]
# Les PUUID dépendent de la clé API : si la clé change, on repart de zéro.
KEYH = hashlib.sha256(KEY.encode()).hexdigest()[:10]
_c = load(D / "puuids_live.json", {})
same_key = _c.get("key") == KEYH
puuids = _c.get("ids", {}) if same_key else {}
rank_cache = load(D / "rank_cache.json", {}) if same_key else {}
old = load(D / "live.json", {"games": {}, "players": {}})

# 1. Qui est en partie ?
ignored = {}   # riot -> file de la partie ignorée (hors solo/duo)
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
        if g.get("gameQueueConfigId") == SOLO_QUEUE:   # seulement la classée solo/duo (pas draft, aram, flex…)
            in_game[riot] = g
        else:
            ignored[riot] = g.get("gameQueueConfigId")
            print(f"{riot} est en partie hors solo/duo (file {g.get('gameQueueConfigId')}) : ignorée")
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
roles_data = None
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
    # Postes : top, jungle, mid, bot, support (estimés), équipe bleue puis rouge
    if roles_data is None:
        roles_data = load_roles(D / "roles_cache.json")
    parts = [p for team in (100, 200)
             for p in assign_roles([x for x in parts if x["team"] == team], roles_data)]
    games[gid] = {"id": gid, "queue": g.get("gameQueueConfigId", 0),
                  "start": g.get("gameStartTime", 0), "players": parts}

new = {"v": 2, "games": games, "players": by_player, "ignored": ignored}
# On n'écrit que si quelque chose a changé (sinon GitHub se remplirait de commits inutiles)
if new != {"v": old.get("v"), "games": old.get("games"), "players": old.get("players"), "ignored": old.get("ignored", {})}:
    new["checked"] = int(time.time())
    (D / "live.json").write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    print("live.json mis à jour :", list(by_player) or "personne en partie")
else:
    print("rien de changé")

current = {p["riot"] for p in players}
(D / "puuids_live.json").write_text(json.dumps(
    {"key": KEYH, "ids": {k: v for k, v in puuids.items() if k in current}}, indent=1), encoding="utf-8")
(D / "rank_cache.json").write_text(json.dumps(rank_cache), encoding="utf-8")
