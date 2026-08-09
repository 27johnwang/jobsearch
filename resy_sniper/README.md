# resy_sniper

Book **your own** Resy reservation the instant it drops (e.g. tables that open
at 9:00 AM a month out). It syncs its clock, waits for the exact drop time,
then burst-polls Resy's find endpoint and books the best-matching slot in the
same breath.

## ⚠️ Read this first — personal use only

This tool is for grabbing **one table, for yourself**, faster than you could
click. It is **not** a scalping tool, and it shouldn't be used as one:

- **Automating Resy is against Resy's Terms of Service.** They can rate-limit,
  CAPTCHA, or ban accounts that hammer their API. Use gentle burst settings and
  your own account, at your own risk.
- **Reselling reservations is illegal in some places.** New York's 2024
  Restaurant Reservation Anti-Piracy Act bans selling reservations through
  unauthorized services, and other cities are following. Don't hoard slots you
  won't use, and don't resell them.
- Booking a table you intend to actually show up for = fine. Grabbing tables to
  flip = not something this tool is for, and not something I'll help extend it
  to do.

Be a good citizen: cancel reservations you can't make so someone else can have
the table.

## How it works

1. **Clock sync** — optionally queries NTP once so we fire on Resy's clock, not
   your laptop's drifting one.
2. **Wait** — sleeps until ~1s before the drop, then spin-waits for
   millisecond precision.
3. **Burst find** — repeatedly calls `GET /4/find` until matching slots appear
   (they often show up a few hundred ms after the nominal drop).
4. **Rank** — filters by your allowed table types and preferred-time window,
   orders best-first.
5. **Book** — exchanges the slot for a book token (`POST /3/details`) and
   commits (`POST /3/book`), falling through to the next-best slot if one gets
   sniped out from under you.

## Install

```bash
pip install requests ntplib   # ntplib is optional but recommended
```

(`requests` is already in the repo's `requirements.txt`; `ntplib` is added
there too.)

## Setup: get your three inputs

You need your **auth token**, the **venue id**, and the reservation **day**.

### 1. Auth token (identifies your account)

1. Log in at [resy.com](https://resy.com) in Chrome/Firefox.
2. Open DevTools → **Network** tab.
3. Click around (e.g. search a restaurant). Find any request to
   `api.resy.com`.
4. In its request headers, copy the value of **`X-Resy-Auth-Token`**
   (a long `eyJ...` JWT).
5. Export it — don't put it on the command line or commit it:

   ```bash
   export RESY_AUTH_TOKEN="eyJ..."
   ```

Tokens expire periodically; re-grab it if you start getting 401s.

### 2. Venue id

Open the restaurant's Resy page and check the `venue_id` in the same Network
requests (the `/4/find` call carries `venue_id=...`), or in the page's data.
It's a number like `12345`.

### 3. Day & party size

The reservation date you want (`YYYY-MM-DD`) and how many people.

## Usage

Dry run first — this finds and ranks slots but **never books**, so you can
confirm your venue id / times are right against a date that's already open:

```bash
python -m resy_sniper.cli \
  --venue-id 12345 --day 2026-09-01 --party-size 2 \
  --time 19:00 --time 19:30 --time 18:30 \
  --table-type "Dining Room" \
  --dry-run
```

Real snipe, waiting for a 9:00 AM US-Eastern drop (UTC-4 in summer):

```bash
python -m resy_sniper.cli \
  --venue-id 12345 --day 2026-09-01 --party-size 2 \
  --time 19:00 --time 19:30 --time 18:30 \
  --table-type "Dining Room" \
  --drop "2026-08-25 09:00:00" --tz-offset -4
```

Or drive it from a config file (copy `config.example.json` → `config.json`,
which is gitignored):

```bash
python -m resy_sniper.cli --config resy_sniper/config.json \
  --drop "2026-08-25 09:00:00" --tz-offset -4
```

### Key flags

| Flag | Meaning |
|------|---------|
| `--drop "YYYY-MM-DD HH:MM:SS"` | When slots open. Omit to book immediately. |
| `--tz-offset -4` | Hours from UTC for `--drop`. Default: your machine's tz. |
| `--time HH:MM` | Preferred time, repeatable, best first. |
| `--table-type "Dining Room"` | Acceptable seating, repeatable. Omit = any. |
| `--window 90` | Accept slots within N min of a preferred time. |
| `--burst-seconds 20` | How long to keep retrying after the drop. |
| `--burst-interval 0.25` | Gap between find attempts. Keep it polite. |
| `--lead-seconds 1` | Start bursting this early to beat the crowd. |
| `--no-ntp` | Trust the system clock (skip NTP sync). |
| `--dry-run` | Find + rank, never book. |

## Running it exactly at 9:00 unattended

The tool blocks internally until `--drop`, so you can just launch it a few
minutes early and leave it. If you want the OS to launch it, use `cron`
(Linux/macOS) or Task Scheduler (Windows) a couple minutes ahead and let the
internal timer handle the precise moment.

## Tests

```bash
python -m resy_sniper.test_sniper
```

All logic tests are offline (no network, no account needed).

## Limitations & honesty

- These are **unofficial** endpoints. If Resy changes them, `client.py` is the
  one file to update.
- High-demand drops have serious anti-bot defenses (Cloudflare, device
  fingerprinting, CAPTCHAs). This tool does **not** try to defeat those — if
  Resy challenges the request, it'll fail loudly rather than evade. That's on
  purpose.
- Nothing here guarantees a table. It just makes your honest attempt fast.
