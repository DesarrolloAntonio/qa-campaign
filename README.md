# qa-campaign

A Claude Code skill for running a **pre-release QA campaign** on a product you can drive from the
command line — and, more importantly, a set of rules that stop the campaign from lying to you.

It was used on one production release: a dozen gated processes, **79 defects found, 77 fixed** (the
other two were product decisions). Every fix was verified in the running app; most carry a
regression test that was watched fail before it was trusted, and the ones that don't say so.

## What it actually gives you

The scripts are the cheap half. The valuable half is in [`SKILL.md`](SKILL.md) — fourteen rules,
each of which earned its place on a real campaign:

- **Gates, not a checklist.** A flat list of N scenarios × M devices is never executed; a short list
  of gates with a hard stop at each one is.
- **Inventory before catalogue** — and then the **absence sweeps**, because deriving tests from the
  code enumerates what the app *has* and is structurally blind to what it *lacks*. That is where the
  dead "Privacy Policy" button and the settings screen that never names your server come from.
- **Never one oracle.** The screen, the client's own store, the server, and a reference
  implementation — and a rule for what to do when they disagree. The interesting defects live in the
  gap between two of them: an optimistic UI reporting success for a write the server refused is
  invisible to any single one.
- **Seen red, always.** A regression test does not exist until you have watched it fail.
- **The harness is under test too.** When your tool reports a defect, its first suspect is itself —
  a false positive costs more than a miss, because it trains you to ignore the tool. And it must
  never print a silent all-clear.

## Before you run it

A campaign is not a read-only audit. It **installs and drives builds on real devices**, **signs in and
writes to a server**, **changes your source** (fixes, tests, and deliberate breaks it undoes after),
and **deletes the test data it created**. It asks before leaving the ground agreed at setup — that is
R2 — but the ground is what you tell it, and an agent can still get it wrong.

So, every time:

- **on a branch of its own**, with a clean tree before it starts (it will ask; say yes to the branch);
- **a test server and test accounts**, never a personal or production account. No disposable server?
  R10 says what to do instead — and say out loud which data must not be touched;
- **the devices you name and no others**: list them in `qa.config.json` and the scripts refuse the
  rest, so nothing lands on a work or personal phone;
- **a backup of anything you could not lose**, on the server as well as the device.

It is a tool that acts. **You run it at your own risk** — see the licence: no warranty of any kind.

## Install

```bash
git clone https://github.com/DesarrolloAntonio/qa-campaign ~/.claude/skills/qa-campaign
```

Then, in the project you want to test:

```bash
cp ~/.claude/skills/qa-campaign/qa.config.example.json qa.config.json
printf 'qa.config.json\nqa.credentials.json\nqa-shots/\n' >> .gitignore
```

Setup writes the campaign's own `CAMPAIGN.md` — don't pre-copy the template: a blank one in the docs
folder reads as a campaign that was never finished.

Fill in `qa.config.json` (the scripts read `android.*`, `devices`, `managedDevices` and `campaign`; the rest documents the plan),
write your backend adapter ([`adapters/README.md`](adapters/README.md)) with its credentials in
`qa.credentials.json`, and ask Claude to run the campaign.

## Any project, not just mobile

The fourteen rules are about method: nothing in them is Android, or mobile, or even a GUI. What is
platform-specific is the **harness**, and that is seven capabilities behind a documented contract
([`harness/README.md`](harness/README.md)) — enumerate the screen as text, act, read the local
store, screenshot, cut the network, force a UI recreation, read crashes.

`harness/android/` implements them. Web, iOS and desktop each need a harness written to that
contract — a real piece of work, and the most useful PR this repo can get.

Pointing the Android harness at a different app is **one config file** — verified by driving a
second, unrelated app on the same emulator with nothing but a different `qa.config.json`.

## If an agent already drives your phone

Tools such as Google's [ARTEMIS](https://github.com/google/artemis) let an AI assistant use a real
Android device like a person: read the screen, tap, type, recover when a target moves. That is the
**hands** — the "enumerate", "act" and "screenshot" capabilities of the harness contract, done
better than `ui.py` does them.

This skill is the **method on top**, and none of it comes with the hands:

- **what to test** — the inventory of controls and entry points (R3), and the sweeps for what the
  product is *missing* (R4);
- **how to know it worked** — the device's screen is one oracle; the client's own store and the
  server are the others (R5). The defects that matter most — an edit the server refused while the
  screen said "saved", a record deleted by a sync — are invisible to anything that only looks at
  the screen;
- **what a fix must leave behind** — a regression test seen red for the right reason, with its
  negative pair (R6, R7);
- **what must not happen along the way** — destructive tests only on the campaign's own data (R10),
  no real password typed (R11), a single queue for the human (R2), gates that reopen (R1).

The two combine: let the agent do the driving, and keep the harness for what it doesn't cover —
reading the store, cutting the network, forcing a UI recreation, reading crashes. *(Not tried yet:
no campaign has run with ARTEMIS as its hands.)*

## The harness

`harness/android/ui.py` drives an Android device over `adb`, reading the accessibility tree rather
than pixels — it is text, it can be asserted on, and it is cheap.

```bash
ui.py --device phone tap "text=Add card"   # selectors: text= text~= desc= desc~= id= id~= class= class~=
                                           #            clickable= scrollable= enabled= checked= selected=
ui.py a11y                                 # small targets, overlaps, off-screen, unnamed icons
ui.py db main "select id, title, syncStatus from items"
ui.py rotate 1                             # and reads the rotation back from the window manager
ui.py kill                                 # process death that keeps saved state
ui.py crashes                              # the APP's crashes, not the harness's
```

`harness/net.sh on|off` toggles airplane mode and waits until the change is real in both directions.

Every command refuses, with adb's own message, when no device answers. Everything project-specific
lives in `qa.config.json`; there is nothing to edit in the scripts.

## Status

Extracted from a production campaign and generalised; then reviewed adversarially (60 findings
against the first version, all fixed or recorded). The Android harness is used daily and proven
against a second, unrelated app; the process applies to anything you can drive and query.
Issues and PRs welcome — most useful of all would be `harness/web/` or `harness/ios/`.

Issues: <https://github.com/DesarrolloAntonio/qa-campaign/issues> — two templates, *Friction log
from a campaign* and *A harness bug, or an idea*.

**Friction logs are the best issue you can send.** Every campaign keeps `SKILL-FRICTION.md`: each
place where the skill made the agent guess, assumed something untrue, or where a harness command
lied or was missing. At close-out the agent offers to file it here as an issue, with the project's
names, addresses and data taken out, and only after you have read it and said yes. Most of this
skill's rules came from those lines.

## Licence

MIT — and, in plain words: **no warranty**. It comes as it is; what it does to your code, your
devices, your server and your data is your responsibility.
