# Gameday planner (static)

Compare college football schedules, mark which games you're going to, and see what's worth traveling for.

**Everything runs in the browser.** There is no backend, no accounts, no analytics. Crew names and "going" marks live in the visitor's own browser (localStorage) and are never sent anywhere.

External calls made by the page: ESPN's CDN (team logos), api.weather.gov (kickoff weather, no key), seatgeek.com and calendar.google.com (links only, opened on tap).

## Deploy on GitHub Pages
1. Create a repo, push these files (keep `index.html` at the root and `data/games.json` next to it).
2. Settings → Pages → Deploy from branch → `main` / root.
3. To keep scores current, move `ci/refresh-data.yml` to `.github/workflows/refresh-data.yml` (do it in the GitHub web editor: Add file → paste). Then Settings → Actions → General → allow "Read and write permissions". It rebuilds `data/games.json` a few times a day.

## Rebuild the data by hand
```
GD_OUT=data/games.json GD_GEO=geocode_cache.json python3 build_gameday_data.py
```
Needs `curl` and Python 3. Uses ESPN's public site API (unofficial) and Nominatim for city coordinates (cached in `geocode_cache.json`).
