# US Cannabis IB Dashboard

A static dashboard of US cannabis M&A, financing, stock performance, state catalysts and news, for investment banking coverage.

- `index.html` — the page (tabs, tables, maps and charts; d3 in `assets/`)
- `data/*.json` — the data, one file per dataset: headlines refresh hourly (about 6am–10pm ET), everything else once a day by about 6am ET
- `data/meta.json` — last refresh time; open pages re-check it every five minutes

Counts and totals are computed from the trackers in `data/` (M&A, debt financings, other transactions and stock prices). Every row links to its public source: SEC filings, company releases, state regulators and trade press; stock prices are Yahoo Finance closes and fund data comes from AdvisorShares. Hemp is out of scope.

For information only; not investment advice.
