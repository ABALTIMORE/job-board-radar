# job-board-radar

**A daily feed of new job postings from the companies you actually want to work for.**

🌐 **Website:** https://abaltimore.github.io/job-board-radar/ &nbsp;·&nbsp; MIT licensed &nbsp;·&nbsp; Python 3.9+, no dependencies

Give it a list of target companies. Every day it checks their public job boards, keeps the roles that match your titles, level, location, and pay floor, and shows you **only the postings you haven't seen before**.

- **Early:** companies post on their own boards before the job aggregators pick them up.
- **Free:** Python standard library only. No accounts, API keys, or AI costs.
- **Within the rules:** it reads the public job-board endpoints companies publish through Greenhouse, Lever, and Ashby so their jobs can be shown. No LinkedIn or Indeed scraping.

```
$ python job_board_radar.py
{
 "companies": 15,
 "on_public_boards": 15,
 "matching_open_roles": 96,
 "new_today": 75,
 "report": "data/new_jobs.md"
}
```

Each run writes a clickable table to `data/new_jobs.md`, for example:

| Company | Title | Location | Pay ceiling | Link |
|---|---|---|---|---|
| Brex | Senior Product Manager, AI | Seattle, WA | $400,000 | apply |
| Coinbase | Group Product Manager, Compliance Automation | Remote, USA | $286,900 | apply |
| Airbnb | Senior Product Manager, Community Support | Remote, USA | $207,000 | apply |

_Sample rows from a real run against the 15 example companies; roles and pay change daily._

## Quick start

1. **Get the code** (Python 3.9+):
   ```bash
   git clone https://github.com/ABALTIMORE/job-board-radar.git
   cd job-board-radar
   ```
2. **Add your companies.** Copy `companies.example.csv` to `companies.csv` and list your targets:
   ```csv
   name,website,priority
   Stripe,https://stripe.com,1
   Figma,https://www.figma.com,2
   ```
   `priority` is optional and sorts the report (1 first).
3. **Set your filters.** Copy `config.example.json` to `config.json` and edit it (see below). Point `companies_csv` at your file.
4. **Run it:**
   ```bash
   python job_board_radar.py
   ```
   Open `data/new_jobs.md` for a clickable table of today's new roles.

Run it again tomorrow and you'll only see what's new.

## Configuration

| Key | What it does | Example |
|---|---|---|
| `companies_csv` | Your company list (`name`, `website`, optional `priority`) | `"companies.csv"` |
| `title_include` | Regexes; a title must match one | `["\\bproduct manager\\b"]` |
| `title_level` | Regexes; a title must also match one (leave empty to skip) | `["\\bsenior\\b", "\\bstaff\\b"]` |
| `title_exclude` | Regexes; drop titles matching any | `["\\bintern\\b"]` |
| `location` | `"any"`, `"US"` (US plus US-remote, using built-in place matching), or your own regex | `"(new york\|remote)"` |
| `pay_floor` | Drop roles whose **posted** pay ceiling is below this. Roles with no posted pay are kept | `150000` |
| `exclude_companies` | Names to always skip (e.g. your current employer) | `["Acme"]` |
| `skip_boards` | Companies whose auto-detected board turned out to be wrong | `["Acme"]` |
| `data_dir` | Where results and state are written | `"data"` |

It works for any role, not just PMs: change the title patterns to fit engineering, design, data, and so on.

## Output

Everything goes in `data/` (git-ignored):

| File | What |
|---|---|
| `new_jobs.md` | Today's new roles as a table with apply links |
| `new_jobs.json` | The same, as JSON, for other tools |
| `backlog.json` | Every role ever found (only added to, never overwritten) |
| `seen.json` | Posting IDs already reported |
| `boards.json` | Each company's detected job board (cached; refresh with `--rediscover`) |

## How it works

1. **Find each company's board.** It tries likely names (from the website and company name) on Greenhouse, Lever, and Ashby. Greenhouse matches are checked against the board's company name, to avoid a namesake's board.
2. **Fetch open roles** from each board's public endpoint.
3. **Filter** by title, level, location, and posted pay.
4. **Report only what's new.** It de-duplicates across runs and within a run (the same title posted in several cities appears once).

Companies that use other systems (Workday, custom career sites) won't be found automatically. Check those by hand, or add support in a pull request.

## Run it daily for free (optional)

`.github/workflows/daily.yml` runs the radar every morning on GitHub Actions, which is free for public repos, and attaches `new_jobs.md` to each run. To use it:
1. Fork this repo.
2. Commit your own `config.json` and company CSV. Note: on a public fork these are visible to anyone.
3. Turn on Actions in your fork.

## Be a good citizen

It makes one request per company per run, with a small thread pool. Please don't run it more than a few times a day. These endpoints are public courtesies from the job-board providers.

## License

MIT. See [LICENSE](LICENSE).
