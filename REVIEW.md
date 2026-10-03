# Review — qa-campaign

Branch `review/fable-pass`, from `a1ee970`. Phases 1–3 done (map, promises vs code, harness
correctness). Phases 4–6 not started. Nothing pushed.

`./tests/run`: **51 tests, OK, 27.8 s** before · **71 tests, OK, 34.8 s** after (Python 3.14.8, bash
3.2.57, macOS; the harness sources also parse on the system Python 3.9.6). No device was used: every
claim below about device behaviour comes from the code and the stub.

## (a) Fixed

Each regression test was seen failing before its fix, on its own assertion.

| # | What was wrong | Seen red as | Commit |
|---|---|---|---|
| 1 | **`ui.py`: the `packagePrefix` list was ignored by the input guard, the BACK check and the crash filter.** The config documents the list as "count several variants as one app", but those three compared with `android.package` alone. With the listed debug variant in front, input was refused; worse, its crash came out as `0 crashes`, exit 0 — a silent all-clear. | `refusing input: com.example.app.debug is in front` · `1 != 0 : 0 crashes` | `80a8a25` |
| 2 | **`net.sh`: a `$ADB` that is not a file fell through to the adb on PATH.** `ui.py` refuses this case on purpose; `net.sh` did not. | exit 0, the PATH adb was asked | `e43dc33` |
| 3 | **`net.sh on`: `${ANDROID_SERIAL#emulator-}` on an unset variable under `set -u`.** As I read the bash manual, bash 4+ stops there with "unbound variable" instead of the "network not validated" message. **Not seen red and not confirmed:** bash 3.2 (the only bash here) tolerates it, so the test was removed and this one-token change has no test. | — | `e43dc33` |
| 4 | **`redcheck.py`: a report timestamp with no zone was read as local time.** Gradle up to 8.x writes GMT with no marker (Ant's `DateUtils`; checked in Gradle's source at v7.6.0 and v8.5.0 — current Gradle writes `…Z`). East of Greenwich a report written seconds ago looked hours old, was "ignored", and a real red came back NOT RUN. Now stale means stale under both readings. **Trade-off:** for zone-less timestamps the stale check is weaker by the UTC offset. | `ignored … the report says it ran at 13:43:38, before this run started` → NOT RUN | `34c9335` |
| 5 | **`redcheck.py`: `--break` on one file spelled two ways** (`Repo.kt`, `./Repo.kt`) kept the already-broken text as the second "original", wrote it back, and crashed in the restore. Keyed by real path now. | `FileNotFoundError` in `restore`, exit 1 | `34c9335` |
| 6 | **`redcheck.py`: a timeout killed only the command, not what it started.** A child kept running and could write a report after the break was undone. The run now gets its own session and the whole tree is stopped (also on Ctrl-C / SIGTERM). | `the command's own child was still running after the timeout` | `34c9335` |
| 7 | `redcheck.py --help`: `--test` said "contains" (it is an identity match); `--reports` omitted `androidTest-results`. | — (help text) | `34c9335` |
| 8 | **`fake_server.py`: a credential in the query string was printed** (`?api_key=…`). README says the harness hides secrets "everywhere it prints". | secret found in the request log | `3e262d1` |
| 9 | **`fake_server.py`: the body was cut to 300 bytes before hiding**, so an object under a secret key never closed and its contents printed. | `"user": "4321"` in the log | `3e262d1` |
| 10 | **`fake_server.py`: `--header` with no colon** started fine and then dropped every connection (the app sees a network failure, not the status asked for). Refused at start now. | the server started | `3e262d1` |
| 11 | Doc drifts: README test count (51 → 71); `tests/README` "a couple of seconds" (it is ~35 s); `templates/inventory.md` pointed permissions at R4 (the rule is in R5); `templates/CAMPAIGN.md` had no slot for "which build users get" (asked in §2.1, rated by in §2.3); SKILL.md §2.1 step 7 "both" for three entries; `qa.config.example.json` said `db` refuses any unlisted alias (it also takes a path); `ui.py` docstring omitted `secretKeys`, `managedDevices`, `campaign`. | — (docs) | `f98b139`, `80a8a25` |

**New tests for paths nothing covered** (`2e131e5`). No bug found in them; each was seen red by one
deliberate break in the harness, then the break was put back:

| Test | The break that turned it red |
|---|---|
| a managed device is not rotated | `"rotate"` out of `DEVICE_CHANGING` |
| a device another campaign is driving is refused until released | `LOCK_STALE_S = 0` |
| text the device would drop is refused, not typed | non-ASCII check → `if False` |
| `--in` takes the control of the item it names | `find_in` ignores the anchor |
| `assert` exits 1 when wrong, in either direction | `if present == a.absent` → `if False` |
| `find` with no match is not exit 0 | `raise` → `print` |
| `db` hides a secret column | `secret = [False …]` |
| `db` hides the value of a row whose key is secret | `row_secret[i] = False` |
| a binary store is never printed | control-character check → `if False` |
| `net.sh` refuses an unknown `--device` alias | `|| exit 1` → `|| true` |

Also in `80a8a25`: a control test for the other direction of fix 1 (another app's crash is still not
the app's).

## (b) Proposals — ranked, none applied

1. **`ui.py type` probably types stray backslashes — unproven, needs one device check.** It
   backslash-escapes `\ " ' $ & | ; < > ( ) * ? ! # ~` and the backtick, *then* wraps the result in
   `shlex.quote`. Inside single quotes the device's shell keeps backslashes literally, and `input text`
   only interprets `%s`, so `type "a&b (1)"` should arrive as `a\&b (\1\)`. Fixtures like `QA_Note1`
   never hit it. Check: `ui.py type "a&b (1) it's"` into any field. If confirmed, drop the backslash
   step and keep `%s` + `shlex.quote`. I did not change it because I could not see it on a device.

2. **`ui.py db` can print a secret column under an implicit alias.** The guard refuses
   `select password as p`, but `select password p from users`, a subquery or a CTE rename the column
   with no `as`, and the result prints unhidden. A fix that does not depend on parsing SQL: an sqlite
   authorizer that records which columns are read, and hides or refuses when a secret-looking one is
   read under another name. It changes how `db` decides, so it is your call.

3. **Refusals that are still Python tracebacks.** R8 says a traceback reads like a harness bug. Left:
   `require_device` when adb does not answer in 20 s; `fake_server.py` on a port in use, a routes file
   that is not JSON, or a route that is not an object; `net.sh` on a `qa.config.json` that is not valid
   JSON; `redcheck.py` when the command does not exist. Each is a few lines; together they are a
   behaviour pass over four scripts, so I listed them.

4. **`redcheck.py` says NOT RUN when *any* task came FROM-CACHE**, including a compile task while the
   test task itself ran and wrote a fresh report. It errs on the safe side and the message says what to
   add (`--no-build-cache`), but it is a false NOT RUN. Narrowing it to the test task needs a rule for
   which task that is.

5. **`net.sh` interpolates the configured host, port and path into a device shell command unquoted.**
   The values come from the project's own `qa.config.json`, so the risk is a typo, not an attacker; a
   character check on the host (as the path already has) would close it.

6. **`net.sh` asks for a device and claims it before printing usage.** `net.sh --help` with no device
   says "no device reachable". Moving the usage case up is harmless, but it reorders the script.

7. **`redcheck.py`: a report file with only crashes counts as "green"** in the "two report files
   disagree" message (`not f and t > s`). The verdict is still NOT RUN; only the wording is wrong.

8. **README's `qa.credentials.json` example has `server.url` inside it**; `adapters/README.md` gives
   the shape without it, and the server address lives in `qa.config.json`. One of the two should move
   (phase 5).

9. **SKILL.md §3 lists `state` among "what a script gates on"**, but it exits 0 for both ON and off —
   only a missing switch is exit 1. Either the doc or an `--expect on|off` flag (phase 4).

10. **Still no test:** `rotate`/`size` read-back, `kill`, `hide-keyboard`, `installed --apk`, `shot`
    on a second display, `reach` over https, `slow`/`full` succeeding, `a11y`'s clipped-vs-small rule.
    The stub needs more state for these (a rotation that changes, a pid that dies).

## (c) Verified OK

- **SKILL.md → files:** every path it names exists (`templates/` ×3, `references/setup-notes.md`, `adapters/README.md`, `harness/README.md`, `harness/android/GOTCHAS.md`, `qa.config.example.json`); section cross-references (§2.1 steps, §2.2, §2.3, `CAMPAIGN.md` §4/§5/§6) point where they say.
- **SKILL.md / harness README → `ui.py` commands:** all 34 subcommands and the flags the docs name (`--expect`, `--in`, `--index`, `--any`, `--any-app`, `--absent`, `--gone`, `--until`, `--apk`, `--out`, `--grep`, `--force`, `--allow-device-change`) exist and behave as described.
- **Config keys:** the scripts read exactly what the docs say — `android.package/packagePrefix/databases/files/secretKeys`, `devices`, `managedDevices`, `campaign`, plus `server.url/urlFromDevice` in `net.sh`; the rest is documentation, as stated.
- **`redcheck.py` promises in R6:** RED / GREEN / NOT RUN, `--break` byte-for-byte restore, whitespace-only break refused, MUTATION NOT VALIDATED, `--reports`, two files disagreeing = NOT RUN, exit codes 0/1/2/3.
- **`fake_server.py` promises:** status, body, type, delay, routes, repeated headers, HEAD without body, no DNS lookup on bind.
- **`net.sh` promises:** on/off wait and read back, `reach` goes DNS → TCP → HTTP, NOT PROVEN when `run-as` resolves nothing, offline proved from the app's side, exit codes 1/2.
- **Friction issue #13 (Shiori):** both lines are fixed in the code and have a test (`reach` control host; Mockito verification = the test's own check).
- **Portability:** `net.sh` runs on bash 3.2 (no bash-4 syntax); `ps -ax -o command` is not truncated on macOS, with or without a tty or `COLUMNS`; Python sources parse on 3.9. Linux and bash 5 were not run.
- **Links:** every relative link in README, SKILL.md, the harness/adapters/tests READMEs and `examples/shiori/` resolves (checked by script; the one miss is `templates/CAMPAIGN.md` → `00-setup.md`, a placeholder for the campaign's own folder).
- **`examples/shiori/`:** read in full, not edited (published "as it came out").
