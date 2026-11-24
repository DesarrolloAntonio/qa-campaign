# How a session gets into the app

The detail behind `SKILL.md` R11. Read it when setup reaches §2.1 step 11: the rule is there, the
mechanisms and what each has cost are here. In order of preference:

1. **A test that runs inside the app and writes the session** — an instrumentation test on a
   debuggable build writes to the app's secure storage exactly what the login would have written.
   Works for any Android app; ~50 lines. The test runs on the device and the credentials file is on
   the computer: put the value into the **test build** when it is built (generated into the build
   folder from the gitignored file, never into source), and uninstall the test app once the session
   is written. Never pass it with `am instrument -e` (a command line, visible to other processes
   and kept in shell history) and never `adb push` the file (a loose copy left on the device).
2. **Write the store directly** (`run-as` on a debuggable build) when the session lives in a plain
   preferences file or database. The transport is the part to get right, because the obvious two
   break R11's rules: **stream it over stdin**, so the value is never an argument and no copy is
   left on the device —
   `adb -s "$(ui.py serial qa)" shell run-as <pkg> tee shared_prefs/<file>.xml < local.xml >/dev/null`
   (`ui.py serial` because raw adb doesn't know the allow-list). Paths are relative to the app's data
   folder. `tee` rather than `sh -c 'cat > …'` because the redirection has to reach the device's shell
   as **one** argument: unquoted, `sh -c 'cat > …'` was taken apart on the way and answered
   "Permission denied" (measured on API 37; `adb shell "run-as <pkg> sh -c 'cat > …'"`, all in one
   string, works too). A session inside SQLite needs the device's own `sqlite3` — emulators have it,
   many phones don't — and where it isn't there, mechanism 1 is the answer. The harness has no `put` command on purpose: what the session is made
   of is the project's, not the skill's.
3. **A debug-only launch argument** that accepts a token — app code, development builds only, and
   **only for a token that is ordinary test input**: one minted on a disposable server you run, or a
   declared test identifier. A real server's token never goes on a command line (above).
4. **A credential read from hardware** — an NFC card, the IMEI, a serial: the emulator cannot
   produce it. Inject the session it results in (1–3), ask at setup whether the **server** also checks
   the device, and put the real tap on a physical test phone in the queue.
5. **Log in once by hand and snapshot the device** — the human signs in, the emulator or
   simulator is snapshotted logged-in, and every run starts from that snapshot. This is the answer
   for iCloud, two-factor and anything else with no programmatic path.
6. **The session belongs to another app** — a companion app hands it over (a ContentProvider, a
   launch intent with the user's id). Drive that route: the companion signed in by the human, or its
   launch extra with a **test** identifier (below). **Whether writing the app's own store works at
   all is read from the receiving code, not assumed**: an app that keeps a copy of the hand-off can
   be injected and survives a cold start; one that re-reads the companion on every start signs out
   again, which is what was measured here. Before writing an injector, grep the receiving Activity
   for `getStringExtra`/`hasExtra` to learn the exact extras it parses — and for a debug injector the
   app may already have.
   **Keep a simulated hand-off consistent with its source:** a launch extra saying "this driver" while
   the companion app reports nobody signed in is a state no user has, and the next cold start signs
   out by design (measured). Don't file what only that contradiction produces.
