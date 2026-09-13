# Colombian Professional Football (FPC) — Matches, Standings, Players

The first open, standardized dataset of Colombian professional football
(Categoría Primera A — Liga BetPlay Dimayor), from the inaugural 1948
championship to the current season. Built for analysts, journalists and
developers — and as the database for a future FPC fantasy game.

> Independent project. Not affiliated with DIMAYOR or the Colombian Football Federation.
> Source: Spanish Wikipedia (CC BY-SA 4.0 — attribution required, see License).

## Coverage (as of September 2026)

| File | Rows | Content |
|---|---|---|
| `matches.csv` | ~20,900 | Every documented match: season, stage, round/leg, date, home/away, score, penalties, status |
| `standings.csv` | ~1,680 | League tables per season (position, P/W/D/L, GF/GA/GD, points, bonus) |
| `groups.csv` | ~870 | Semifinal-group and phase tables (cuadrangulares, liguilla, pentagonales…) |
| `teams.csv` | 60 | Clubs: city, stadium, capacity, founded, colors, active flag |
| `players.csv` | ~600 | Current squads: team, position (GK/DF/MF/FW), shirt number, age |
| `scorers.csv` | ~670 | Top scorers per season (player, team, goals, apps) |
| `assists.csv` | ~210 | Top assists per season (where documented, 2010s+) |
| `seasons.csv` | 103 | Season index with champion, dates and match counts |
| `champions.csv` | 101 | Every champion 1948–today (runner-up, final score, top scorer) |

103 seasons (1948–2026), 60 clubs, 101 championship editions.

## Key fields

- **Team ids** are stable ASCII slugs (`nacional`, `millonarios`, `santafe`…).
- **Season ids**: `{year}-i` (Apertura) / `{year}-ii` (Finalización) since 2002;
  plain `{year}` for single-championship years (pre-2002, 1995-96, 1996-97, 2020).
- **Match stages**: `regular`, `cuadrangulares`, `liguilla`, `octogonal`, `hexagonal`,
  `pentagonales`, `triangulares`, `octavos`, `cuartos`, `semifinales`, `final`, `playoffs`
  (formats changed over the decades — see `seasons.csv`).
- **Player ids** are name slugs, stable across transfers. Genuine homonyms playing
  for different clubs get a `-{club}` suffix.
- **Points**: 2 per win before 1995, 3 since; 1995–1998 include era bonus points
  (shootouts, phase bonuses) in the `bonus` column.

## Known limitations (documented, not hidden)

- **Match coverage before 2002 is partial**: `seasons.csv` (`n_matches`, `n_played`)
  documents exactly what each season contains. Five seasons (1987, 1991, 1992,
  1993, 1995) have standings but no documented matches on Wikipedia.
- **No match dates before ~2002** for most seasons (`date` is null) — dates were
  only systematically documented later.
- **Squads are current only** (`players.csv`); no historical rosters.
- **No minutes, cards or lineups** (Wikipedia doesn't have them).
- A handful of **verified source typos** are published as-is (e.g. Quindío's 22
  instead of 25 points in 2011-II, a phantom goal in Pasto's 2020 GA).
- Result-matrix orientation (home/away) is auto-verified against fixture lists
  where both exist; where only a matrix exists, row=home is assumed (es.wiki
  convention).
- The 1989 season was suspended (no champion, `status=cancelled`); 2020 had a
  single tournament (COVID).

## How it's built

Scraped daily from es.wikipedia.org by the open-source
[fpc-api](https://github.com/Norwyx/fpc-api) pipeline (Python, BeautifulSoup),
with blocking validators (W+D+L=PJ, points math, standings↔matches cross-checks).
Data never ships if it doesn't add up. `seasons.csv` is regenerated every day;
re-upload as a new dataset version whenever you want it fresh.

## License

Data: **CC BY-SA 4.0** (derived from Wikipedia — credit Wikipedia and link back).
Build code: MIT.
