# Keel

A private budgeting app for Mac, Windows and iPhone. Accounts, budgets, cash flow, forecasts,
reimbursements, shared costs with a partner, recurring bills, goals and debt payoff.

Your data stays on your device. Nothing is sent anywhere. Each install keeps its own data, so use
**Categories → Your data → Everything (JSON backup)** to save a copy, and **Restore from a JSON backup**
to move it to another device.

## Bank sync

Keel can pull balances and transactions from your banks through
[SimpleFIN Bridge](https://beta-bridge.simplefin.org/), a read-only service with a small yearly fee.
It works in the Mac, Windows, iPhone and web versions. The Claude page cannot reach outside services,
so it has no bank sync.

1. Create a SimpleFIN account, link your banks, and create a setup token.
2. In Keel, open **Accounts**, paste the token under **Connect your bank**, and press **Connect**.
3. Choose where each bank account goes, then **Save and import**. Keel brings in up to 45 days of history.

After that Keel syncs on its own when it is open, at most every 4 hours, and **Sync now** pulls on demand.
Banks send new data to SimpleFIN about once a day, so a purchase shows up the next day, not the moment
you pay. Your categories, notes and splits stay put when a bank updates a transaction, and a pending
charge keeps your category when it posts.

The connection key never goes into backups. The desktop app encrypts it with your Mac Keychain or
Windows account. The web and iPhone versions keep it in that device's storage. SimpleFIN cannot move
money, and Keel never sees your bank password.

## Windows

1. Download `Keel-Windows-2.2.0.zip`, or the `Keel-windows` build from GitHub Actions (see below).
2. Unzip it anywhere, open the folder and run `Keel.exe`. The Actions build also gives you
   `Keel-Setup-2.2.0.exe`, a normal installer with a Start menu shortcut.
3. Windows shows "Windows protected your PC" because the app is not code-signed. Click
   **More info → Run anyway**. A code-signing certificate removes this warning.

## Mac

1. Download the `Keel-mac` build from GitHub Actions and open `Keel-2.2.0-universal.dmg`.
   It runs on both Apple Silicon and Intel Macs.
2. Drag Keel into Applications.
3. The first time, right-click Keel and choose **Open**, then **Open** again. If macOS still blocks it,
   go to **System Settings → Privacy & Security** and click **Open Anyway**. An Apple Developer ID
   (Apple Developer Program, paid yearly) removes this step.

To build it yourself on a Mac: install Node.js 20 or newer, then in this folder run
`npm install` and `npm run dist:mac`. The app lands in `dist/`.

## iPhone and iPad

Three ways, easiest first.

1. **Open the Claude link.** The Keel page on claude.ai works on iPhone in Safari or the Claude app,
   and keeps the same data you see there.
2. **Install the web version.** Put the `web/` folder on any HTTPS host (GitHub Pages works). Open it
   in Safari, tap **Share → Add to Home Screen**. It opens full screen and works offline.
3. **Build the native app.** Needs a Mac with Xcode.
   ```
   npm install
   npm run ios:add
   npm run ios:open
   ```
   In Xcode, pick your Apple ID under **Signing & Capabilities**, plug in your iPhone and press Run.
   With a free Apple ID the app stops opening after 7 days until you run it from Xcode again.
   Keeping it longer, or putting it on the App Store, requires the Apple Developer Program.
   After changing the app, run `npm run ios:sync` before building again.

## Building with GitHub Actions

The workflow in `.github/workflows/keel-apps.yml` builds the Mac and Windows apps on real Mac and
Windows machines. Open the repository's **Actions** tab, choose **Build Keel apps → Run workflow**,
and download `Keel-mac` and `Keel-windows` from the finished run.

## Working on the app

- `src/keel-budget.html` is the app, the same file published as the Claude artifact.
- `npm run build:web` turns it into the standalone app in `web/`. Run this after editing `src/`.
- `npm start` opens the desktop app. `npm run serve` serves the web version at http://localhost:5173.
- `node tools/gen-sample.js out` regenerates the sample household. Copy `out/local.json` to `src/sample.json`, then run `npm run build:web`.
