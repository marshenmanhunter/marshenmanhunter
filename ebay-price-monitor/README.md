# pricewatch: eBay price monitor

Scans eBay on a schedule for items you pick. For each item it:

1. Tracks the market price over time: asking-price median, spread, daily trend, and a **likely-sold** price estimate.
2. Flags listings priced well below market and pushes an alert to your phone (ntfy) or Discord.

Uses the official eBay Browse API. No scraping. Runs on macOS, Windows and Linux with Python 3.9 or newer.

## Get started

Pick your system. Each guide takes you from nothing to scheduled scans.

- [macOS](#macos)
- [Windows](#windows)
- [Linux](#linux)

Every guide has the same five steps:

1. Install Python
2. Download the code
3. Run the demo (no eBay account needed)
4. Connect to eBay and run your first real scan
5. Schedule automatic scans

---

## macOS

All commands go in **Terminal** (press Cmd+Space, type Terminal, press Enter).

### 1. Install Python

```bash
python3 --version
```

If it prints `Python 3.9` or higher, go to step 2. If macOS offers to install the **Command Line Tools**, click Install, wait for it to finish, then run the command again. This also installs `git`.

### 2. Download the code

```bash
mkdir -p ~/code && cd ~/code
git clone https://github.com/marshenmanhunter/marshenmanhunter.git
cd marshenmanhunter/ebay-price-monitor
```

Keep the project out of Desktop, Documents and Downloads. macOS blocks scheduled jobs from those folders.

### 3. Run the demo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pricewatch demo
```

You see 30 days of simulated scans, a price trend and alerts. See [what the demo shows](#what-the-demo-shows).

Each time you open a new Terminal window, get back in with:

```bash
cd ~/code/marshenmanhunter/ebay-price-monitor && source .venv/bin/activate
```

### 4. Connect to eBay

Get your keys first: [Get your eBay API keys](#get-your-ebay-api-keys). Then:

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Fill in your keys and items ([how to edit the config](#edit-your-config)). In nano, save with Ctrl+O then Enter, quit with Ctrl+X. Avoid TextEdit: it swaps in curly quotes, which break the file.

```bash
python -m pricewatch check
python -m pricewatch run --no-notify --show-excluded
```

`check` confirms your keys work. `run` does a real scan and lists every listing it threw out, so you can tune your filters.

### 5. Schedule automatic scans

```bash
./scheduling/install-mac.sh            # every 60 minutes
./scheduling/install-mac.sh 15         # or every 15 minutes (5, 10, 15, 20, 30, 60)
tail -f pricewatch.log                 # watch results, Ctrl+C to stop watching
```

To stop: `./scheduling/install-mac.sh --uninstall`

A sleeping Mac does not scan. It runs one catch-up scan when it wakes. For round-the-clock scans on a MacBook, keep it plugged in and turn on the option to prevent automatic sleep on power adapter in **System Settings > Battery > Options**.

### Common problems on macOS

| You see | Fix |
|---|---|
| `command not found: python` or `pip` | You are outside the virtualenv. Run `source .venv/bin/activate`. |
| `externally-managed-environment` | Same cause, same fix. |
| `Operation not permitted` in pricewatch.log | The project sits in Desktop, Documents or Downloads. Move it to `~/code` and rerun the install script. |
| `missing eBay credentials` in pricewatch.log | Scheduled jobs ignore `export` lines. Put your keys in config.yaml. |

---

## Windows

All commands go in **PowerShell** (press Start, type PowerShell, press Enter).

### 1. Install Python

Download Python from [python.org/downloads](https://www.python.org/downloads/) and run the installer. On the first screen, tick **Add python.exe to PATH**, then click Install Now.

Close and reopen PowerShell, then check:

```powershell
py --version
```

It should print `Python 3.9` or higher.

### 2. Download the code

**Option A, no git:** on the [GitHub page](https://github.com/marshenmanhunter/marshenmanhunter), click **Code > Download ZIP**. Right-click the ZIP, choose **Extract All**, and extract to `C:\Users\<you>\code`. Then:

```powershell
cd $HOME\code\marshenmanhunter-main\ebay-price-monitor
```

**Option B, with git** (install it with `winget install Git.Git`):

```powershell
mkdir $HOME\code -Force; cd $HOME\code
git clone https://github.com/marshenmanhunter/marshenmanhunter.git
cd marshenmanhunter\ebay-price-monitor
```

### 3. Run the demo

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pricewatch demo
```

The `Set-ExecutionPolicy` line is a one-time setting so PowerShell runs the activation script. Answer `Y` if asked.

You see 30 days of simulated scans, a price trend and alerts. See [what the demo shows](#what-the-demo-shows).

Each time you open a new PowerShell window, get back in with (use your folder from step 2):

```powershell
cd $HOME\code\marshenmanhunter\ebay-price-monitor; .venv\Scripts\Activate.ps1
```

### 4. Connect to eBay

Get your keys first: [Get your eBay API keys](#get-your-ebay-api-keys). Then:

```powershell
copy config.example.yaml config.yaml
notepad config.yaml
```

Fill in your keys and items ([how to edit the config](#edit-your-config)), save, close Notepad.

```powershell
python -m pricewatch check
python -m pricewatch run --no-notify --show-excluded
```

`check` confirms your keys work. `run` does a real scan and lists every listing it threw out, so you can tune your filters.

### 5. Schedule automatic scans

```powershell
powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1              # every 60 minutes
powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1 -Every 15    # or every 15 minutes
Get-Content pricewatch.log -Wait -Tail 30                                            # watch results
```

To stop: `powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1 -Uninstall`

Scans run in the background while you are signed in, with no window popping up. A scan missed during sleep or shutdown runs once at the next chance. To keep a laptop scanning, set **Settings > System > Power > Sleep** to Never when plugged in.

### Common problems on Windows

| You see | Fix |
|---|---|
| `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and answer Y. |
| `py` is not recognized | Reinstall from python.org. The `py` launcher comes with it. |
| `python` opens the Microsoft Store | You are outside the virtualenv. Run `.venv\Scripts\Activate.ps1`. |
| `missing eBay credentials` in pricewatch.log | Scheduled tasks ignore `$env:` variables. Put your keys in config.yaml. |

---

## Linux

All commands go in a terminal.

### 1. Install Python

Most distributions ship Python 3.9 or newer. Install the virtualenv module and git:

```bash
sudo apt install python3 python3-venv git      # Debian, Ubuntu, Raspberry Pi OS
sudo dnf install python3 git                   # Fedora
sudo pacman -S python git                      # Arch
```

### 2. Download the code

```bash
mkdir -p ~/code && cd ~/code
git clone https://github.com/marshenmanhunter/marshenmanhunter.git
cd marshenmanhunter/ebay-price-monitor
```

### 3. Run the demo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pricewatch demo
```

You see 30 days of simulated scans, a price trend and alerts. See [what the demo shows](#what-the-demo-shows).

Each time you open a new terminal, get back in with:

```bash
cd ~/code/marshenmanhunter/ebay-price-monitor && source .venv/bin/activate
```

### 4. Connect to eBay

Get your keys first: [Get your eBay API keys](#get-your-ebay-api-keys). Then:

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Fill in your keys and items ([how to edit the config](#edit-your-config)). Save with Ctrl+O then Enter, quit with Ctrl+X.

```bash
python -m pricewatch check
python -m pricewatch run --no-notify --show-excluded
```

`check` confirms your keys work. `run` does a real scan and lists every listing it threw out, so you can tune your filters.

### 5. Schedule automatic scans

Open your crontab:

```bash
crontab -e
```

Add this line (every hour, on the hour). Replace `you` with your username, or run `pwd` in the project folder to get the full path:

```cron
0 * * * * cd /home/you/code/marshenmanhunter/ebay-price-monitor && .venv/bin/python -m pricewatch run --log pricewatch.log
```

For every 15 minutes, start the line with `*/15 * * * *` instead. Watch results with `tail -f pricewatch.log`.

cron skips runs while the machine sleeps. A Raspberry Pi or an always-on server avoids this.

### Common problems on Linux

| You see | Fix |
|---|---|
| `ensurepip is not available` | `sudo apt install python3-venv`, delete the `.venv` folder, redo step 3. |
| `externally-managed-environment` | You are outside the virtualenv. Run `source .venv/bin/activate`. |
| `missing eBay credentials` in pricewatch.log | cron ignores `export` lines. Put your keys in config.yaml. |

---

## Get your eBay API keys

Same on every system. Free.

1. Sign up at [developer.ebay.com](https://developer.ebay.com) and sign in.
2. Open **Application Keys** and create a **Production** keyset (not Sandbox, which holds fake data).
3. eBay asks how your app handles **Marketplace Account Deletion** notifications. You either set up a notification endpoint or claim an exemption. This tool stores no buyer or seller personal data (only item ID, title, URL, condition and price), which fits the exemption. Read eBay's wording and decide for yourself.
4. Copy the **App ID** (this is your `client_id`) and **Cert ID** (your `client_secret`) into config.yaml.

config.yaml is git-ignored, so your keys never get committed. For one-off runs you can instead set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` as environment variables. Scheduled scans only read config.yaml.

## Edit your config

config.yaml has four parts. The example file explains every setting in comments.

```yaml
ebay:
  marketplace: EBAY_US                     # EBAY_GB, EBAY_DE, EBAY_CA, EBAY_AU, ...
  client_id: YourApp-PRD-xxxxxxxx-xxxxxxxx
  client_secret: PRD-xxxxxxxxxxxx-xxxx-xxxx
  ship_to: {country: US, zip: "10001"}     # your location, for real shipping costs

notify:
  ntfy_topic: pricewatch-k3j9x2            # see Phone alerts below
  discord_webhook: ""

defaults:
  deal_pct: 0.20                           # alert at 20% below the likely-sold price

items:
  - name: Steam Deck OLED 512GB
    query: steam deck oled 512gb           # what you would type in eBay's search box
    require_words: [oled, 512]             # title must contain all of these
    exclude_words: [carrying case, skin, lcd]  # title must contain none of these
    condition_ids: [3000]                  # 3000 = used. Track new and used as separate items
    min_price: 150
    max_price: 900
```

Rules of thumb for items:

- Make the query specific. "steam deck oled 512gb" beats "steam deck".
- Put the model number in `require_words` and sibling models in `exclude_words`.
- Track new and used as two items. They are different markets.
- Set `min_price` above accessory prices and `max_price` above the new price.

## Phone alerts

**ntfy** (free, no account):

1. Install the ntfy app from the Google Play Store or Apple App Store.
2. Tap + and subscribe to a topic name nobody would guess, such as `pricewatch-k3j9x2`. Anyone who knows the name sees your alerts.
3. Put the same name in `notify.ntfy_topic`.

**Discord:** in your server, open **Server Settings > Integrations > Webhooks**, create a webhook, copy its URL into `notify.discord_webhook`.

Alerts show price, discount, seller feedback and a link that opens the listing.

---

## What the demo shows

The demo simulates 30 days of scans on a fake market (listings arrive, sell and expire, plus planted junk, scams and real deals) and runs it through the real pipeline. Sample result:

```
asking   median $481.55  middle half $449.81 to $514.56  (n=224)
sold*    median $414.66  middle half $390.69 to $442.12  (n=195, last 14d)
gap      asking median is +16.1% vs likely-sold
(simulator's real median sale price, last 14d: $410.46)
```

The asking median is 17% above what items sell for. The likely-sold estimate lands within 1%. That gap is the reason this tool exists.

## Read this before trusting any number

**Asking price is not market price.** Overpriced listings sit unsold and pile up. Well-priced listings sell within hours and vanish. A snapshot of active listings skews high. Flag "20% below the asking median" and you get alerts for normal prices.

**eBay does not give you sold prices.** The old Finding API (`findCompletedItems`) shut down in February 2025. The Marketplace Insights API (sold history) is limited to developers eBay approves. The Browse API returns active listings only.

**How this tool estimates sold prices:** it remembers every listing it sees. When a fixed-price listing disappears between two complete scans, it most likely sold. Its last price goes into the likely-sold pool. Some vanished listings were ended or relisted by the seller, so the estimate leans a little high. That errs toward fewer false alerts. It only works when a scan fetches every matching listing, so keep queries narrow.

**Default behavior:** alerts stay off until the likely-sold pool has 8 listings (`sold_min_sample`). In a busy market that takes hours to a day. For rare items where few listings vanish, set `baseline: asking` on that item and raise `deal_pct`.

**Junk is the real enemy.** A $40 "Steam Deck" is a box, a case, or a broken unit. Filters remove:

- titles with phrases like `for parts`, `box only`, `broken`, `as is`, `untested`, `replacement` (full list in `pricewatch/config.py`)
- your own `exclude_words` per item
- titles missing any of your `require_words`
- the "For parts" condition
- multi-variation listings (eBay shows the cheapest variant's price, so a $99 case option makes a $500 console look cheap)

Run with `--show-excluded` to audit what got dropped and why.

## Commands

Same on every system, inside the activated virtualenv.

| Command | What it does |
|---|---|
| `python -m pricewatch run` | One scan of every item. Prints stats and outliers, sends alerts. |
| `python -m pricewatch run --item deck` | One item only (matches part of the name). |
| `python -m pricewatch run --log pricewatch.log` | Same, output appended to a file. |
| `python -m pricewatch loop --every 60` | Scan every 60 minutes until Ctrl+C. Simple alternative to step 5. |
| `python -m pricewatch report` | Trend per item: daily median chart, 1d/7d/30d change, likely-sold median, cheapest listings. |
| `python -m pricewatch report --csv prices.csv` | Export every scan for a spreadsheet. |
| `python -m pricewatch check` | Test your keys. |
| `python -m pricewatch demo` | Fake-market simulation. |

## How often to scan

Hourly suits most items. Faster scans catch deals sooner and sharpen the likely-sold estimate. Underpriced listings on popular items sell within minutes because resellers run alert tools too, so scan those every 5 to 15 minutes.

**API budget:** the Browse API allows 5,000 calls per day by default. One scan costs 1 call per 200 listings, plus 1 extra call when a search has more listings than `max_pages` covers. 10 items x 3 pages x 24 scans = 720 calls per day. One item every 5 minutes = 288 calls per day.

## How a listing becomes an alert

A listing is a **deal** when all of these hold:

- price + shipping is at least `deal_pct` (20%) below the baseline median
- it sits at least `deal_min_z` (2.0) robust standard deviations below the median, so a wide-spread market does not fire on normal variation (spread = 1.4826 x median absolute deviation, floored at 2% of the median)
- the seller has at least `min_seller_score` feedback and `min_seller_pct` positive
- it sits less than `suspicious_pct` (55%) below the median

Anything failing the seller or "too cheap" rules becomes **check carefully**. It shows in the scan output and only gets pushed when `notify_suspicious: true`. Each listing alerts once, then again only if its price drops another 3%.

## Tuning

- **No alerts ever:** check for "learning" or "only N were fetched" warnings in `run` output. Narrow the query, add `min_price`/`max_price`, or raise `max_pages`.
- **Too many alerts:** raise `deal_pct` to 0.25 or 0.30, add exclude words, split new and used into separate items with `condition_ids`.
- **Mixed models in results:** add the model number to `require_words`, add sibling models (`xm4`, `lcd`) to `exclude_words`.
- **Bundles skew prices:** add `bundle`, `lot`, `with games` to `exclude_words`, or track bundles as their own item.

## Files

```
pricewatch/
  ebay.py      Browse API client (OAuth, paging, cheapest-first pass)
  listing.py   normalize API results, junk filters
  stats.py     medians, percentiles, robust z-score, trend helpers
  store.py     SQLite history (runs, listings, alerts)
  monitor.py   one scan: fetch, filter, measure, track sold, flag outliers
  notify.py    ntfy and Discord alerts
  report.py    terminal output, CSV export
  demo.py      fake market simulator
  cli.py       commands
scheduling/
  install-mac.sh        launchd job for macOS
  install-windows.ps1   Task Scheduler job for Windows
tests/                  python -m unittest discover -s tests
```
