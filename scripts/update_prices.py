"""Append new daily closes to data/perf.json for every ticker already in it.

Primary source: Yahoo Finance chart data. Fallback: Stooq daily CSV.
Only completed sessions are added (today's bar only after 16:30 New York time).
A ticker is skipped (and reported) if no source answers or a close looks wrong;
existing rows are never changed.
"""
import csv
import datetime as dt
import io
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
PERF = ROOT / 'data' / 'perf.json'
META = ROOT / 'data' / 'meta.json'
NY = ZoneInfo('America/New_York')
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
DRY = '--dry-run' in sys.argv


def fetch(url):
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
                return r.read()
        except Exception as e:  # network errors, 429s
            last = e
            time.sleep(3 * (attempt + 1))
    raise last


def from_yahoo(ticker):
    out = {}
    for host in ('query1', 'query2'):
        try:
            raw = fetch(f'https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?range=1mo&interval=1d&includePrePost=false')
            res = json.loads(raw)['chart']['result'][0]
            tz = ZoneInfo(res['meta'].get('exchangeTimezoneName') or 'America/New_York')
            closes = res['indicators']['quote'][0]['close']
            for ts, c in zip(res.get('timestamp') or [], closes):
                if c is not None:
                    out[dt.datetime.fromtimestamp(ts, tz).date().isoformat()] = float(c)
            if out:
                return out
        except Exception as e:
            print(f'  yahoo {host} {ticker}: {e}')
    return out


def from_stooq(ticker):
    sym = '^spx' if ticker == '^GSPC' else ticker.lower() + '.us'
    out = {}
    try:
        text = fetch(f'https://stooq.com/q/d/l/?s={urllib.parse.quote(sym)}&i=d').decode()
        for r in csv.DictReader(io.StringIO(text)):
            c = r.get('Close')
            if c and c not in ('N/D', '0'):
                out[r['Date']] = float(c)
    except Exception as e:
        print(f'  stooq {ticker}: {e}')
    return out


def rnd(v):
    return round(v, 2) if abs(v) >= 1 else round(v, 4)


def main():
    rows = json.loads(PERF.read_text())
    now = dt.datetime.now(NY)
    cutoff = now.date() if now.time() >= dt.time(16, 30) else now.date() - dt.timedelta(days=1)
    tickers = []
    for r in rows:
        if r['ticker'] not in tickers:
            tickers.append(r['ticker'])
    added, failed = 0, []
    for t in tickers:
        mine = sorted((r for r in rows if r['ticker'] == t), key=lambda r: r['date'])
        last = mine[-1]
        data = from_yahoo(t)
        source = 'yahoo'
        if not data:
            data, source = from_stooq(t), 'stooq'
        if not data:
            failed.append(t)
            print(f'{t}: no source answered')
            continue
        new = sorted(d for d in data if last['date'] < d <= cutoff.isoformat())
        prev = last['close']
        accepted = []
        for d in new:
            c = rnd(data[d])
            if prev and abs(c / prev - 1) > 0.5:
                print(f'{t}: {d} close {c} vs previous {prev} looks wrong; stopping this ticker')
                failed.append(t)
                break
            accepted.append({'date': d, 'ticker': t, 'name': last['name'], 'label': last['label'],
                             'kind': last['kind'], 'slot': last['slot'], 'close': c})
            prev = c
        latest = max(data) if data else None
        print(f'{t}: source {source}, latest bar {latest} {rnd(data[latest]) if latest else ""}, stored {last["date"]}, adding {len(accepted)}')
        rows.extend(accepted)
        added += len(accepted)
    if failed:
        print('WARNING tickers not updated:', ', '.join(failed))
    if len(failed) == len(tickers):
        sys.exit('No price source answered for any ticker')
    if added and not DRY:
        PERF.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
        meta = json.loads(META.read_text())
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        entry = meta['datasets'].setdefault('perf', {})
        entry.update(updated=stamp, rows=len(rows))
        meta['updated'] = stamp
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f'added {added} row(s){" (dry run, nothing written)" if DRY else ""}')


if __name__ == '__main__':
    main()
