#!/usr/bin/env python3
"""job-board-radar: a daily feed of new job postings from your target companies.

Reads a CSV of companies, finds each company's public job board on Greenhouse, Lever,
or Ashby, keeps the roles that match your config (titles, levels, locations, pay floor),
and reports only postings you haven't seen before. Standard library only.

    python job_board_radar.py                    # uses config.json (or config.example.json)
    python job_board_radar.py --config my.json
    python job_board_radar.py --rediscover       # re-detect every company's job board
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
USER_AGENT = "job-board-radar (+https://github.com/ABALTIMORE/job-board-radar)"

# Used when config sets "location": "US".
US_PLACES = re.compile(
    r"\b(united states|usa|u\.s\.|remote[ ,-]*(us|usa|united states|north america|americas)|"
    r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|"
    r"idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
    r"minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|"
    r"new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|"
    r"south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|"
    r"wisconsin|wyoming|san francisco|bay area|nyc|seattle|chicago|boston|austin|denver|"
    r"los angeles|atlanta|miami|dallas|portland|salt lake|raleigh|pittsburgh|philadelphia|"
    r"mountain view|palo alto|menlo park|sunnyvale|san jose|santa clara|san mateo|bellevue|redwood city)\b", re.I)
US_STATE_CODES = re.compile(
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|"
    r"NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC|US|USA)\b")
NON_US_PLACES = re.compile(
    r"\b(canada|toronto|vancouver|montr[eé]al|ontario|british columbia|mexico|brazil|argentina|uk|"
    r"united kingdom|london|ireland|dublin|germany|berlin|munich|france|paris|spain|madrid|barcelona|"
    r"portugal|lisbon|netherlands|amsterdam|poland|warsaw|india|bangalore|bengaluru|hyderabad|"
    r"singapore|japan|tokyo|korea|seoul|china|shanghai|beijing|australia|sydney|israel|tel aviv|"
    r"emea|apac|latam|europe)\b", re.I)
MONEY = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])")


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg["_title_include"] = re.compile("|".join(cfg["title_include"]), re.I)
    cfg["_title_level"] = re.compile("|".join(cfg["title_level"]), re.I) if cfg.get("title_level") else None
    cfg["_title_exclude"] = re.compile("|".join(cfg["title_exclude"]), re.I) if cfg.get("title_exclude") else None
    cfg["_exclude"] = {c.lower() for c in cfg.get("exclude_companies", [])}
    cfg["_skip"] = set(cfg.get("skip_boards", []))
    return cfg


def http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_companies(csv_path, cfg):
    out = []
    with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            if name and name.lower() not in cfg["_exclude"]:
                out.append({"name": name, "website": (row.get("website") or "").strip(),
                            "priority": (row.get("priority") or "").strip()})
    return out


def slug_candidates(co):
    out = []
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9-]+)\.", co["website"].lower())
    if m:
        out.append(m.group(1))
    out += [norm(co["name"]), re.sub(r"[^a-z0-9]+", "-", co["name"].lower()).strip("-")]
    return list(dict.fromkeys(s for s in out if s))


def discover(co):
    """Find the company's public board. Greenhouse boards are checked by name to avoid namesakes."""
    for slug in slug_candidates(co):
        for ats, url in [("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
                         ("lever", f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1"),
                         ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}")]:
            try:
                data = http_json(url, timeout=8)
            except Exception:
                continue
            if ats == "greenhouse" and "jobs" in data:
                try:
                    a = norm(http_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}", timeout=8).get("name"))
                    b = norm(co["name"])
                    if a[:5] not in b and b[:5] not in a:
                        continue
                except Exception:
                    pass
                return {"ats": ats, "slug": slug}
            if (ats == "lever" and isinstance(data, list)) or (ats == "ashby" and "jobs" in data):
                return {"ats": ats, "slug": slug}
    return {"ats": None, "slug": None}


def fetch(co, board):
    jobs = []
    try:
        if board["ats"] == "greenhouse":
            for j in http_json(f"https://boards-api.greenhouse.io/v1/boards/{board['slug']}/jobs?content=true").get("jobs", []):
                jobs.append({"id": f"gh-{j['id']}", "title": j.get("title", ""),
                             "location": (j.get("location") or {}).get("name", ""),
                             "url": j.get("absolute_url", ""), "updated": (j.get("updated_at") or "")[:10],
                             "_pay": j.get("content", "")})
        elif board["ats"] == "lever":
            for j in http_json(f"https://api.lever.co/v0/postings/{board['slug']}?mode=json"):
                sr = j.get("salaryRange") or {}
                jobs.append({"id": f"lv-{j['id']}", "title": j.get("text", ""),
                             "location": (j.get("categories") or {}).get("location", ""),
                             "url": j.get("hostedUrl", ""), "updated": "",
                             "_pay": f"${sr.get('min', '')} ${sr.get('max', '')}" if sr else j.get("descriptionPlain", "")})
        elif board["ats"] == "ashby":
            data = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{board['slug']}?includeCompensation=true")
            for j in data.get("jobs", []):
                jobs.append({"id": f"ab-{j['id']}", "title": j.get("title", ""), "location": j.get("location", ""),
                             "url": j.get("jobUrl", ""), "updated": (j.get("publishedAt") or "")[:10],
                             "_pay": (j.get("compensation") or {}).get("compensationTierSummary", "") or ""})
    except Exception as e:
        return co, [], str(e)
    return co, jobs, None


def pay_ceiling(text):
    vals = []
    for raw in MONEY.findall(text or ""):
        s = raw.replace(",", "").replace(" ", "")
        try:
            v = float(s[:-1]) * 1000 if s[-1] in "kK" else float(s)
        except ValueError:
            continue
        if 30_000 <= v <= 2_000_000:
            vals.append(int(v))
    return max(vals) if vals else None


def title_ok(title, cfg):
    if not cfg["_title_include"].search(title):
        return False
    if cfg["_title_level"] and not cfg["_title_level"].search(title):
        return False
    return not (cfg["_title_exclude"] and cfg["_title_exclude"].search(title))


def location_ok(loc, cfg):
    mode = (cfg.get("location") or "any").upper()
    if mode == "ANY":
        return True
    if mode == "US":
        if US_PLACES.search(loc or ""):
            return True
        if NON_US_PLACES.search(loc or ""):
            return False
        return bool(US_STATE_CODES.search(loc or "")) or "remote" in (loc or "").lower() or not (loc or "").strip()
    return bool(re.search(cfg["location"], loc or "", re.I))  # any other value is a regex


def write_markdown(path, jobs, today):
    lines = [f"# New roles ({today})", "", f"{len(jobs)} new matching postings.", "",
             "| Company | Title | Location | Pay ceiling | Link |", "|---|---|---|---|---|"]
    for j in jobs:
        pay = f"${j['pay_ceiling']:,}" if j["pay_ceiling"] else "not posted"
        lines.append(f"| {j['company']} | {j['title'].strip()} | {j['location']} | {pay} | [apply]({j['url']}) |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--rediscover", action="store_true")
    args = ap.parse_args()
    cfg_path = Path(args.config) if args.config else (HERE / "config.json" if (HERE / "config.json").exists()
                                                       else HERE / "config.example.json")
    cfg = load_config(cfg_path)
    data_dir = (HERE / cfg.get("data_dir", "data")).resolve()
    data_dir.mkdir(exist_ok=True)
    boards_f, seen_f, backlog_f = data_dir / "boards.json", data_dir / "seen.json", data_dir / "backlog.json"

    companies = load_companies(HERE / cfg["companies_csv"], cfg)
    boards = json.loads(boards_f.read_text(encoding="utf-8")) if boards_f.exists() else {}
    todo = [c for c in companies if args.rediscover or c["name"] not in boards]
    if todo:
        print(f"Looking up job boards for {len(todo)} companies...", file=sys.stderr)
        with ThreadPoolExecutor(16) as ex:
            for c, b in zip(todo, ex.map(discover, todo)):
                boards[c["name"]] = b
    for name in cfg["_skip"]:
        boards[name] = {"ats": None, "slug": None}
    boards_f.write_text(json.dumps(boards, indent=1, sort_keys=True), encoding="utf-8")

    seen = set(json.loads(seen_f.read_text(encoding="utf-8"))) if seen_f.exists() else set()
    on_board = [(c, boards[c["name"]]) for c in companies if boards.get(c["name"], {}).get("ats")]
    floor = cfg.get("pay_floor") or 0
    new, keys, errors, matched = [], set(), [], 0
    with ThreadPoolExecutor(16) as ex:
        for co, jobs, err in ex.map(lambda cb: fetch(*cb), on_board):
            if err:
                errors.append(co["name"])
            for j in jobs:
                if not title_ok(j["title"], cfg) or not location_ok(j["location"], cfg):
                    continue
                ceiling = pay_ceiling(j.pop("_pay"))
                if floor and ceiling is not None and ceiling < floor:
                    continue
                matched += 1
                key = (co["name"], j["title"].strip().lower())
                if j["id"] in seen or key in keys:
                    seen.add(j["id"])
                    continue
                seen.add(j["id"])
                keys.add(key)
                new.append({**j, "company": co["name"], "priority": co["priority"], "pay_ceiling": ceiling})

    today = date.today().isoformat()
    new.sort(key=lambda j: (j["priority"] or "~", j["company"]))
    seen_f.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    (data_dir / "new_jobs.json").write_text(json.dumps({"date": today, "jobs": new}, indent=1), encoding="utf-8")
    write_markdown(data_dir / "new_jobs.md", new, today)
    backlog = json.loads(backlog_f.read_text(encoding="utf-8")) if backlog_f.exists() else []
    have = {j["id"] for j in backlog}
    backlog += [{**j, "found": today} for j in new if j["id"] not in have]
    backlog_f.write_text(json.dumps(backlog, indent=1), encoding="utf-8")

    print(json.dumps({"companies": len(companies), "on_public_boards": len(on_board),
                      "matching_open_roles": matched, "new_today": len(new),
                      "fetch_errors": errors[:10], "report": str(data_dir / "new_jobs.md")}, indent=1))


if __name__ == "__main__":
    main()
