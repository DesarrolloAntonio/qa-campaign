---
name: qa-campaign
description: Run a gated, evidence-based pre-release QA campaign on any project you can drive and query. Enumerate every control, sweep for what the product is MISSING (not just what it has), cross-check every claim against independent oracles instead of one, and prove every regression test by watching it fail first. Use when preparing a release, auditing a feature end to end, or when "we tested it" needs to mean something. The rules are platform-independent; an Android harness is included, and any other platform needs a harness that implements the seven-capability contract in harness/README.md.
license: MIT
metadata:
  keywords:
    - qa
    - release
    - testing
    - android
    - ios
    - web
    - offline-first
    - regression
---

# QA campaign

A process for testing a whole product before release, in a way that produces evidence instead of
confidence.

**The scripts in `harness/` are the cheap half.** What finds defects is the set of rules below.
Each earned its place on a real release campaign — most because its absence let a real bug through,
a few because they stopped the campaign from lying about what it had done. Read them before running
anything.

The rules are generic. The **examples are not**: they come from the one campaign this was extracted
from — a mobile client for a self-hosted server, with notes, boards and shared folders. When a rule
mentions a trash, a shared note or a server quirk, read it as *"the kind of thing"*, and substitute
your own.

---

## 1. The rules

### R1 — Gates, not a checklist

Split the product into **sequential processes** and put a **gate** at the end of each. What closes
a gate depends on the **fix mode** chosen at setup (§2.1):

- **Fix severe** *(default)* and **fix all**: every finding the mode covers is fixed and verified in
  the running system; the rest is **deferred with an id in the user queue (R2)**.
- **Report only**: every finding is **documented** to the standard of §2.3 — exact steps, the
  oracles' evidence, the file:line, the likely fix — and nothing in the product is changed.

In every mode: the full suite is green (R13), the fixtures are cleaned (R10) and the run report is
written. Items sitting in the user queue are not "open work" for gate purposes — that is what the
queue is for.

The order, one platform at a time:

```
shell → one process per feature module (primary target, online)
→ second form factor / window size → offline → second device or account → release build
```

When the product's devices are **shared between people** — a fleet app, a shift terminal — switching
the signed-in person is the core of the shell, not a late process: put it in the shell gate.

Later processes are the ones that can invalidate earlier work if they change; that is why they come
after, not before. Drop what does not apply. `templates/CAMPAIGN.md` is this order as a table;
§2.2 is what closing a gate means step by step.

**How deep offline goes** is decided once, at setup, from the code — not by habit. Whether to test
offline at all depends on one thing: **does the product talk to a server?** How deep depends on
what it keeps locally:

| Depth | The product… | Offline testing |
|---|---|---|
| **None** | talks to no server | no offline gate, no API oracle, no adapter — the rest of the method stands |
| **Short** | talks to a server but keeps no data of its own (always online), or keeps a **read-only cache** | inside each module's process only: every screen says clearly that it can't reach the server, nothing spins forever (S4), nothing pretends a write was saved, and it recovers when the network returns. No gate of its own |
| **Full** | keeps its own data and **writes it locally first** (offline-first) | each module's controls driven online *and* offline, **and** the drain-and-reconcile gets a gate of its own: every write queued, sent later, conflicts resolved, nothing lost |

The kind of storage is a hint, not the answer: a local database can be only a cache (short), and a
preferences file can hold a list of pending changes (full). The clues that decide it:

- **a queue of pending writes** — a background job that sends changes later (WorkManager,
  BackgroundTasks, Background Sync), or a *pending / dirty / syncStatus* field in the stored data →
  **full**;
- **screens read the local copy first** and refresh from the server afterwards, *and* edits land
  locally before the server answers → **full**;
- local reads but every edit waits for the server → **short** (a cache);
- network calls and nothing stored beyond settings and the session → **short**.

When the clues disagree, take the deeper level. At either depth, **test the recovery on its own**:
"it says it can't reach the server" and "it works again when the network returns" are two checks. A
map said the first and never did the second — the P1 was in the half that's easy to skip (measured).

**At full depth, test the mix, not only the two halves.** For every kind of write: make it offline,
then — **before the queue drains** — make another change to the same record online, and check both
reach the server. An online save that sends only its own field and then marks the row as synced
throws away what was waiting in the queue. Measured: four P0s in one campaign, in three modules,
none of which showed up offline-only or online-only.

A flat checklist of N scenarios × M devices is never executed. A short list of gates with a hard
stop at each one is.

**A gate waiting on the human** — a device to create, an account to fill in — doesn't stop reading.
The next process may be **prepared from the code**: its inventory, its suspects. Nothing is driven,
fixed or committed for it until the gate closes, and what was prepared is re-read then, because the
human's answer can change it. When **the gate's own criterion** depends on the human — "every entry
point reachable" needs them signed in to another app — close it **assuming the queue item**, name the
item in the log, and reopen when the answer comes back different (R2).

### R2 — Defer everything that needs the user

Anything that needs a human — a real login, a physical device, a product decision, any
**irreversible action on real data** (emptying a trash, deleting an account) — goes into a **single
queue at the end of the plan**, not inline. Otherwise the campaign stalls on
its first blocker and never restarts.

Every queue entry records **which gates were closed assuming what**. When the human answer changes
that assumption, those gates reopen — the same logic R1 applies to platform and form factor.

**Putting the queue to the human.** Don't walk it one question at a time: thirteen questions in a
row tire the human, who stops reading them halfway (measured). Two groups, in this order:

1. the few items that **change what the campaign does next** — a real login, a scope decision, a
   suspect to chase — one at a time;
2. everything else — "fix or accept" on a small finding, a wording, a display format — in **one
   list**, each with your recommendation and why in one line, answered in one go.

**Don't stop for each finding.** A campaign that asks after every bug turns the human into the
bottleneck and gets abandoned; findings go into the run report and the gate is where the human
reads them. Stop **at once**, and only, when:

1. **A P0** — data loss, a security hole, or real data at risk. The human needs to know now, not at
   the gate. First check **which builds reach it**: a screen or path gated by build type or flavor
   is rated for the builds users get — a campaign stopped for a P0 in a debug screen only its staging
   flavor shows (measured). A P0 found while setup is still **looking**, before its round of
   questions, goes to the human in that same round, first.
2. **A blocker** — the finding makes the rest of the process untestable (the app won't launch,
   login is broken). Carrying on only produces noise; say what is blocked and what still can be
   tested.
3. **Leaving the agreed ground** — what setup agreed on (§2.1, "what already exists"): creating or
   deleting a device, building or starting a server, downloading and running something, pointing at
   a server that is not the agreed test server, or any irreversible action on data the campaign did
   not create. Ask first.
4. **Calibration, once per campaign** — after the **first P1-or-worse finding**, show it and
   confirm the severity and the fix mode match what the human expects. Then carry on uninterrupted.

### R3 — Inventory before catalogue

Before testing a module, **enumerate its controls**: every button, menu entry, dialog, gesture and
field of its UI state — *and* every entry point that is not a control: deep links, share targets,
notification actions, widgets, shortcuts. Those live in the manifest or the router, not the UI
layer; a shell gate that says "every entry point reachable" without them has not tested them.
`templates/inventory.md` is the shape. Some entry points exist **only with certain data** — a Home
section shown only when something is coming up was one of a screen's two ways in, and on the day it
was tested it wasn't there (measured). Note them as such, and re-check "every entry point reachable"
when the data changes, not only when the code does.

**A delegated inventory is a list of suspects.** A subagent reading a large area is fast and
thorough, but it states claims from the code with the same confidence as facts, and two of them didn't
hold on the device (measured). Take its rows as controls to drive; a finding exists only once driven.

Enumerating from the code gives you everything the product **has** — which most plans never do, so
they test a guess at the product instead of the controls that exist. What it cannot see is what the
product **lacks**. That is R4.

### R4 — The absence sweeps (what the product does NOT have)

R3 is **structurally blind to missing features**: a feature that doesn't exist leaves nothing to
enumerate. So run four sweeps — **once, for the whole product, at setup** (§2.1), filing each finding
under its module. Before writing a module's catalogue, re-read that module's findings; re-run the
sweeps for it only if its code changed since. Each sweep is a **grep for candidates followed by a
fixed discard list** — reproducible, but not judgement-free, and the discard list is part of the
rule:

| # | Sweep | How | Discard | Catches |
|---|---|---|---|---|
| **S1** | Data held but never shown | For each field of your domain models / UI state, grep for references in the UI layer. Zero references = candidate. Also **values the screen computes and decides with but never states** — today's date on a calendar, the one-year window it asks the server for — which no grep of fields finds (measured). | fields that are ids, timestamps, or sync bookkeeping; credentials and session tokens (never shown by design) | A settings screen that never says which server or user you're connected to |
| **S2** | Dead control | Empty or TODO handlers, *including* empty lambdas passed down as arguments: Compose `grep -rnE 'onClick *= *\{ *\}|\w+ *= *\{ *\}|/\* *TODO' --include='*.kt'`; web `grep -rnE '=\{\(\) *=> *\{\}\}|href="#"' --include='*.tsx'`; SwiftUI `grep -rn 'action: {}' --include='*.swift'`. Then routes: every `navigate(x)` has a matching destination. | previews, read-only chips, disabled placeholders; an empty **default value** in a function's signature (`onClick: () -> Unit = {}`) — for those, follow the callers: a candidate only if a real screen leaves it empty | "Privacy Policy" and "Help" buttons that do nothing (a store blocker) |
| **S3** | Expected absence | **Enumerate REF (R5), not your imagination**: walk the reference implementation's navigation, settings and menus and write down every feature name; grep your code for each term; zero files = absent. | features REF has that are out of scope *by written decision* — **while the code still agrees**. A written decision the code has since contradicted ("out of scope" in the README, built by a later commit) is not a discard: it goes to the queue as "which decision stands" | No quota, no licences, no changelog, no clear-cache |
| **S4** | Stuck when something fails | Controls that work when everything goes right and never recover when something goes wrong. Find where work starts — a flag set to true, a `Loading` state, a button disabled — and check each is undone on the **failure** path too, not only on success. Then error handlers that are empty or only log, searched **across lines**. Commands below the table. Drive each candidate with the network cut or the server stopped. | undone in a `finally`, or by one state that covers both outcomes | A spinner nothing ever clears after the server says no; a save button that stays disabled |

The S4 searches, Kotlin first. Each misses something if you narrow it: `ing *= *true` alone missed
`_isRefreshing.value = true` and sealed `Loading` states, and a one-line `catch {}` grep found **0**
on a codebase with 16 empty or log-only handlers, because formatted code puts the body on its own
line (measured):

```bash
# where work starts — then check each one is undone when it fails
grep -rnE 'ing *= *true|\.value *= *true|Loading\b|enabled *= *!' --include='*.kt' .
# empty or log-only error handlers, across lines (-U lets a match span lines)
rg -U -n 'catch\s*\([^)]*\)\s*\{\s*((Log\.\w+|println|Timber\.\w+|logger\.\w+)\([^)]*\)\s*)?\}' --glob '*.kt' .
rg -U -n 'onFailure\s*\{\s*\}' --glob '*.kt' .                                   # Kotlin Result
rg -U -n 'catch\s*\{\s*\}' --glob '*.swift' .                                     # Swift
rg -U -n '\.catch\(\s*\(\s*\w*\s*\)\s*=>\s*\{\s*\}\s*\)' --glob '*.{ts,tsx,js}' .  # JS
# no ripgrep: perl -0777 reads a whole file at once, so the same pattern can span lines
```

**A candidate you can't provoke** — a save racing the screen closing, a server refusing one item
among several — can't be driven by cutting the network or stopping the server. Don't file it as
clean, and don't guess. **First, change the campaign's own fixture on the server so that one call
fails** — moving a `QA_` bookmark's URL made the app's upload fail once while the refresh still
worked, and confirmed a P0 in minutes (measured). Only when the data can't do it: in a fix mode, add
a **debug-only fault switch** (a flag in the debug build
that makes that one call fail, with a test proving the release build ignores it) and drive it; in
report-only, or when the switch would touch too much, queue it as *"unproven — can't be driven"*,
with the code path as the evidence.

S2's greps are first-order: a handler that calls an empty function escapes them. Say so in the
report. S4 exists because S2 only finds controls that are dead for everyone; the more common dead
control works on the happy path and dies when something fails — which is exactly when the user needs
it. S3 needs an input you don't have in the repo — a REF. Without one it degrades to a list you
wrote yourself, and a list you wrote yourself has the same blind spot as your code: **skip S3, say
why in the report, and queue "is there a reference?"** rather than run the degraded version.

Comparing against a **sibling** — the other platform's client, the previous version — is a
*different* net: it catches what one has and the other lacks. It says nothing when **both** are
missing something. You need both nets, and R5 says which is which.

### R5 — Never one oracle

An oracle is something you can query that answers yes or no:

| Oracle | What it is | Where it comes from |
|---|---|---|
| **UI** | the screen as text — accessibility tree, DOM | the harness |
| **STORE** | the client's own persistence — SQLite, IndexedDB, settings files, the background work queue | the harness — and a project-side reader for formats it can't decode |
| **API** | the server, queried independently of the client | your adapter |
| **EYE** | a screenshot, read by a human or a model | the harness |
| **LOG** | what the app writes to the system log — where secrets leak, and evidence of which path ran; never proof that anything was saved | the harness (`ui.py log`, secrets hidden) |
| **REF** | the implementation that is the **full list of what the domain supports** — the vendor's web client, the spec | you |

Siblings (the other platform's client, the previous release) are *not* REF: they share your blind
spots. The **UI / STORE / API triple** is what every platform has: a backend service has the
response it gave, the row it wrote and what a downstream system sees; a CLI has stdout, the files it
touched and the exit code. EYE is any rendered artefact a human can look at; REF is whatever
document or system defines what the product should do.

**Scope.** A claim that something was *written, synced, granted or deleted* needs at least two of
UI / STORE / API — an optimistic UI that reported success for a write the server refused is
invisible to any single one. A pure-UI claim (a dialog opened, the back stack is sane) needs the UI
oracle plus a second look: EYE, or the same UI read again after a recreation (R9).

Four ways the UI oracle says less than it seems, all measured:

- **A form that closes on save has told you nothing.** The screen going back is not the write: every
  finding in one process needed the API to be seen.
- **Some screens only hold what they draw.** A map's markers exist in the tree for the current
  viewport only, so the same filter answers differently wherever the map happens to be. Bring such a
  screen to one known view (fit everything, zoom out) before comparing.
- **A modal window hides the rest.** With a sheet or dialog open, the dump is that window alone; a
  message raised behind it is invisible until it closes. Before concluding something is missing,
  close what is modal and look again.
- **Accessibility is more than `a11y`'s warnings.** It reported 0 on screens where the selected filter
  chip and the only action on the page exposed no state and no action. For what matters on each
  screen, check that its state (selected, checked) and its action are exposed — **in the attribute
  that control uses**: a Compose filter chip or switch says `checked` (✓ in `dump`), a tab or nav item
  says `selected` (•). A finding "the chosen chip exposes no state" was filed on `selected="false"`
  while the chip said `checked="true"` all along (measured).
- **A screenshot nobody opened is not an oracle.** Across nine processes screenshots were taken and
  saved, and every screen was judged from the dump — which says what text is there, not whether it is
  cut off, overlapping or crowded. The human saw a date field pushed out of its card in one glance;
  opening the screenshots then found eight more (measured). **Every screen a gate calls verified has
  had its screenshot opened and described**, and the report quotes what was seen.

**When oracles disagree**, that is a finding until R8 shows an oracle wrong, and the report names
which. Online, API decides. Offline, STORE's pending queue decides and API is consulted only after
the drain. When the API contradicts *itself* (a list endpoint says one thing, the item endpoint
another), the outcome of a **write** is the oracle, and the read quirk goes into the adapter's
quirk list.

**When it is unclear what the product should do, REF decides** — open it, look, copy the behaviour.
What REF does not settle, or where REF looks wrong, is a product decision: R2 queue, not a guess.
Record which REF you copied and its version.

### R6 — Seen red, always

**A regression test does not exist until you have watched it fail.** This is not mutation testing;
it is one deliberate break per test, recorded:

- a test for a **fix**: revert the fix, run, see red, restore, see green;
- a **negative pair** (R7): invert the guard it protects;
- a **migration test** (R14): drop the column default or the `ALTER`;
- a fix that **removes** something — a stored field, a parameter, a call — has nothing to revert
  *to* without rewriting the old code: break the part that can come back instead (the clean-up of
  what was stored, the guard that stops the call) and say in the report that this was the break;
- a fix that lives in a **build-type value** (a release or QA `buildConfigField`, a manifest
  placeholder) that no unit-test variant compiles: the red and green are **the generated files of
  each variant** — read the built `BuildConfig` or merged manifest before and after, and say so; it is
  a check, not a test (measured: AGP 9 builds unit tests for debug only);
- anything else: name the one-line change that must make it fail, and make it.

**Red for the reason the test names.** Read the failure: it must be the test's own check saying
"expected this, got that". A crash, a compile error, a timeout or a test-runner failure *before* the
check is not red — the test never ran. Measured: on an Android 17 emulator every UI test crashed
inside the testing library before checking anything, and that crash was read as the red. The same
goes for green: the test ran and passed — not skipped, and **not handed back by a build cache**. The
red and the green of the test a fix touches come from a real run — `harness/redcheck.py` runs the test and says RED, GREEN or NOT RUN from
the reports that run wrote, and with `--break FILE OLD NEW` makes the break itself and puts the file
back, checked byte for byte (measured: a break undone by hand left four files broken after a correct
red) (by hand, Gradle: `--rerun --no-build-cache`
on that test task), and **the result you read must be from that run**: check the report's time is
after the run started. Measured twice in a row: a break re-applied after a restore came back
UP-TO-DATE, and the report on disk was the previous run's. **In shared code, name the target:** a
Kotlin Multiplatform test has an Android task and an iOS task, and a final run re-ran only the iOS one
while the Android copy of the very test the fix added was up to date (measured) — the green you report
says which target ran it.

**Check what the test touched.** A red is only as good as the element it acted on:
- **a selector that can match twice** — two panes on screen, each with a back arrow of the same
  description — takes the first one. A test pressed the wrong arrow and "rotating leaves Notes" was a
  finding the selector invented (measured). When a red is surprising, count the matches (`ui.py find`
  lists them) and scope the selector to its pane;
- **what isn't on screen doesn't exist** for UI tests: in landscape, a field below the fold of a
  scrolling dialog is invisible to UiAutomator, and a rotation test looking for it was red with and
  without the fix (measured). Assert on something visible in both orientations, or scroll to it first.

**A test that never ends is neither red nor green.** A regression test for an endless re-save looped
inside the test and held the module's run at full CPU for twenty minutes, in silence (measured).
Give every run a time limit — Gradle `tasks.withType<Test> { timeout.set(Duration.ofMinutes(15)) }`,
JUnit 5 `@Timeout`, JUnit 4 `@Test(timeout = …)`, coroutines `runTest(timeout = …)`; macOS has no
`timeout` command (`gtimeout` from coreutils, or `perl -e 'alarm shift; exec @ARGV' 900 ./gradlew …`),
and a test task has no limit of its own by default. Make a loop *fail* rather than spin — a fake that refuses the call after the few it expects — and a run that
stays silent past its limit is stopped and reported as a hang, which is a finding in itself.

A fix with **no** test is allowed — a visual defect, a device-only behaviour — and the report says
so in those words (`device-only, no test — because …`). What is not allowed is a test that was never
seen red: that is how a suite grows to a thousand green tests that assert nothing. **When the test
environment can't reproduce the defect** — a Compose test window is taller than a phone, so a sheet
cut off on the device shows whole in the test (measured) — a test written anyway stays green whatever
the fix does: delete it, and call the fix device-only with that reason. The same when the test **can't
drive the path reliably** — list rows with no test tag, where every way of tapping them from the test
flaked (measured): verify the fix on the device, call it device-only, and put the missing hook (a
`testTag`, an accessibility id) in the user queue as the change that unblocks the test. A test that
passes one run in three is not kept in the suite, and the fix is not held back waiting for it.

### R7 — Negative pairs

A test that asserts "X is not deleted" needs its twin asserting the case where X *should* be
deleted. Otherwise a fix that simply breaks the whole feature passes.

Every "doesn't happen" test carries its "does happen" pair. Where there is no absence to assert — a
cosmetic fix — there is no pair, and the report says "n/a".

**A break that leaves the test green means the test is wrong**, not that the pair is unnecessary.
Measured: inverting the guard of a "not pruned" test left it green, because its fixture page still
contained the bookmark — the assertion was true for another reason. Find that reason before trusting
either test.

The same shape applies to **authorisation**, and it's cheap: three accounts — **A** owns, **B** is
granted access, **C** is granted nothing. Every share/permission feature is tested from B (sees it,
can do what was granted and nothing more) *and* from C (sees nothing). C is the negative pair; a
campaign that only ever logs in as the owner has not tested permissions at all.

**Roles are permissions too.** An owner and a read-only visitor, an admin and a member: each role
gets its own account, and each is tested for what it can do *and* for what it must not — the
read-only account's write is refused by the server, and the app says so instead of pretending. The
account with the fewest rights is the negative pair. Skip B and C only when the product has **neither
sharing nor roles**.

**A second account is still needed whenever the app keeps anything per account** — a session, a
cache, a search, a log — even on a backend where every account sees the same data. There B is not
about permissions: it is about **what one session leaves for the next**. Measured: on a single-library
server with no sharing or roles, B found a leftover search and the previous account's network log.

### R8 — The harness is under test too

When your tooling reports a defect, **its first suspect is itself**.

Real example: an accessibility checker flagged two "touch targets below the minimum" on a tablet.
Both were the tool measuring elements that were half-scrolled out of view — `uiautomator` reports
*visible* bounds. Fixing the tool removed two false findings and, more importantly, stopped training
the operator to ignore it.

A false positive costs more than a miss: a missed defect is one defect, but a tool that cries wolf
gets ignored, and then it misses everything. The mirror image is a **silent all-clear**: a tool that
cannot reach the device, or has no configuration, must refuse — never print "0 warnings".

When you change the harness, prove the change in **both directions**: the false positives are gone,
*and* a real finding is still caught (re-introduce one and check).

### R9 — "The UI gets recreated" is an axis of its own

Every platform has a moment where it throws the UI away and rebuilds it from whatever state you
bothered to save. That is where badly-saved state falls over, and **no catalogue derived from the UI
will ever cover it**, because nothing in the code enumerates it.

| Platform | What recreates the UI |
|---|---|
| Android | rotation, process death (`ui.py kill`), font-size or theme change, split-screen |
| Web | reload, restore from bfcache, tab discard |
| iOS | rotation, jetsam, scene reconnection, multitasking resize (Split View / Stage Manager — a compact↔regular size-class change) |
| Desktop | window resize across a breakpoint, sleep/wake |

**First find out what recreates the UI in *this* app.** An app can declare that it handles some of
those changes itself — on Android, `android:configChanges` in the manifest (`orientation`,
`screenSize`, `uiMode`, `fontScale`…). Then rotating recreates nothing, and `rotate` proves the
screen turned, not that any state was rebuilt: counting it as an R9 test counts a non-event
(measured on a Compose app that declared them all). For each change the app handles itself, test
something different — the layout adapts and nothing typed is lost as it re-lays out. **Process
death** (`ui.py kill`) recreates the UI in every app, so it is always an R9 test — except where a
cold start is **by design a sign-out** (the session is re-read from elsewhere on every start): there R9
checks that it signs out cleanly and leaves nothing behind, and "state lost after kill" is not a
finding (measured on a fleet app).

Ask it of every screen — especially with a **half-filled form, an open dialog, or a scrolled list**.
On a single-device iPad campaign the "second form factor" of R1 is a window size, not a device.

⚠️ **Assert that it actually happened.** On Android,
`adb shell settings put system user_rotation 1` writes the property and **does not rotate the
screen** while auto-rotate is on: the test passes without having tested anything. Whatever your
platform, read the rotation or size back from the system before asserting anything else.

### R10 — Destructive only on fixtures you made

**First choice: a server nobody else uses.** When the backend is something you can run yourself —
open source, self-hosted, a container — a disposable copy started for the campaign takes real data
out of the picture entirely: every account and every row on it is the campaign's. Propose it at
setup when there is no test server yet (§2.1, "what already exists"); don't just start one — the
human may already have a test server, and starting one is a stop (R2). On a disposable server,
record how it is started and thrown away, and which version of the server it runs.

Otherwise — a shared test server, or the real one — error paths and destructive flows get tested
only against fixtures **the campaign created**, with a recognisable prefix (`QA_`). Clean them up at
the gate and verify the cleanup through the API.

**A fixture you did not choose the id of is not yours yet.** Sample data that ships with the project —
a seeding script, a demo record in the code — can carry the **same id** as a live record: injecting one
overwrote a real record on the server (measured). Before injecting any fixture, ask the server whether
that id is already taken, and give the campaign's copies ids of their own.

**A stored flag has other readers.** Flipping something in the app's own store to reach a screen — a
licence bit, a feature flag, a role — is not a read-only act: one flipped to open a screen also changed
which records the app's own clean-up deleted, and it deleted a record that was not the campaign's
(measured). Grep who reads a flag before changing it, and say in the report that it was changed.

**On the real server**, three more things:

- **Test accounts, never a personal one.** The human creates them — A, and B and C if R7 needs them
  — and the campaign never creates or deletes an account itself (R2, stop 3).
- **Server errors come from somewhere else than the real server.** Cut the network, point the app at
  an address that doesn't answer, or run a **fake server** on the computer that answers with the
  errors you need (a 500, a 412, an HTML page instead of JSON) — `harness/fake_server.py` does that
  and prints what the app sent. From an emulator, reach it through `adb reverse` and `127.0.0.1`:
  the device's shell reached `10.0.2.2`, the app didn't (measured). Never break the real one to see an error. Ending **the campaign's own** session — signing it out, revoking its token through the API —
  is a fine way to get a "session ended" error: it touches nothing but the campaign. Another
  account's session, never.
- **A 401 is not a 403.** Code often sends "the session expired" down the same branch as "you may
  not do this", and a rejection handler written for the second then discards or locks what the user
  wrote. With a write waiting in the queue, answer **401** from the fake server, and check that the
  write survives, nothing turns read-only, and it goes up after signing in again. Measured: an expired
  session made notes read-only for good and threw away the text. Provoke 401s on the fake server
  only: repeated failed sign-ins against a real server trip its brute-force protection, and the
  computer's address got 429s (measured).
- **Side effects the clean-up can't undo.** Sharing or inviting can send an email or a push
  notification to a real person, create a public link, fire a webhook or cost money. List them in
  `CAMPAIGN.md` §4 before the first test that could trigger one; if one would reach someone outside
  the campaign, use addresses the human controls, or queue it.
- **The ones that need no action at all.** Before the first launch, grep every outbound channel the
  app has — chat and messaging APIs, webhooks, push, crash reporting, third-party SDKs — and ask what
  fires **on start**, on an error, or on a health check. A test device is not a real one, and what it
  is *missing* can be the trigger: an app that alerts a real chat when a companion app is absent did
  it on every cold start on the emulator (measured). Agree an off switch with the human before driving
  anything.

A backend nobody can query directly (a vendor sync service) changes the API oracle, not these rules:
`adapters/README.md`, "A backend you don't own".

**Put the marker where the server keeps it.** Servers rewrite what you send: a title replaced by the
page's own title, a name trimmed or lowercased — and the app may have no field for the title at all.
Create one fixture, read it back through the API, and check the prefix survived; if it didn't, move
it to a field the server stores as sent (a URL, a tag, a description). Record that field in
`CAMPAIGN.md` §4, because the clean-up searches it.

**The server also makes records of its own.** A `QA_` place with coordinates and a visit marked a
whole region "visited" for the account, and deleting the place didn't undo it (measured). A clean-up
that searches for `QA_` can't see that. Before each process, **note the account's counts** —
statistics, visited or derived lists — and compare them after the clean-up.

Know which of your product's destructive actions are **irreversible** — no trash, no undo, no
server-side copy — and say so in the plan; those are tested last, and only on fixtures.

### R11 — The agent never types credentials

Sessions are injected, never typed. The skill cannot ship this — every app stores its session its
own way — so the setup gate builds it. It is two questions.

**What the session is made of**, best first:

- **A token made with the server's own secret.** On a disposable server you run yourself (R10),
  where sign-in tokens are signed with a key you hold, make the token for account A, B or C
  directly. No password exists anywhere.
- **A token or app password the adapter gets once**, from credentials the human wrote into the
  gitignored `qa.credentials.json`; only the token is kept.
- **The password itself**, from that same file, when the app accepts nothing else.

**How it gets into the app**, in order of preference:

1. **A test that runs inside the app and writes the session** — an instrumentation test on a
   debuggable build writes to the app's secure storage exactly what the login would have written.
   Works for any Android app; ~50 lines. The test runs on the device and the credentials file is on
   the computer: put the value into the **test build** when it is built (generated into the build
   folder from the gitignored file, never into source), and uninstall the test app once the session
   is written. Never pass it with `am instrument -e` (a command line, visible to other processes
   and kept in shell history) and never `adb push` the file (a loose copy left on the device).
2. **Write the store directly** (`run-as` on a debuggable build) when the session lives in a plain
   preferences file or database.
3. **A debug-only launch argument** that accepts a token — app code, development builds only.
4. **Log in once by hand and snapshot the device** — the human signs in, the emulator or
   simulator is snapshotted logged-in, and every run starts from that snapshot. This is the answer
   for iCloud, two-factor and anything else with no programmatic path.
5. **The session belongs to another app** — a companion app hands it over (a ContentProvider, a
   launch intent with the user's id). Drive that route: the companion signed in by the human, or its
   launch extra with a **test** identifier (below). Writing the app's own store is no mechanism here.
   **Keep a simulated hand-off consistent with its source:** a launch extra saying "this driver" while
   the companion app reports nobody signed in is a state no user has, and the next cold start signs
   out by design (measured). Don't file what only that contradiction produces.

**Cold-start once before relying on an injected session.** An app that re-reads its session from
somewhere else on every start wipes an injected one before the first screen (measured: the app
cleared its stored session whenever the companion app reported nobody signed in).

Whatever the mechanism, `session.injectCommand` in `qa.config.json` names it, and a **real**
password is never typed, echoed, or passed on a command line by the agent.

**The credentials file feeds the scripts, never the login screen.** `qa.credentials.json` is how the
adapter signs in *through the API* — to ask the server what is true, and to get the session that is
injected into the app. The agent runs those scripts and never sees what they read. It does **not**
type a password from that file into the app, and won't even when the human asks: that refusal is the
agent's own rule, not only this skill's, so don't plan a step that needs it. **Session tokens count
as credentials too**: never on a command line (`curl -H "Authorization: Bearer …"` is readable by
other processes) — go through the adapter.

**Reading the store never prints a credential.** The place the session lives often holds a token or
an encrypted password next to ordinary settings. Select the columns you need, never `select *`, on
anything that holds a session. `ui.py db` and `ui.py file` hide secret-looking columns and keys; a
project-side reader (for a format the harness can't decode) must do the same. To check a logout,
assert the value is **empty**, not what it was.

**Before writing a session or testing logout, look at whose app it is.** The app may already be
installed on the test device holding someone's real account — logout wipes it, and an injected
session overwrites it. Check whether it is installed and signed in. If it may be a real account,
test a **separate build with its own app id** (a debug or staging variant: same code, its own data)
so the real install is never touched — or ask. **When no variant has its own id** (debug = release),
propose a QA build type with an `applicationIdSuffix` — it changes the build file, so ask first. If
the app needs another app's signature permission, that build may need the release key: then it must
never leave the test device, and the build file says so (measured on a work phone holding the
production app). Don't trust a note that says what is on the device;
look.

The rule protects real credentials, not the password field. **A test identifier the human declares
as test data** — a test account's NFC card, a test user number — is ordinary test input: it can go on
an adb command line (`am start … --es <extra> <id>`). Keep it in `qa.credentials.json`, and in docs and
commits call it by its role ("the test chip"), never by its value. Without that declaration, treat any
sign-in value as a real credential (measured: a campaign rightly refused to put a driver's card id on
a command line until the human said it was a test card). **Invented values against a disposable
or local test server** — a wrong password to test the error path, a fixture account the campaign
created — are ordinary test input: use them without asking. The **one real,
end-to-end login** is a user-queue item (R2): the human does it once, and it is the only part of
login that cannot be automated.

**After that real login, compare what it stored with what the injection writes — field by field**,
secrets hidden. Every field the injection sets that a real login doesn't, or sets differently, is a
place where a test on the injected session tests a state no user ever has. Measured: the injection
wrote an account `id` and `owner`, which the real login never stores, and a fix looked done on the
injected session only. Ask for the real login early — in the first queue round, before the shell
gate closes — and **don't wait for it**: keep driving on the injected session and close gates assuming
it (R1). When it comes, the comparison shapes the injection and reopens only what it contradicts.
Measured: a campaign stopped after setup to wait for that login, and the human, seeing nothing move,
took it for a hang.

**Switch accounts once without a process death.** Injection stops the app to write the store, so
every injected account switch is also a process death (R9), and whatever lives in memory after a
logout can never show up that way. Log out and sign in as the next account **by typing, in the same
process** — with invented credentials against a disposable or fake server (allowed above), or as the
human's queue item. Measured: two leftovers from the previous account appeared only on a switch
inside one process. Against a fake server, sign-in is not enough: **every screen the fake account
visits needs its routes answering empty**, not erroring — an error screen hides exactly the leftover
you are looking for. List the calls the shell and tabs make, route them, let the rest 404. When
neither a fake nor a disposable server can sign the next account in, **the in-process switch is the
human's queue item** — never claimed from injected switches, which are all cold starts. **A second
client** for "the same account in two places" is the API adapter, not the web: the web needs a
typed login the agent doesn't do.

### R12 — Report what happened, including your own mistakes

When you got it wrong, the report says so in the same voice it reports everything else:

> *"My first alignment check computed the zip offsets by hand and reported 0 of 20 aligned. **That
> was my mistake** — it didn't account for local header padding. The official tool says the file is
> fine."*

A campaign that never records an operator error is not being honest, and its other results are worth
less because of it. Equally: when a defect cannot be reproduced from the test harness, **rename the
test to say what it actually covers** instead of claiming coverage you don't have.

**And when the skill is what went wrong, log it too.** A rule that made you guess, an assumption that
isn't true in this project, a harness command that lied or was missing, an instruction that makes no
sense here: one line in `SKILL-FRICTION.md`, in the campaign's docs folder, **when it happens** — not
reconstructed at the end. Each line carries a tag — **GUESS**, **FALSE-ASSUMPTION**, **TOOL** or
**NONSENSE** — then where in the skill (`SKILL.md` R6, `ui.py tap`), what happened, and what you did
instead. The file's first line names the skill version the campaign started with (its commit, when
the skill is a git checkout). Don't edit the skill from inside a campaign; work around it in the
project and log the line. Most rules in this file after the first campaign came from lines like
these.

**At close-out, offer the log to the skill's maintainers** — as an issue on the skill's repository
(its `git remote` when the skill was installed from git; otherwise the one in its `README.md`).
Sending it is **publishing**: nothing goes out without the human's yes, asked every time.
1. Write `SKILL-FRICTION.public.md` next to the log, **without the project in it**: no paths, host
   names, addresses or URLs, no account or person names, no titles or content from the product's
   data, no file:line of the project's code. Keep the tag, where in the skill, what happened in general
   terms ("a list screen", "a sync queue", "the project's login script"), what you did instead, and the
   measured numbers. Name the kind of product and platform, and the skill version.
2. Show the human that text, and say where it would go.
3. On a yes, file it — `gh issue create --repo <skill repo> --title "Friction: <kind of product>,
   skill <version>" --body-file SKILL-FRICTION.public.md` — and put the issue's link in the close-out.
   No `gh`, no repository or a no: the public file stays in the docs folder for the human to send.

### R13 — Run the whole suite before closing a gate

Per-module test runs pass while the repository-wide build is broken — typically stale fakes in
*other* modules after an interface changed. Run the full suite at every gate, not at the end. **A fix
that changes wording** breaks every test that pinned the old words, in modules the fix never touched:
grep the test sources for the old string before running the suite, and update them in the same
change (measured).

A result restored from the build cache counts here: same inputs, same result, and the gate asks
whether the repository as it stands is green. Say it in the report — *"722 tests, 688 from cache"* —
because a cached pass is not the real run R6 needs for the tests the fix touched (measured: 688
results came back in 5 s without running).

Two ways the count lies, both measured: Gradle's `--rerun` applies to **the task just before it** —
`gradlew test --rerun` reran nothing that hadn't changed, so name the task
(`:data:testDebugUnitTest --rerun`) — and a report folder keeps XML from tasks the build no longer
runs, so summing every `TEST-*.xml` inflated three gates' totals. **Count only the reports this run
wrote**: their time is after the run started.

On a multi-module build most modules are up to date and write no report at all, so the honest count
has two parts — say it that way: *"405 tests ran this time; the other modules were up to date with
unchanged inputs (last green at `<commit>`)."* When a process changed no code, the honest line is
*"no code changed in this process, so no test ran; last green at `<commit>`"* — not "0 results",
which reads like a broken command. And **a task that never reached the device is not
green**: a module that failed with *"No compatible devices connected"* inside an otherwise green run,
with the device connected, ran nothing (measured). Run that module alone and report both runs.

### R14 — Every change to the local store ships with its migration, and the migration with a test

If the client persists anything, a released version has users with data in the **old** shape. A
schema change without a migration is data loss on upgrade; a migration without a test is a guess.
Test it against the real engine (a migration test helper, a fixture database at the old version),
and see it red (R6): drop the `ALTER` and watch the test fail. The release process then does the
thing the test only models: **install the previous release, create data, install the new build over
it**, and check STORE and API.

**"Once" means once per device, not once per version.** A one-time job — pushing local data into a
new store, a backfill, a re-registration — gated on "the version changed" runs again at **every**
upgrade, and the second run overwrote newer data with this device's stale copy (measured). Gate it on
"has never run here", and let its test upgrade **twice**: the second upgrade must do nothing.

**The version has to be above what users already have.** Before building the artefact, compare its
version number with the highest one **shipped from any branch** — a release branch was numbered below
what the maintenance branch had already published, and the in-place install died with
`INSTALL_FAILED_VERSION_DOWNGRADE` (measured). It costs one command, it doesn't need the human, and a
unit test pinning "above the last shipped" keeps it that way. While there, look on disk for an earlier
artefact to upgrade from before queueing the human for one.

Two more things that process needs, both found the hard way:

- **Signing.** An update only installs over an APK signed with the same key, and the published one is
  usually signed with a key that lives only in CI. Build the previous release **from its tag** with
  the same local key as the new build — its size matching the published APK is a cheap check that it
  is the same code (measured).
- **The human, again.** A release build isn't debuggable: no injected session and no STORE oracle.
  The one real login is needed once more, and every claim in that process rests on UI and API only —
  say so in its report. Put that login in the queue **when the release process is planned**, not
  when it is reached.

---

## 2. Running a campaign

### 2.1 Set up (once per project)

**Resuming a campaign that already exists?** When `CAMPAIGN.md` is already there, don't start setup
over — and don't skip it either. Read the plan, the process files and the queue; then check each
step below against what the plan records, **including steps the skill has added since the campaign
began** (compare with *Skill at start* in `CAMPAIGN.md`), and ask the missing ones **before** doing
any more work. Uncommitted changes left by the earlier run are step 2's question. Measured: a
resumed campaign got the setup questions after the fixes they were meant to shape.

**Unless that campaign is closed.** When its last gate closes, `CAMPAIGN.md` says `Status: closed`,
with the date and the commit. A closed campaign is not resumed: running the skill again starts a
**new** campaign, in a dated folder inside the same docs folder (`docs/qa/<date>/`), and the closed
one is earlier QA work for it (step 3).

**Look first, then ask once.** Good questions need facts, so setup starts by **looking without
touching**: which AVDs exist and which are already running (`ui.py avds`), whether the server
answers, what the manifest and the build files say, and **what QA work the repo already has** — test
plans, an earlier campaign's reports, QA scripts, a client for the server, test credentials kept in
some file (steps 3 and 6). "Before anything else" in step 1 means before *changing* anything, not
before looking.

Then the questions of steps 1, 3 and 5 go to the human **in one round of at most four** — question
tools take four, and a second round gets skipped:

1. **Fix mode** (step 1);
2. **Commits**, and where the campaign docs live (step 1);
3. **Devices** — propose one from what you saw, and name the ones that are busy or off-limits (step 5);
4. **Server and accounts** — which server, whether it holds real data, which account for each role
   (step 3). Test data defaults to *"only what the campaign creates, marked `QA_`, is touched"*;
   say so in the question, and the human corrects it only if something else must be protected.

1. **Ask two questions, once, before changing anything** — in the setup round above — and record
   the answers at the top of `CAMPAIGN.md`. Never ask them again per finding.

   **Fix mode**

   | Mode | What happens to a finding | When it fits |
   |---|---|---|
   | **Fix severe** *(default)* | P0 and P1 are fixed, with their test seen red (R6). P2s and anything that is a **product decision** (wording, whether to confirm, what to show) go to the user queue | your own product before a release |
   | **Fix all** | also fixes P2s — product decisions still go to the queue | polishing your own product |
   | **Report only** | nothing in the product is touched. Each finding is written up to §2.3 with exact reproduction steps, the oracles' evidence, file:line and the likely fix | code you don't own, a frozen release branch, an audit |

   **Commits, and where the work goes** — may the agent commit at each gate, or only leave the
   changes for the human to review? **On a branch of its own (`qa/<date>`) or on the branch that is
   checked out?** Ask; don't assume: a project forbade new branches as a standing rule (measured).
   Where do campaign docs live if `docs/` is not versioned in this repo? Notes kept
   only on this machine have **no backup** — say so when that is the answer.

   In the fix modes every fix ships with its regression test (R6, R7) — that is part of fixing, not
   an extra. *Report only* changes nothing in the repository's source: no fixes and **no test
   files**; the report names the test that would prove each fix instead. The harness, the adapter
   and the campaign docs are written in every mode.
2. **Start from a clean tree, on a campaign branch.** Run `git status` before touching anything.
   If there are uncommitted changes, **stop and ask** — commit them, stash them, or explicitly
   accept them as part of the baseline — because otherwise the campaign's diff mixes with
   someone's work in progress, a finding can come from a half-done change instead of the product,
   and reverting a fix to see its test red (R6) touches code that was never the campaign's. Then,
   set up the work where step 1's answer said — `qa/<date>` from the current commit unless the human
   asked to stay on the branch that is checked out — and record that commit as **Build at start** in
   `CAMPAIGN.md`. Every gate's diff is then that process and nothing else.
3. **Ask what already exists before building anything.** One question, four parts:
   - **devices** — which emulators, simulators or phones are for testing (step 5);
   - **a test server** — is there one already, at what address, and does it hold anyone's real
     data? (R10 says what to propose when there is none);
   - **test accounts** — which ones, and for which roles (R7);
   - **test data** — anything that must not be touched, and anything already prepared.

   Use what exists. Build, start or create only what is missing — and ask before doing it (R2,
   stop 3). The answers go at the top of `CAMPAIGN.md`: they are the "agreed ground" every later
   stop refers to.

   **QA work already in the repo** is found by looking, not asked, and it is a **baseline, not the
   plan**:
   - the inventory is still derived from the product (R3); the old one is a cross-check — a control
     it lists that you didn't find was either removed or missed;
   - defects it records as fixed are **re-checked, not re-reported**: still fixed, or a regression —
     and a regression is a finding;
   - scripts that work are reused once proven (R8): an existing client for the server becomes the
     adapter (step 8) instead of being written again;
   - nothing of it is overwritten or moved. The campaign's docs go in their own folder, and the
     earlier ones stay the record of that campaign;
   - **what changed since it closed** — the commits since its closing commit (or its date, when it
     recorded none), the server's and its apps' versions, the target OS — sets the **order**, not what
     is skipped: untouched screens still break through shared code and a changed server. Changed
     areas go first, and every finding says whether it comes **from a change** or was **missed
     last time**. The misses are what the earlier campaign could not see; the close-out names them;
   - **`QA_` records already on the server** are an earlier run's fixtures, not this campaign's.
     Count them per account **by owner** while looking, and say so in the setup round: a record
     shared with another account shows up in that account too, and cleaned from there it takes the
     share with it (measured: a cleanup would have deleted a read-only note B shared with A, counted
     as A's leftover). Clean a record up only from the account that owns it. Reuse them when the seed
     script finds and reuses existing ones; otherwise ask before cleaning them up (R10).
4. Copy `templates/CAMPAIGN.md` into the campaign's docs folder and fill in the process list. The
   other two templates are **models, not files to copy now**: each process writes **one file**,
   `NN-<area>.md` (`01-shell.md`, `02-bookmarks.md`), shaped like `templates/run-report.md`, with
   the process's inventory (`templates/inventory.md`) as its first section. Only an inventory too big
   to read inside the report gets its own `NN-<area>-inventory.md`. Never leave a blank template in
   the folder: it reads as a process that was never done.
5. **Pick devices before creating any.** List what exists — `ui.py avds` shows every AVD with its
   Android version and whether it is **already running**, read from the computer's processes
   without touching any emulator; `emulator -list-avds` and `adb devices` alone don't say which AVD
   is behind which running serial (measured: a campaign proposed an AVD as free that was another
   campaign's running emulator) — and **ask before creating or deleting a device**. Test first at the product's **target** OS
   version, and at its minimum only as a later, separate pass. **No image for the target installed?**
   Use the nearest installed one, write the difference down, and ask before downloading the right one
   (R2, stop 3). One resizable emulator can cover
   phone and tablet layouts. Any physical device attached that is not explicitly the test device is
   **off-limits** — list the test devices in `devices` and pass `--device` on every command. Once
   `devices` lists anything, the scripts **refuse any device that is not on the list**, so nothing
   lands on someone's personal or work phone by accident. List an emulator by its AVD —
   `"qa": "avd:Resizable_Experimental"` — not by its serial: `emulator-5554` is only *whichever
   emulator booted first*, so the same serial can name another campaign's emulator tomorrow
   (measured). Start emulators with `-port <even number>` so their serial can be found from the
   process list. A project-side script that talks to the device (a store reader, an injector) gets
   the serial from `ui.py serial <alias>` — `avd:…` is not a serial.
6. Copy `qa.config.example.json` to `qa.config.json`. The scripts read `android.*` and `devices`;
   the rest (`server`, `session`, `fixtures`, `app`) documents the plan. **Secrets never go in it**:
   the adapter reads a separate `qa.credentials.json` (its shape: `adapters/README.md`).

   **When you ask the human to fill in `qa.credentials.json`, say what it is for in the same
   message.** "The agent never types a password" next to "put the password in this file" reads as a
   contradiction — measured twice, in two projects. One sentence settles it: *the scripts read it to
   sign in through the API, check the server and inject the session into the app; I never see the
   password and never type it into the login screen — the one typed login is yours.*

   **Test credentials already kept in another file** (`e2e.properties`, `.env.test`)? When the
   project's own scripts — an adapter, an injection test — already read it, **use it as it is** and
   name it as the source in `CAMPAIGN.md`: a second copy that nothing reads is one more place for the
   passwords to leak from (measured). Only for scripts written now, and never by asking the human to
   copy them: generate `qa.credentials.json` from that file with a short script that writes
   the values without printing them and reports only the keys it filled. Leave the original where it
   is — whatever reads it still does — and record it as the source in `CAMPAIGN.md`, so a changed
   password is regenerated rather than debugged.

   **No credentials anywhere?** Create the file for the human to fill in: add it to `.gitignore`
   first (step 7), then write it with mode `600` and **empty values**, in the shape this server signs
   in with, for the accounts agreed in step 3 — `{"accounts": {"A": {"username": "", "password":
   ""}}}`. Give its path and say what goes in each field. When the human says it is filled in, check
   that no value is empty, naming keys only.
7. Add both to the project's `.gitignore` — the skill's own `.gitignore` does not apply to your
   repo: `printf 'qa.config.json\nqa.credentials.json\nqa-shots/\n' >> .gitignore`.
8. Write the **API adapter** for the test server agreed in step 3 (see `adapters/README.md`). This
   is the only part the skill cannot give you: it's how the campaign asks the server what is true.
   Then check that **the app on the device reaches that same server** — `net.sh reach` (§3) — before
   setup closes: the computer reaching it says nothing about the device. Measured: setup closed with
   "the harness drives the app" while the app could not resolve the server's name, and it surfaced a
   gate later as "deleted notes that don't disappear".
9. Run the four absence sweeps (R4) once, for the whole product, and file each finding under its
   module — before writing any catalogue.
10. **Decide how deep offline goes** — none, short or full (R1) — from the clues in the code, and
    write it at the top of `CAMPAIGN.md` with the clue that decided it. It sets whether the
    campaign has an offline gate at all.

### 2.2 Per process

1. **Inventory** the controls and entry points of the area under test (R3) — the first section of
   the process's file, `NN-<area>.md` (§2.1 step 4), in the shape of `templates/inventory.md`.
2. Drive them with the harness, asserting against the oracles (R5). **For every edit form, once:
   change the record elsewhere first** — through the API, or the web client — **then save from the
   app**, and check the other change is still there (or that the app says it conflicts). Forms that
   save through **one code path** share one check — show the shared path in the report instead of five
   round trips through the UI. It is
   cheap with the API oracle already built, and it found a lost update on an app with no sync at all:
   the form saved the list's stale copy over a change made a minute earlier (measured).
3. For each finding the **fix mode** covers: fix it, write the regression test, **see it red**
   (R6), add its negative pair where the test asserts an absence (R7). Everything else: write it up
   (§2.3) and queue it. Stop only for what R2 lists.
4. Run the whole suite (R13).
5. Verify each fix **in the running system**, not only in the test — and first prove the running
   system **is the build with the fix**. A failed build stops here: never install whatever the last
   successful build left behind, and **never hide the build's exit code**: a build piped through
   `grep` to shorten its output looked fine, the install pushed the previous APK, and the run that
   followed damaged data (measured). Install only when the build command itself exited 0. Measured
   again elsewhere: a build failed, the install pushed the previous APK, and old code on the device
   read as "the fix does not work". On Android, `ui.py installed --apk <file>`
   refuses unless the installed app is that exact file. Then drive it **in the exact state the finding
   was measured in** — the same data, an empty account if it was empty — and **the way the user gets
   there**: a gesture, not the function behind it. A fix went green in its test, which called
   `refresh()` directly, and failed on the device, where an empty list passed no drag to
   pull-to-refresh at all (measured). A test proves the function; only the device proves the path.
6. **Open the screenshot of every screen you are about to call verified**, and write down what you
   see — cut off, overlapping, crowded, unlabeled, or fine — in the report's EYE table (R5).
7. Finish that same file as the run report, in the shape of `templates/run-report.md`, with the
   finding table, and link it from the log in `CAMPAIGN.md`.
8. Clean up fixtures (R10) and verify through the API.
9. Commit if the setup answer allows it; otherwise say what is left uncommitted. Then, and only
   then, the next process — and when the campaign stops here, `ui.py release`, so a campaign taking
   turns on the same device isn't refused.

### 2.3 What a finding looks like

Every finding gets an id, a severity, **what actually happens** (not what's wrong in the code), the
file:line, and its status. Severity, the same everywhere in the campaign:

| | |
|---|---|
| **P0** | data loss, **a security hole** — a password, a session token or private data readable by someone or something that shouldn't have it (another app, a backup, a log) — or a state the user cannot recover from |
| **P1** | the user is lied to (told "saved" when it wasn't), or blocked with no workaround |
| **P2** | a workaround exists, or it is cosmetic. Harness `a11y` warnings (small target, unnamed icon) are P2 unless they block a flow. Hardening that exposes nothing by itself (a too-wide file-sharing path, a session not revoked on the server) is P2 |

**A secret in the system log** is **P0** when anyone but the developer collects logs from the devices
users have — a company's device management, bug-report or crash tools — and **P1** otherwise: on a
plain phone the log needs adb or a privileged app. Say which case applies and why.

**Rate for the builds users get** — and **ask at setup which build that is**: a store release, a
flavor, or, in a managed fleet, the **debug** build pushed by the device manager (measured: an app
whose trucks run the debug build, where "debug-only" protects nobody). Then check whether the screen
or path exists in *that* build (`BuildConfig.DEBUG`, the flavor, a debug-only menu) before calling
anything P0: a leak visible only in a build nobody receives is a finding for that build, not a P0 for
users.

The "what" is written so that someone who has never seen the code understands the consequence:

> **P1 — "Note updated" over an edit the server refused.** A note shared read-only answers the PUT
> with **412**, not 403, so it fell into the conflict branch: the row was correctly reverted, but
> `updateNote` still returned success. The editor closed, the user read "Note updated", and the
> screen was left showing the rejected text as if it were the note.

If you can't write that sentence, you haven't understood the defect yet.

---

## 3. The harness

The rules above are platform-independent. A **harness** is what makes them executable on one
platform, and it has to provide exactly seven things — enumerate the screen as text, act on it, read
the local store, screenshot, cut the network, force a UI recreation, and read crashes.
[`harness/README.md`](harness/README.md) is that contract: the seven capabilities, the command each
maps to, and what other platforms' equivalents are.

`harness/android/` is the **reference implementation** — used on a real release and proven against
a second, unrelated app. For any other platform you write the seven capabilities behind the same
command names; nothing above this line changes.

`ui.py` drives an Android device or emulator over `adb`, reading the accessibility tree rather than
pixels — it is text, it can be asserted on, and it is cheap.

```bash
ui.py --device phone dump               # device by alias from qa.config.json (or --serial / ANDROID_SERIAL)
ui.py tap "text=Add item"               # selectors: text= text~= desc= desc~= id= id~= class= class~=
                                        #            clickable= scrollable= enabled= checked= selected=  · --index N
                                        # warns when the selector hits several different controls
ui.py tap "text=Save" --expect "text=Edit item"   # only if that screen is showing; stops otherwise
ui.py tap "desc=Delete" --in "text=QA_Item1"     # the Delete of THAT item — refuses if it can't be sure
ui.py installed --apk <file>            # version, install time, and whether the device runs that exact file
ui.py avds                              # every AVD, its version and size, which are running and which are in use — touches no device
ui.py serial <alias>                    # the adb serial an alias means right now, for project-side scripts
ui.py release                           # free the device for another campaign when this one stops
ui.py wait "text~=Saved" --timeout 10   # gate on something appearing (or --gone); it doesn't scroll
ui.py watch 6 --until "text~=expired"   # every label that shows for 6 s — snackbars last ~2 s, a dump ~1.5
ui.py state "text=Public"               # ON/off of the switch beside that label
ui.py assert "text=Delete" --absent     # exit 1 if wrong — what a script gates on
ui.py type "QA_Item1"
ui.py hide-keyboard                     # BACK only if the keyboard is up; fails if the screen went with it
ui.py scroll-to "text=QA_Item1"
ui.py rotate 1                          # reads the rotation back from the window manager (R9)
ui.py size tablet                       # a resizable emulator becomes phone | unfolded | tablet — read back too
ui.py kill                              # process death that KEEPS saved state (R9); `stop` discards it
ui.py open "myapp://item/42"            # a deep link — an entry point the inventory must include (R3)
ui.py a11y                              # touch targets, overlaps, unnamed icons, off-screen
ui.py db <alias> "select ..."           # the app's own database, pulled with its -wal; secrets hidden
ui.py files                             # every file the app keeps — find where its stores really are
ui.py file <alias> [--out f]            # settings files and other stores; text printed with secrets hidden
ui.py shot <name> --dir qa-shots
ui.py crashes                           # crashes/ANRs OF THE APP (not of the harness — R8)
ui.py demo on                           # frozen status bar, so two screenshots are comparable
ui.py log --grep login                  # the running app's log, secrets hidden; never `adb logcat -c`
```

`harness/net.sh on|off|status` toggles airplane mode and **waits until the change is real**: `off`
until no validated network remains, `on` until one is validated again. `net.sh reach` checks that
the **device** can open a connection to the test server — a validated network only means internet,
and the computer reaching the server says nothing about the device. When it can't, try **another
address for the same server** first — a VPN or Tailscale name the device already resolves — before
building a relay. Measured: an emulator got "No route to host" on the server's LAN address and
reached it at once by its Tailscale name; the relay built the first time was never needed. **A name
the computer resolves and the emulator doesn't** is usually DNS: an emulator takes the computer's
first DNS server when it boots, and with another VPN in front of it, the VPN's names stop resolving
on the device (measured with Tailscale). Boot it with `-dns-server <that VPN's resolver>` —
`100.100.100.100` for Tailscale.

Every command first checks that a device answers and refuses with adb's own message if not. Nothing
project-specific is in the scripts: package, database aliases and device aliases come from
`qa.config.json`. Pointing the harness at a different app is one config file.

### Gotchas that cost a session each

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
- On Android, `connectedAndroidTest` **uninstalls the app afterwards**, taking the injected session
  with it. Install the APKs and run `am instrument` directly instead.
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
  `build/outputs/androidTest-results`, which `redcheck.py` also reads.
- **`ui.py kill` checks that the process really died.** `am kill` once left it alive on API 37.1
  (same pid before and after) while saying it had killed it, and two process-death checks proved
  nothing (measured). `kill` now reads the pid after, finishes a debuggable app with `kill -9`, and
  refuses when it is still alive.

---

## 4. What this does not do

- It does not replace unit tests. It finds the defects unit tests were never pointed at.
- It does not run unattended. The judgement calls — is this a defect or my tool lying? — are the
  work.
- It does not know your product. Oracles come from your backend and your reference implementation;
  the skill knows *that* you need them, not *what* they say.
- It ships one harness. The Android one is done; any other platform is a harness that implements
  the seven-capability contract in `harness/README.md` — a real piece of work, not a shim.

**Blind spots, by design.** This process is strong on state, sync, permissions and dead controls —
things a driver can provoke and an oracle can confirm. It does **not** cover: performance under
load; concurrency beyond what surfaces as a sync conflict; **time** — token and session expiry,
scheduled sync while backgrounded or killed, date rollover; localisation, RTL and non-ASCII data;
accessibility beyond touch targets and names (screen-reader flow, contrast); security beyond
authorisation. Each of those needs its own method. Knowing that is the point of R4 applied to the
process itself.
