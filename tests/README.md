# The harness's own tests

A QA harness that lies is worse than no harness: the agent believes it, writes the claim into the
report, and the defect ships anyway. R8 says the tool is the first suspect — these tests are how that
stops being a good intention.

```bash
tests/run                 # every test
tests/run test_net        # one file
```

**No device, no network, no project.** Every test runs against `stub_adb.py`, a fake `adb` that answers
from environment variables, in a temp folder with its own `qa.config.json`, its own `HOME` and its own
lock folder. They pass on a laptop with nothing plugged in, in a couple of seconds, so there is no
excuse for not running them.

What they pin down is the **contract**, not the implementation:

| The harness must | Because |
|---|---|
| refuse a selector that is two different controls | taking the first is how "Delete" hits the wrong Delete and the run still reads green |
| refuse a device that is not on the allow-list, **before** any shell command | that device can be someone's work phone |
| refuse everything when there is no configuration | a harness with nothing configured must say so, never print "0 warnings" |
| refuse input when another app is in front | the other campaign's app stays in the task stack |
| never print a credential | the STORE and LOG oracles are evidence, and evidence gets pasted into reports |
| refuse when it cannot read the density or the screen size | every dp figure and every tap coordinate comes from them; "assuming 420" is a measurement nobody took |
| refuse a `packagePrefix` that matches two installed apps | the vendor's other app's screens would read as this one's |
| ignore a report whose own timestamp predates the run | this run touching a file is not this run writing it |
| refuse two report files for one test that disagree | neither is the test's verdict, and summing them gives whichever colour you asked for |
| refuse a `--break` that only moves whitespace, and call a green under a break a mutation that proved nothing | "I broke it and it stayed green" is read as "this test won't go red" |
| exit 3 when a `--break` cannot be undone | a source left broken is the worst thing this tool can leave behind |
| treat an open port that answers no HTTP as **not reachable** | a dangling `adb reverse` accepts the connection with nothing behind it (measured on API 37) |
| prove offline from the **app's** side, and name a fake server instead of calling it offline | airplane mode is Android's state, not the app's |
| distinguish "adb lost the device" from "offline" | they look identical on a phone on Wi-Fi |
| refuse a throttle the emulator did not accept | `adb emu` prints `KO:` and exits 0 |
| count only reports **this run** wrote | a stale red from the previous run is not a red |
| call a crash NOT RED, and a cached task NOT RUN | neither is the test's own verdict |
| refuse a `--test` that matches two classes | the colour would be a mix of two different tests |
| undo a `--break` byte for byte, and refuse one that is not unique | a half-restored source is the worst thing this tool can leave behind |
| say what a green does **not** prove | the runner passing is not the test exercising the behaviour |

Adding a test: put it beside the others, use `harness.Case` (it builds the workspace and the stub), and
name it as the sentence it defends — `test_a_crash_is_not_a_red`. When a friction report says the
harness lied, the fix comes with the test that would have caught it.
