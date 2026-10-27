"""
Calcule les statistiques du challenge à partir des parties enregistrées (data/games.json).

Format d'une partie dans games.json :
  {"t": fin de partie (secondes), "d": durée (s), "q": file (420 = solo/duo),
   "p": [[joueur, équipe, victoire(0/1), champion, kills, morts, assists], ...]}
Le "joueur" est l'identifiant Riot en minuscules (ex. "kaori#euw33").
"""
from collections import defaultdict
from itertools import combinations

MIN_GAMES = 5   # nombre minimum de parties pour les records "à la moyenne"


def _streaks(results):
    """results : liste de 1/0 (victoire/défaite) triée du plus ancien au plus récent."""
    best_w = best_l = run = 0
    last = None
    for r in results:
        run = run + 1 if r == last else 1
        last = r
        if r:
            best_w = max(best_w, run)
        else:
            best_l = max(best_l, run)
    current = 0
    if results:
        current = run if results[-1] else -run
    return best_w, best_l, current


def build_stats(games, players, start_ts, now):
    """players : [{"name":..., "riot":...}]. Renvoie un dictionnaire prêt à être écrit en JSON."""
    by_id = {p["riot"].lower(): p for p in players}
    per = defaultdict(list)          # joueur -> [(t, win, champ, k, d, a, mid)]
    team_games = []                  # parties avec au moins un ami
    for mid, g in games.items():
        if g.get("t", 0) < start_ts or g.get("r"):   # avant le challenge, ou remake
            continue
        friends = [x for x in g["p"] if x[0] in by_id]
        if not friends:
            continue
        team_games.append((g, friends))
        for x in friends:
            pid, team, win, champ, k, d, a = x[:7]
            ex = x[7:12] if len(x) >= 12 else None   # sbires, dégâts, vision, premier sang, pentakills
            per[pid].append((g["t"], win, champ, k, d, a, mid, ex, g.get("d", 0)))

    out_players = {}
    for pid, rows in per.items():
        rows.sort()
        n = len(rows)
        wins = sum(r[1] for r in rows)
        k = sum(r[3] for r in rows); d = sum(r[4] for r in rows); a = sum(r[5] for r in rows)
        best_w, best_l, cur = _streaks([r[1] for r in rows])
        champs = defaultdict(lambda: [0, 0])
        for r in rows:
            champs[r[2]][0] += 1
            champs[r[2]][1] += r[1]
        top = sorted(champs.items(), key=lambda kv: (-kv[1][0], -kv[1][1], kv[0]))[:5]
        # données avancées (uniquement pour les parties enregistrées avec ces champs)
        adv = [r for r in rows if r[7] and r[8] >= 300]
        n_adv = len(adv)
        mins = sum(r[8] for r in adv) / 60
        best_dmg = max(adv, key=lambda r: (r[7][1], -r[0])) if adv else None
        most_deaths = max(rows, key=lambda r: (r[4], -r[0]))
        most_kills = max(rows, key=lambda r: (r[3], -r[0]))
        out_players[by_id[pid]["riot"]] = {
            "name": by_id[pid]["name"], "games": n, "wins": wins, "losses": n - wins,
            "winrate": round(100 * wins / n), "kda": round((k + a) / max(1, d), 2),
            "avg_kills": round(k / n, 1), "avg_deaths": round(d / n, 1), "avg_assists": round(a / n, 1),
            "deaths": d, "best_win_streak": best_w, "best_loss_streak": best_l, "streak": cur,
            "champs": [{"champ": c, "games": v[0], "wins": v[1]} for c, v in top],
            "max_deaths": {"v": most_deaths[4], "champ": most_deaths[2], "t": most_deaths[0]},
            "max_kills": {"v": most_kills[3], "champ": most_kills[2], "t": most_kills[0]},
            "n_adv": n_adv,
            "cs_min": round(sum(r[7][0] for r in adv) / mins, 1) if mins else None,
            "vis_min": round(sum(r[7][2] for r in adv) / mins, 2) if mins else None,
            "vis_avg": round(sum(r[7][2] for r in adv) / n_adv) if n_adv else None,
            "fb": sum(r[7][3] for r in adv),
            "pentas": sum(r[7][4] for r in adv),
            "penta_champ": next((r[2] for r in reversed(adv) if r[7][4]), None),
            "max_dmg": {"v": best_dmg[7][1], "champ": best_dmg[2], "min": round(best_dmg[8] / 60)} if best_dmg else None,
        }

    # ---- records ----
    def rec(key, items, value, label, detail=None, reverse=True, adv=False):
        items = [(riot, s) for riot, s in items if value(s) is not None]
        if not items:
            return None
        riot, s = (max if reverse else min)(items, key=lambda it: (value(it[1]), -ord(it[0][0])))
        return {"key": key, "label": label, "riot": riot, "name": s["name"],
                "value": value(s), "detail": detail(s) if detail else "", "adv": adv}

    allp = list(out_players.items())
    enough = [it for it in allp if it[1]["games"] >= MIN_GAMES] or allp
    records = [r for r in (
        rec("win_streak", allp, lambda s: s["best_win_streak"], "Plus longue série de victoires",
            lambda s: f'{s["games"]} parties jouées'),
        rec("loss_streak", allp, lambda s: s["best_loss_streak"], "Plus longue série de défaites",
            lambda s: f'{s["games"]} parties jouées'),
        rec("most_games", allp, lambda s: s["games"], "Le plus de parties jouées",
            lambda s: f'{s["wins"]} V · {s["losses"]} D'),
        rec("troll", enough, lambda s: s["avg_deaths"], "Troll du mois : le plus de morts par partie",
            lambda s: f'{s["deaths"]} morts en {s["games"]} parties'),
        rec("death_record", allp, lambda s: s["max_deaths"]["v"], "Record de morts en une partie",
            lambda s: f'sur {s["max_deaths"]["champ"]}'),
        rec("kills_record", allp, lambda s: s["max_kills"]["v"], "Record de kills en une partie",
            lambda s: f'sur {s["max_kills"]["champ"]}'),
        rec("best_kda", enough, lambda s: s["kda"], "Meilleur KDA",
            lambda s: f'{s["avg_kills"]} / {s["avg_deaths"]} / {s["avg_assists"]} en moyenne'),
    ) if r and not (r["key"] in ("loss_streak", "death_record") and r["value"] == 0)]

    # ---- records avancés (il faut au moins MIN_GAMES parties avec ces données pour les moyennes) ----
    enough_adv = [it for it in allp if it[1]["n_adv"] >= MIN_GAMES]
    records += [r for r in (
        rec("pentas", allp, lambda s: s["pentas"] or None, "Pentakills",
            lambda s: f'sur {s["penta_champ"]}', adv=True),
        rec("first_blood", allp, lambda s: s["fb"] or None, "Le plus de premiers sangs",
            lambda s: f'dans {round(100 * s["fb"] / s["n_adv"])} % de ses parties', adv=True),
        rec("farm", enough_adv, lambda s: s["cs_min"], "Meilleur farm (sbires par minute)",
            lambda s: f'en moyenne sur {s["n_adv"]} parties', adv=True),
        rec("damage", allp, lambda s: s["max_dmg"]["v"] if s["max_dmg"] else None,
            "Plus gros dégâts en une partie",
            lambda s: f'sur {s["max_dmg"]["champ"]} en {s["max_dmg"]["min"]} min', adv=True),
        rec("vision", enough_adv, lambda s: s["vis_min"], "Pire vision (score de vision par minute)",
            lambda s: f'{s["vis_avg"]} de score en moyenne par partie', reverse=False, adv=True),
    ) if r]

    # ---- vis-à-vis ----
    pairs = {}
    for g, friends in team_games:
        for x, y in combinations(sorted(friends, key=lambda f: f[0]), 2):
            key = (x[0], y[0])
            p = pairs.setdefault(key, {"tg": 0, "tw": 0, "ag": 0, "aw": 0, "bw": 0})
            if x[1] == y[1]:
                p["tg"] += 1; p["tw"] += x[2]
            else:
                p["ag"] += 1; p["aw"] += x[2]; p["bw"] += y[2]
    out_pairs = []
    for (a, b), p in pairs.items():
        out_pairs.append({
            "a": by_id[a]["riot"], "b": by_id[b]["riot"],
            "a_name": by_id[a]["name"], "b_name": by_id[b]["name"],
            "together": {"games": p["tg"], "wins": p["tw"]},
            "against": {"games": p["ag"], "a_wins": p["aw"], "b_wins": p["bw"]},
        })
    out_pairs.sort(key=lambda p: -(p["together"]["games"] + p["against"]["games"]))

    return {"updated": int(now), "since": int(start_ts), "games": len(team_games),
            "records": records, "players": out_players, "pairs": out_pairs}
