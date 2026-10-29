"""
Met à jour les données du site SoloQ Challenge.

Pour chaque joueur de players.json :
  - rang solo/duo actuel (tier, division, LP, victoires, défaites)  -> data/ranking.json
  - historique des LP (un point à chaque changement)                  -> data/history.json
  - toutes les parties classées depuis le début du challenge          -> data/games.json
  - statistiques, records et vis-à-vis calculés à partir des parties  -> data/stats.json
Lancé automatiquement par GitHub Actions (voir .github/workflows/update.yml).
"""
import hashlib, json, os, re, time, unicodedata, requests
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
    for attempt in range(5):
        time.sleep(1.3)  # reste sous 100 requêtes / 2 min
        try:
            r = requests.get(url, headers=H, params=params, timeout=20)
        except requests.RequestException:      # coupure réseau passagère
            if attempt == 4:
                raise
            time.sleep(3)
            continue
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)) + 1)
            continue
        if r.status_code >= 500 and attempt < 4:   # panne passagère côté Riot
            time.sleep(3 * (attempt + 1))
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
# fin du challenge : le dernier jour est inclus (jusqu'à 23 h 59 heure de Paris)
END_TS = int(datetime.fromisoformat(config["end"]).replace(tzinfo=ZoneInfo("Europe/Paris")).timestamp()) + 86400 - 1
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
        out.append({"name": str(p.get("name") or riot.split("#")[0]), "riot": riot, "avatar_cfg": p.get("avatar")})
    return out[:20]


players = read_players()


# ---------- photos de profil (dossier avatars/) ----------
AVATAR_EXT = ("png", "jpg", "jpeg", "webp", "gif")
MAX_AVATAR = 1_000_000   # au-delà, la page deviendrait lourde


def slug(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())


AV_FILES = {}
if Path("avatars").is_dir():
    for f in sorted(Path("avatars").iterdir()):
        if f.is_file() and f.suffix.lower().lstrip(".") in AVATAR_EXT:
            AV_FILES.setdefault(slug(f.stem), f)


def avatar_for(p):
    """Photo de 'avatars/' dont le nom correspond au prénom du joueur (ex. avatars/kuro.png),
    ou le fichier indiqué par "avatar" dans players.json."""
    f = None
    cfg = p.get("avatar_cfg")
    if cfg:
        c = Path(str(cfg))
        if not c.is_absolute() and ".." not in c.parts and c.is_file():
            f = c
        else:
            errors.append({"riot": p["riot"], "msg": f"photo introuvable : {cfg}"})
    if f is None:
        f = AV_FILES.get(slug(p["name"])) or AV_FILES.get(slug(p["riot"].split("#")[0]))
    if f is None:
        return None
    size = f.stat().st_size
    if size > MAX_AVATAR:
        errors.append({"riot": p["riot"], "msg": f"photo trop lourde ({size / 1e6:.1f} Mo) : réduis-la sous 1 Mo"})
        return None
    return f"{f.as_posix()}?v={hashlib.md5(f.read_bytes()).hexdigest()[:8]}"


av_map = {p["riot"]: avatar_for(p) for p in players}
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
                      queue=SOLO_QUEUE, startTime=START_TS, endTime=END_TS, start=page * 100, count=100) or []
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
        # [joueur, équipe, victoire, champion, kills, morts, assists,
        #  sbires tués, dégâts aux champions, score de vision, premier sang, pentakills]
        rows.append([pid, x["teamId"], 1 if x["win"] else 0, x["championName"],
                     x["kills"], x["deaths"], x["assists"],
                     x.get("totalMinionsKilled", 0) + x.get("neutralMinionsKilled", 0),
                     x.get("totalDamageDealtToChampions", 0), x.get("visionScore", 0),
                     1 if x.get("firstBloodKill") else 0, x.get("pentaKills", 0)])
    g = {"v": 2, "t": t, "d": inf.get("gameDuration", 0), "q": inf.get("queueId", 0), "p": rows}
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
# Anciennes parties enregistrées sans les données avancées : on les re-télécharge peu à peu
stale = sorted((m for m, g in games.items() if g.get("v", 1) < 2 and g.get("t", 0) >= START_TS),
               key=mid_num, reverse=True)
for m in stale:
    if m not in seen:
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
    champs, last10, ids_l = [], "", []
    for mid in i["last10"]:
        g = games.get(mid)
        if not g or g.get("r"):
            continue
        me = next((x for x in g["p"] if x[0] == riot.lower()), None)
        if me:
            champs.append(me[3]); ids_l.append(mid)
            last10 += "W" if me[2] else "L"
    result[riot]["champs"], result[riot]["last10"] = champs, last10
    result[riot]["ids"] = ids_l

# ---------- 3b. LP gagnés / perdus par partie ----------
# Riot ne donne pas ce chiffre : on le déduit. Si le total de parties classées d'un joueur a augmenté d'exactement 1
# depuis notre dernier passage, la variation de LP vient de cette partie (sinon on ne peut pas trancher, on ne dit rien).
TIERS_ = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]


def lp_score(tier, div, lp):
    i = TIERS_.index(tier)
    return 2800 + lp if i >= 7 else i * 400 + (4 - div) * 100 + lp


lp_track = load(D / "lp_track.json", {})
lp_delta = load(D / "lp_delta.json", {})
now = int(time.time())
for riot in fresh_riots:
    r = result[riot]
    if r["unranked"]:
        continue
    sc, wl = lp_score(r["tier"], r["div"], r["lp"]), r["w"] + r["l"]
    prev = lp_track.get(riot)
    ids_ = info[riot]["since"]
    if prev and wl == prev["wl"] + 1 and ids_ and ids_[0] not in lp_delta.get(riot, {}):
        g_ = games.get(ids_[0])
        if not g_ or g_["t"] >= prev["t"] - 600:   # la partie doit être postérieure à notre dernier passage
            lp_delta.setdefault(riot, {})[ids_[0]] = sc - prev["s"]
    lp_track[riot] = {"wl": wl, "s": sc, "t": now}
for riot in list(lp_delta):
    if riot not in {p_["riot"] for p_ in players}:
        del lp_delta[riot]
    else:   # on ne garde que les parties récentes
        keep_ = set(info.get(riot, {}).get("since", [])) | set(info.get(riot, {}).get("last10", []))
        lp_delta[riot] = {m: d for m, d in lp_delta[riot].items() if m in keep_ or not info.get(riot)}

for riot in info:
    ds_ = [d for _, d in sorted(lp_delta.get(riot, {}).items(), key=lambda kv: mid_num(kv[0]), reverse=True)]   # du plus récent au plus ancien
    result[riot]["lplast"] = {"win": next((d for d in ds_ if d > 0), None),    # dernier gain de LP
                              "loss": next((d for d in ds_ if d < 0), None)}   # dernière perte de LP
    result[riot]["lpd"] = [lp_delta.get(riot, {}).get(m) for m in result[riot].get("ids", [])]
    result[riot].pop("ids", None)

# ---------- 4. historique des LP ----------
for riot in fresh_riots:
    r = result[riot]
    if r["unranked"] or now > END_TS:   # après la fin, la courbe est figée
        continue
    point = [now, r["tier"], r["div"], r["lp"]]
    h = history.setdefault(riot, [])
    if not h or h[-1][1:] != point[1:]:
        h.append(point)

# ---------- 5. nettoyage + écriture ----------
keep = {m for i in info.values() for m in i["last10"]}
for mid in [m for m, g in games.items() if g["t"] < START_TS and m not in keep]:
    del games[mid]

save("lp_delta.json", lp_delta, separators=(",", ":"))
current_ = {p_["riot"] for p_ in players}
for k_ in [k for k in history if k not in current_]:
    del history[k_]
for k_ in [k for k in lp_track if k not in current_]:
    del lp_track[k_]
save("lp_track.json", lp_track, separators=(",", ":"))
save("games.json", games, separators=(",", ":"))
save("history.json", history, separators=(",", ":"))
stats = build_stats(games, players, START_TS, now, END_TS)
for riot_, pl_ in stats["players"].items():
    pl_["avatar"] = av_map.get(riot_)
    # joueur pas encore classé (parties de placement) : on affiche ses parties du challenge à la place des totaux de saison
    if riot_ in result and result[riot_].get("unranked"):
        result[riot_]["w"], result[riot_]["l"] = pl_["wins"], pl_["losses"]
save("stats.json", stats, separators=(",", ":"))

# Le classement reflète toujours players.json (ajouts ET retraits).
# Seule exception : si tout a échoué on garde l'ancien fichier plutôt que d'afficher un site vide.
for riot_, r_ in result.items():
    r_["avatar"] = av_map.get(riot_)
ordered = [result[p["riot"]] for p in players if p["riot"] in result]
if ordered or not players:
    prev_updated = load(D / "ranking.json", {}).get("updated", 0)
    save("ranking.json", {"updated": now if fresh_riots else prev_updated, "key_ok": key_ok,
                          "start": config["start"], "end": config["end"],
                          "errors": errors, "players": ordered}, indent=1)
