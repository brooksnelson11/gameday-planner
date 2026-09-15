#!/usr/bin/env python3
"""Bake the 2026 FBS season into one small JSON for the Gameday planner.
Sources: ESPN public site API (teams list + full-season scoreboard). No key. Runs from cron."""
import json, urllib.request, datetime, sys
SEASON = 2026
import os
OUT = os.environ.get("GD_OUT", "/var/www/html/gameday/data/games.json")
GEO = os.environ.get("GD_GEO", os.path.join(os.path.dirname(os.path.abspath(__file__)), "geocode_cache.json"))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36", "Accept": "application/json"}
import subprocess
def get(url):
    # curl is what this endpoint accepts reliably from this box (urllib got 403s regardless of headers)
    r = subprocess.run(["curl", "-s", "-m", "90", "--compressed", url], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)
CONF = {"8":"SEC","1":"ACC","4":"Big 12","5":"Big Ten","151":"American","12":"C-USA","15":"MAC","17":"Mountain West","9":"Pac-12","37":"Sun Belt","18":"Independent"}
teams = {}
tl = get("https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams?limit=400&groups=80")
for t in tl["sports"][0]["leagues"][0]["teams"]:
    t = t["team"]
    logo = (t.get("logos") or [{}])[0].get("href", "")
    teams[t["id"]] = {"ab": t.get("abbreviation", ""), "name": t.get("displayName", ""), "short": t.get("shortDisplayName", ""),
                      "loc": t.get("location", ""), "mascot": t.get("name", ""), "color": t.get("color", "333333"),
                      "alt": t.get("alternateColor", "ffffff"), "logo": logo, "conf": None}
games = []
events, seen = [], set()
for wk in range(1, 17):   # regular season weeks; the whole-season query is unreliable, per-week is not
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=400&dates={SEASON}&seasontype=2&week={wk}")
    for e in sb.get("events", []):
        if e["id"] not in seen: seen.add(e["id"]); events.append(e)
for e in events:
    c = e["competitions"][0]
    comps = {x["homeAway"]: x for x in c["competitors"]}
    if "home" not in comps or "away" not in comps: continue
    def side(x):
        tm = x["team"]; tid = tm["id"]
        if tid not in teams:
            teams[tid] = {"ab": tm.get("abbreviation",""), "name": tm.get("displayName",""), "short": tm.get("shortDisplayName",""), "loc": tm.get("location",""), "mascot": tm.get("name",""), "color": tm.get("color","333333"), "alt": tm.get("alternateColor","ffffff"), "logo": tm.get("logo",""), "conf": None}
        cid = str(tm.get("conferenceId") or "")
        if cid and teams[tid]["conf"] is None: teams[tid]["conf"] = CONF.get(cid, "FCS")
        rk = (x.get("curatedRank") or {}).get("current", 99)
        sc = x.get("score"); sc = sc.get("displayValue") if isinstance(sc, dict) else sc
        try: sc = int(sc) if sc not in (None, "") else None
        except ValueError: sc = None
        return {"id": tid, "score": (sc if c["status"]["type"].get("state") != "pre" else None), "rank": rk if rk and rk < 99 else None, "rec": next((r.get("summary") for r in x.get("records", []) if r.get("type") == "total"), None)}
    st = c["status"]["type"]
    status = "final" if st.get("completed") else ("live" if st.get("state") == "in" else "sched")
    bc = ""
    if c.get("broadcasts"): bc = (c["broadcasts"][0].get("names") or [""])[0]
    elif c.get("geoBroadcasts"): bc = ((c["geoBroadcasts"][0].get("media") or {}).get("shortName") or "")
    v = c.get("venue") or {}
    note = next((x.get("headline") for x in (c.get("notes") or []) if x.get("headline")), None)
    tk = (c.get("tickets") or [{}])[0]; tix = ((tk.get("links") or [{}])[0].get("href") or "").split("?")[0]
    games.append({"id": e["id"], "wk": (e.get("week") or {}).get("number"), "date": e["date"], "tba": not c.get("timeValid", True), "dtba": not c.get("dateValid", True),
                  "tix": tix or None, "tixFrom": tk.get("summary") or None, "note": note,
                  "neutral": bool(c.get("neutralSite")), "conf": bool(c.get("conferenceCompetition")), "venue": v.get("fullName", ""),
                  "city": (v.get("address") or {}).get("city", ""), "state": (v.get("address") or {}).get("state", ""), "tv": bc,
                  "status": status, "clock": st.get("shortDetail", ""), "h": side(comps["home"]), "a": side(comps["away"]), "name": e.get("shortName", "")})
# venue coordinates (city-level) for kickoff weather: Nominatim, cached, 1 req/s, only for cities not yet cached
import time, urllib.parse
try: geo = json.load(open(GEO))
except Exception: geo = {}
need = sorted({(g["city"], g["state"]) for g in games if g["city"] and (g["city"] + ", " + g["state"]) not in geo})
for city, st in need[:400]:
    key = city + ", " + st
    try:
        q = urllib.parse.quote(city + ", " + st + ", USA")
        r = subprocess.run(["curl", "-s", "-m", "20", "-A", "gameday-planner/1.0 (schedule page; contact via repo)", f"https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1"], capture_output=True, text=True)
        j = json.loads(r.stdout or "[]")
        geo[key] = [round(float(j[0]["lat"]), 3), round(float(j[0]["lon"]), 3)] if j else None
    except Exception as e:
        geo[key] = None
    time.sleep(1.1)
json.dump(geo, open(GEO, "w"))
for g in games:
    ll = geo.get(g["city"] + ", " + g["state"]) if g["city"] else None
    if ll: g["lat"], g["lon"] = ll
games.sort(key=lambda g: (g["wk"] or 99, g["date"]))
out = {"season": SEASON, "built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "teams": teams, "games": games}
json.dump(out, open(OUT, "w"), separators=(",", ":"))
wks = sorted({g["wk"] for g in games if g["wk"]})
print("teams", len(teams), "games", len(games), "weeks", wks[0], "to", wks[-1], "bytes", len(json.dumps(out)))
