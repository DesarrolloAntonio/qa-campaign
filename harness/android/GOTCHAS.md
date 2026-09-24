# Gotchas that cost a session each

Read this when something the harness does makes no sense, before you decide the app is at fault.
Every line here is one session someone lost. The rules themselves are in `SKILL.md`; this is the
Android-specific debris.

- **A test device that isn't disposable** — a managed work phone, someone's own phone — goes in
  `managedDevices`: `rotate`, `size`, `demo`, `clear-crashes` and `net.sh on/off/slow/full` then refuse
  on it unless the human agrees (`--allow-device-change`). Never `adb logcat -c` on such a device: it
  clears everyone's log (measured). The harness writes its files to `/data/local/tmp`, which a
  managed phone's USB policy leaves readable where `/sdcard` wasn't.
- **Two campaigns on one computer** share one adb server and one set of AVDs. An AVD runs **once**
  at a time — the emulator refuses a second instance — so campaigns running in parallel each need
  their own AVD; campaigns that take turns can share one (different app ids keep their data apart).
  Never `adb kill-server`: it cuts the other campaign's device. A plain adb command that starts a
  stopped server is harmless. The `devices` allow-list keeps each campaign on its own serial.
  Running the harness **from another campaign's folder counts as that campaign** — the claim names it
  by its config, so it can't protect the campaign from you: to look at a campaign's device, ask that
  campaign or wait until it releases it (measured: it resumed while the device was being driven from
  its own folder). The other campaign's app stays in the task stack, so every input command refuses when another
  app is in front (`--any-app` for a share sheet or a browser on purpose). **Taking turns on one AVD:** every harness command stamps the device with its campaign —
  `campaign` in `qa.config.json`, else the git root, so a second config of the same campaign (another
  app id) still counts as the same — and a command from another campaign within 30 minutes is refused — `ui.py avds` shows who has it. Run
  `ui.py release` whenever a campaign stops, so the other one doesn't wait out the 30 minutes.
- **Pull the `-wal` file too** when copying a SQLite database off the device, or you read stale rows.
- `uiautomator dump` reports **visible** bounds. Half-scrolled elements look small. (R8)
- Two `uiautomator dump` calls at once crash each other with *"UiAutomationService already
  registered!"*, and that lands in the crash buffer looking like an app crash. Filter by package.
- A `@Preview` is not a dead control. It is on S2's discard list for a reason.
- `id=` selectors read `resource-id`. In Compose that only exists if the app enables
  `testTagsAsResourceId`; without it they match nothing, silently. `text=`/`desc=` always work.
- `ui.py db` uses `run-as`, which needs a **debuggable** build. On a release build it refuses and
  says so.
- **Not every store is in `databases/`.** WorkManager keeps its queue in
  `no_backup/androidx.work.workdb`; DataStore lives in `files/datastore/` and is binary. Run
  `ui.py files` once per app and point the aliases at what is really there.
- **Some emulator images revert `user-rotation` within seconds** — seen on an older resizable phone
  AVD, not on a newer one (API 37 Resizable kept the lock). It depends on the image, so don't avoid
  resizable emulators for it: `rotate` re-issues the lock once and then refuses rather than pass; only
  if it refuses on *your* device, rotate from the emulator's toolbar or pick another device for R9.
- **A text with quotes can look cut short** — a campaign saw "No countries found for " with the
  search term gone, while the app showed it right. Not reproduced on API 37: the dump escaped `"` and
  `'` and read the whole text back (measured). If a text looks cut, check it with `ui.py shot` before
  filing anything.
- **A modal bottom sheet or dialog is its own window**, and the dump returns only that window: the
  screen behind it — a snackbar raised there included — is invisible until it closes. Close it and
  dump again before concluding anything is missing (measured: a message was found only that way).
- **Gboard's stylus pill can sit on top of the app** — over a nav rail it took a tap meant for the
  rail and raised another app's permission dialog. The input guard caught it; `adb shell am force-stop
  com.google.android.inputmethod.latin` clears the pill without changing a setting (measured).
- **`ui.py size` changes width and density together** (tablet 240 dpi, phone 420): compare layouts in
  dp, never columns or pixels across presets — the tool warns when the density changed.
- **Kotlin Multiplatform: no comma in a backtick test name.** Kotlin/Native rejects it, and it surfaces
  as an iOS *compile* error in `allTests` minutes after the edit, not as a test failure (three times
  in one campaign).
- `input text` **drops non-ASCII** (ñ, é, emoji): every fixture typed by the harness is ASCII, so
  non-ASCII data never round-trips through STORE and API unless you create it through the API.
- **Gboard on an emulator shows a stylus pill, not a keyboard**, every time a field gets focus — a
  small floating toolbar that doesn't take BACK. `ui.py show-keyboard` brings a real keyboard up with
  the pill's own Alt+K; `hide-keyboard` sends nothing while only the pill is up. For the whole run,
  `settings put secure stylus_handwriting_enabled 0` gives the keyboard from the next focus — a device
  setting, so ask first.
- **A Toast is not in the accessibility tree**, so `dump`, `find` and `assert` never see one; a
  snackbar is. To read a Toast: `adb shell uiautomator events` while you trigger it — it is a
  UiAutomation session, so never at the same time as a `dump` — or a screenshot taken at once.
  Take screenshots with `ui.py shot`, not a raw `adb exec-out screencap`: on a two-display emulator
  the raw one comes out unreadable (measured), and `shot` picks the display.
- **Tests on the device reinstall the app, and uninstall it when they finish.** Android's
  `connectedAndroidTest` installs over the app **keeping its data**, runs, and removes it. So after
  every red or green on the device the injected session is gone — inject it again before driving by
  hand — and whatever a manual check left in the store is there for the next test run (measured: a
  pending change left by hand made a negative pair fail). Their reports land in
  `build/outputs/androidTest-results`, which `redcheck.py` also reads. **Claim a red or a green only
  through the Gradle task**: `am instrument` by hand writes no JUnit XML at all — nothing for
  `redcheck.py` to read — so keep it for exploratory driving, where no colour is claimed.
- **`ui.py kill` checks that the process really died.** `am kill` once left it alive on API 37.1
  (same pid before and after) while saying it had killed it, and two process-death checks proved
  nothing (measured). `kill` now reads the pid after, finishes a debuggable app with `kill -9`, and
  refuses when it is still alive.
- **The device can't resolve a name this computer resolves.** An emulator takes the computer's first
  DNS server when it boots, so with another VPN in front of it, the VPN's own names stop resolving on
  the device (measured with Tailscale). Boot it with `-dns-server <that VPN's resolver>` —
  `100.100.100.100` for Tailscale. Before building a relay, try another address for the same server:
  an emulator got "No route to host" on a LAN address and reached the same server by its Tailscale
  name at once (measured); the relay built the first time was never needed.
