#!/usr/bin/env python3
"""Seen red, for real (SKILL.md R6): run one test command and say RED, GREEN or NOT RUN — from the
reports THIS run wrote, never from what was already on disk.

    redcheck.py --expect red   --test PaneBackStackTest -- ./gradlew :feature:ui:testDebugUnitTest --tests '*PaneBackStackTest' --rerun --no-build-cache
    redcheck.py --expect green --test PaneBackStackTest -- ./gradlew :feature:ui:testDebugUnitTest --tests '*PaneBackStackTest' --rerun --no-build-cache

    redcheck.py --expect red --test PaneBackStackTest \
        --break feature/ui/src/commonMain/kotlin/PaneBackStack.kt 'if (popped) return' 'if (false) return' \
        -- ./gradlew :feature:ui:testDebugUnitTest --tests '*PaneBackStackTest' --rerun --no-build-cache

Exit 0 when the result is the one you expected, 1 when it is the other colour, 2 when the test did not
run at all (a build failure, a timeout, only skipped tests, no report newer than the run, or a `--test`
that named more than one class), 3 when a `--break` could not be put back (the message says where the
original is).

`--test` is an identity, not a search: it matches the class, its last segment, or `Class.method`, and
every report file it was counted from is printed. Two different classes answering to it is a NOT RUN,
because the colour would be a mix of both.

`--break FILE OLD NEW` makes the break for this run and undoes it afterwards: OLD must appear exactly
once in FILE, and the file is written back byte for byte and checked — after this script's own
`--timeout`, after Ctrl-C, and after a SIGTERM or SIGHUP. A copy of every original is written **before
the first byte changes** and its path is printed, so even a kill no handler survives (SIGKILL, or the
tool that launched this one timing out) leaves the original somewhere. Give the caller a timeout above
`--timeout`, or run this in the background: whoever kills this process wins. Repeat it for a break that spans several places. Breaking and restoring by hand is where it goes
wrong: a shell loop that didn't split its file list left four files broken after a correct red, and
only a failed `cp` gave it away (measured).

Why it exists: a break that did not compile left the previous run's report on disk, and only its
unchanged time showed the "red" was never run (measured); a break re-applied after a restore came back
UP-TO-DATE twice in a row. Reading the report by hand is care; this makes it a rule.

Reports: JUnit XML (Gradle, Maven, most runners) under --reports (default: every `test-results` folder
below the working directory, and every `outputs/androidTest-results`, where tests on a device write
theirs). Only report files the command created or changed count.
"""
import argparse
import glob
import hashlib
import re
import os
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def keep_path(path):
    return os.path.join(tempfile.gettempdir(),
                        "redcheck-" + hashlib.sha256(os.path.abspath(path).encode()).hexdigest()[:12]
                        + "-" + os.path.basename(path))


def apply_breaks(breaks):
    """Apply every --break; return {path: original bytes}. Refuses — putting back what it already
    changed — unless each OLD is found exactly once.

    The copy of each original is written BEFORE anything changes: no handler runs on SIGKILL, and the
    tool that launched this one can time out and kill it — SIGTERM and SIGHUP left the source broken
    with no copy anywhere (measured).
    """
    originals = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(2))
    for path, _, _ in breaks or []:
        if os.path.exists(keep_path(path)):
            print(f"note: a copy of {path} from an earlier run is still at {keep_path(path)} — a break may "
                  "have been left in place; compare them before trusting this run.", file=sys.stderr)
    try:
        for path, old, new in breaks or []:
            if old == new:
                refuse(f"--break {path}: OLD and NEW are the same — that breaks nothing")
            if not os.path.isfile(path):
                refuse(f"--break {path}: no such file")
            data = open(path, "rb").read()
            n = data.count(old.encode())
            if n != 1:
                refuse(f"--break {path}: OLD appears {n} times, not once — make it unique")
            if path not in originals:
                originals[path] = data
                with open(keep_path(path), "wb") as fh:
                    fh.write(data)
                print(f"break: {path} — original kept at {keep_path(path)}", file=sys.stderr)
            with open(path, "wb") as fh:
                fh.write(data.replace(old.encode(), new.encode(), 1))
    except BaseException:
        restore(originals)
        raise
    return originals


def refuse(message):
    """Nothing ran: exit 2, like any other NOT RUN — 1 means "the other colour"."""
    print(f"NOT RUN: {message}", file=sys.stderr)
    raise SystemExit(2)


def restore(originals):
    """Write every broken file back and check it is byte for byte the original. A copy of each
    original is kept in the temp folder until that check passes."""
    failed = []
    for path, data in originals.items():
        keep = keep_path(path)
        try:
            with open(path, "wb") as fh:
                fh.write(data)
            ok = open(path, "rb").read() == data
        except OSError:
            ok = False
        if ok:
            os.remove(keep)
        else:
            failed.append(f"{path} (original kept at {keep})")
    if failed:
        print("BREAK NOT UNDONE — put these back before anything else: " + "; ".join(failed), file=sys.stderr)
        raise SystemExit(3)
    if originals:
        print(f"break undone: {len(originals)} file(s) back byte for byte")


def default_roots():
    """Where JUnit XML lands below here: `test-results` for tests on the JVM, and
    `outputs/androidTest-results` for connectedAndroidTest, which does not write under test-results
    (measured: a campaign had to pass that folder by hand)."""
    found = glob.glob("**/test-results/*", recursive=True) + glob.glob("**/outputs/androidTest-results/*", recursive=True)
    return sorted({os.path.dirname(d) for d in found}) or ["."]


def snapshot(roots):
    """Every report file and its (mtime, size) before the run."""
    seen = {}
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*.xml"), recursive=True):
            st = os.stat(path)
            seen[path] = (st.st_mtime_ns, st.st_size)
    return seen


ASSERTION_TYPES = ("assertionerror", "assertionfailederror", "comparisonfailure", "assertionfailure",
                   "multiplefailureserror", "opentest4j")


def is_assertion(kind):
    """Did the test's own check fail, or did something blow up before it? (R6)"""
    last = (kind or "").rsplit(".", 1)[-1].lower()
    return any(t in last for t in ASSERTION_TYPES)


def matches_filter(classname, name, name_filter):
    """`--test Foo` means the class Foo, its last segment, or Foo.method — not any string containing it.

    A plain substring on "classname.name" counted a sibling class and a same-named method in another
    module as the target test (audit).
    """
    if not name_filter:
        return True
    cls = (classname or "").replace("$", ".")
    f = name_filter.replace("$", ".")
    return (f == cls or cls.endswith("." + f) or f == f"{cls}.{name}" or f == f"{cls.rsplit('.', 1)[-1]}.{name}"
            or f == name)


def reports_written_since(roots, before, name_filter):
    tests = failures = skipped = 0
    messages, crashes, counted = [], [], {}
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*.xml"), recursive=True):
            st = os.stat(path)
            # Written by THIS run: new, or changed since the snapshot. A time margin instead let a red from
            # the previous run, under a second old, count for a run that never compiled (measured here).
            if before.get(path) == (st.st_mtime_ns, st.st_size):
                continue
            try:
                tree = ET.parse(path)
            except ET.ParseError:
                continue
            for case in tree.iter("testcase"):
                cls, name = case.get("classname", ""), case.get("name", "")
                if not matches_filter(cls, name, name_filter):
                    continue
                tests += 1
                # Every report the class was counted from, not just the first: the same class name in two
                # modules, or one class run on two devices, look identical in the totals otherwise.
                if path not in counted.setdefault(cls, []):
                    counted[cls].append(path)
                bad = case.find("failure")
                if bad is None:
                    bad = case.find("error")
                if bad is not None:
                    first = (bad.get("message") or (bad.text or "")).strip().splitlines()
                    line = f"{name}: {first[0][:160] if first else '(no message)'}"
                    if is_assertion(bad.get("type")):
                        failures += 1
                        messages.append(line)
                    else:
                        # R6: a crash before the check is not the test saying "expected this, got that".
                        crashes.append(f"{line}  [{bad.get('type') or 'no type'}]")
                elif case.find("skipped") is not None:
                    skipped += 1
    return tests, failures, skipped, messages, crashes, counted


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--expect", choices=["red", "green"], required=True)
    p.add_argument("--test", help="count only test cases whose class.name contains this")
    p.add_argument("--reports", action="append", help="folder with JUnit XML; default: every test-results folder below .")
    p.add_argument("--timeout", type=float, default=900, help="seconds; a test that never ends is not red (R6)")
    p.add_argument("--break", dest="breaks", nargs=3, action="append", metavar=("FILE", "OLD", "NEW"),
                   help="make this break for the run and undo it after, checked byte for byte; OLD must appear once")
    p.add_argument("command", nargs=argparse.REMAINDER)
    a = p.parse_args()
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        p.error("give the test command after --")
    if "gradle" in os.path.basename(cmd[0]) and "--rerun" not in cmd:
        print("note: no --rerun — Gradle may call the task up to date and write no report (it will say NOT RUN)",
              file=sys.stderr)

    originals = apply_breaks(a.breaks)
    try:
        judge(a, cmd)
    finally:
        restore(originals)


def judge(a, cmd):
    roots = a.reports or default_roots()
    before = snapshot(roots)
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
        output, code = run.stdout + run.stderr, run.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or b""
        tail = (raw if isinstance(raw, str) else raw.decode(errors="replace"))[-300:].strip()
        print(f"NOT RUN: no end after {a.timeout:.0f} s — a hang is a finding, not a red (R6). Last output: {tail or '(none)'}")
        sys.exit(2)
    if not a.reports:
        roots = default_roots()

    tests, failures, skipped, messages, crashes, counted = reports_written_since(roots, before, a.test)
    for cls, paths in sorted(counted.items()):
        for path in paths:
            print(f"   counted {cls} from {path}")
        if len(paths) > 1:
            print(f"   note: {cls} counted from {len(paths)} report files — two variants, two source sets or two "
                  "devices. The colour below is all of them together.")
    if not a.test and len(counted) > 1:
        # Without --test, any report the command touched counts: an unrelated module's tests turned an
        # up-to-date target into GREEN (audit). Name what was counted instead of hiding it.
        print(f"   ⚠️ {len(counted)} test classes counted and no --test: this colour is the whole run's, "
              "not one test's", file=sys.stderr)
    cached = [l for l in output.splitlines() if "FROM-CACHE" in l and "> Task" in l]
    if cached:
        print(f"NOT RUN: the task came FROM-CACHE, so the report on disk is a restored one, not this run's "
              f"({cached[0].strip()[:120]}). Re-run with --rerun --no-build-cache.")
        sys.exit(2)
    if a.test and len(counted) > 1:
        # `--test Foo` names ONE test. Two classes answering to it are two different tests — sibling
        # classes, or the same name in another module — and the colour would be a mix of both (audit).
        print(f"NOT RUN: --test {a.test!r} matched {len(counted)} different classes: " + ", ".join(sorted(counted))
              + ". Name the class with its package, or point --reports at the one module.")
        sys.exit(2)
    if tests == 0:
        # Only when the command actually failed: `error:` appears in plenty of successful output, and an
        # up-to-date run was reported as a failed build because of it (audit).
        compile_lines = [l for l in output.splitlines() if l.startswith("e: ") or "Compilation error" in l
                         or "compilation failed" in l.lower() or re.search(r"\.(java|kt):\d+: error:", l)] if code != 0 else []
        if compile_lines:
            print(f"NOT RUN: the build failed before the test — {compile_lines[0][:200]}")
        else:
            tasks = [l.strip()[:120] for l in output.splitlines()
                     if "> Task" in l and ("UP-TO-DATE" in l or "FROM-CACHE" in l or "NO-SOURCE" in l)]
            print(f"NOT RUN: no report from this run{' for ' + repr(a.test) if a.test else ''} (exit {code}). "
                  "Up to date or cached? Rerun with --rerun --no-build-cache and name the test task."
                  + ("\n   " + "\n   ".join(tasks[:3]) if tasks else ""))
        sys.exit(2)
    if crashes and not failures:
        print(f"NOT RED: {len(crashes)} of {tests} ended before their check — a crash, not the test's own "
              "verdict (R6). Fix the crash, then look again:")
        for m in crashes[:5]:
            print(f"   {m}")
        sys.exit(2)
    if crashes:
        print(f"   note: {len(crashes)} more ended in a crash rather than a failed check: {crashes[0][:120]}")
    if failures:
        result = "red"
        print(f"RED: {failures} of {tests} failed, from reports this run wrote")
        for m in messages[:5]:
            print(f"   {m}")
        print("   Read the message: it must be the test's own check (R6), not a crash before it.")
    elif tests == skipped:
        print(f"NOT RUN: all {tests} test cases were skipped")
        sys.exit(2)
    else:
        result = "green"
        print(f"GREEN: {tests - skipped} passed{f', {skipped} skipped' if skipped else ''}, from reports this run wrote")
        print("   A green is the runner's verdict, not proof the test exercised the behaviour: an early `return`, a "
              "swallowed exception or a missing assertion all pass. The red you saw first is what proves it (R6).")
    sys.exit(0 if result == a.expect else 1)


if __name__ == "__main__":
    main()
