# Job Board Radar

**Stop checking 20 careers pages every morning.**

Make a list of the companies you'd love to work for. Job Board Radar checks their careers pages every day and gives you a short list of **new jobs that fit you**, often before they show up on the big job sites. Free, and no coding needed.

🌐 **Website with the full walkthrough:** https://abaltimore.github.io/job-board-radar/

Each morning you get a short list like this, with a link to apply to each job:

| Company | Job title | Location | Pay up to |
|---|---|---|---|
| Brex | Senior Product Manager, AI | Seattle, WA | $400,000 |
| Coinbase | Group Product Manager, Compliance Automation | Remote, USA | $286,900 |
| Airbnb | Senior Product Manager, Community Support | Remote, USA | $207,000 |

_Example from a real run. Jobs and pay change daily. It works for any kind of job, not just product managers._

## Start here: set it up in your browser (about 10 minutes)

You need a free [GitHub account](https://github.com/signup). Nothing to install.

1. **Make your own copy.** Click **Fork** (top right of this page), then **Create fork**.
2. **Add your companies.** In your copy, open `companies.example.csv`, click the pencil icon, and replace the list with your companies, one per line: name, website, and an optional priority (1 = top choice). Keep the first line. Click **Commit changes**.
   ```csv
   name,website,priority
   Stripe,https://stripe.com,1
   Figma,https://www.figma.com,2
   ```
3. **Say what you're looking for.** Open `config.example.json` the same way and change:
   - **Job titles** in `"title_include"`, e.g. change `"\\bproduct manager\\b"` to `"designer"`. Plain words work.
   - **Where:** `"location"` is `"US"` (US plus US remote) or `"any"`.
   - **Lowest pay:** `"pay_floor"`, the lowest yearly salary you'd consider. Jobs that don't list pay are kept.

   Keep the quotes and commas, then click **Commit changes**.
4. **Turn on the daily check.** Open the **Actions** tab and click **I understand my workflows, go ahead and enable them**. To try it now: click **daily radar**, then **Run workflow**.
5. **Read your list.** In **Actions**, click the newest run. Your new jobs are right on that page. It runs again every morning, around 7 to 8am Eastern, and only shows jobs you haven't seen.

> **Good to know:** your copy is public, so anyone could see your company list and job titles. Don't put anything private in it, like your current employer's name.

## Common questions

- **Does it cost anything?** No. No subscriptions, no AI fees.
- **Does it apply for me?** No. It finds new jobs; you choose and apply yourself.
- **Will it work for my companies?** For any company whose careers page runs on Greenhouse, Lever, or Ashby (popular hiring systems used by most tech companies). Open a job on their careers page: if the link mentions greenhouse, lever, or ashby, it works. Companies on Workday or custom sites aren't covered yet.
- **Is this allowed?** Yes. It reads the same public listings each company shows on its own careers page. No logins, no LinkedIn or Indeed scraping. Please don't run it more than a few times a day.

---

## For developers

### Run it on your own computer

Python 3.9 or newer, standard library only.

```bash
git clone https://github.com/ABALTIMORE/job-board-radar.git
cd job-board-radar
python job_board_radar.py
```

It uses `config.json` if present, otherwise `config.example.json`. Open `data/new_jobs.md` for the results. Run it again tomorrow and you'll only see what's new.

### Settings in detail

| Key | What it does | Example |
|---|---|---|
| `companies_csv` | Your company list (`name`, `website`, optional `priority`) | `"companies.csv"` |
| `title_include` | Patterns (case-insensitive regex); a title must match one | `["\\bproduct manager\\b"]` |
| `title_level` | A title must also match one of these (leave empty to skip) | `["\\bsenior\\b", "\\bstaff\\b"]` |
| `title_exclude` | Drop titles matching any | `["\\bintern\\b"]` |
| `location` | `"any"`, `"US"` (US plus US-remote, using built-in place matching), or your own regex | `"(new york\|remote)"` |
| `pay_floor` | Drop roles whose **posted** pay ceiling is below this. Roles with no posted pay are kept | `150000` |
| `exclude_companies` | Names to always skip (e.g. your current employer) | `["Acme"]` |
| `skip_boards` | Companies whose auto-detected board turned out to be wrong | `["Acme"]` |
| `data_dir` | Where results and state are written | `"data"` |

### Output

Everything goes in `data/` (git-ignored):

| File | What |
|---|---|
| `new_jobs.md` | Today's new roles as a table with apply links |
| `new_jobs.json` | The same, as JSON, for other tools |
| `backlog.json` | Every role ever found (only added to, never overwritten) |
| `seen.json` | Posting IDs already reported |
| `boards.json` | Each company's detected job board (cached; refresh with `--rediscover`) |

### How it works

1. **Find each company's board.** It tries likely names (from the website and company name) on Greenhouse, Lever, and Ashby. Greenhouse matches are checked against the board's company name, to avoid a namesake's board.
2. **Fetch open roles** from each board's public endpoint.
3. **Filter** by title, level, location, and posted pay.
4. **Report only what's new.** It de-duplicates across runs and within a run (the same title posted in several cities appears once).

### The daily GitHub run

`.github/workflows/daily.yml` runs every day at 12:00 UTC (and on demand), shows `new_jobs.md` on the run's summary page, attaches it as an artifact, and caches `data/` so each run reports only new roles. GitHub Actions is free for public repos.

### Be a good citizen

It makes one request per company per run, with a small thread pool. Please don't run it more than a few times a day. These endpoints are public courtesies from the job-board providers.

## License

MIT. See [LICENSE](LICENSE).
