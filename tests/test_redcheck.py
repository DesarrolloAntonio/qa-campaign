"""redcheck.py's contract: a colour only from a report THIS run wrote, and only for the test you named."""
import os
import shlex
import unittest

from harness import Case

PASS = '<testcase name="testSave" classname="{cls}" time="0.1"/>'
FAIL = ('<testcase name="testSave" classname="{cls}" time="0.1">'
        '<failure message="expected:&lt;1&gt; but was:&lt;0&gt;" type="org.junit.ComparisonFailure">at Foo</failure>'
        '</testcase>')
CRASH = ('<testcase name="testSave" classname="{cls}" time="0.1">'
         '<failure message="lateinit property db has not been initialized" '
         'type="kotlin.UninitializedPropertyAccessException">at Foo</failure></testcase>')
SKIP = '<testcase name="testSave" classname="{cls}" time="0"><skipped/></testcase>'


def junit(case=PASS, cls="com.a.FooTest", timestamp=None):
    stamp = f' timestamp="{timestamp}"' if timestamp else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<testsuite name="{cls}" tests="1" skipped="0" failures="0" errors="0" time="0.1"{stamp}>'
            + case.format(cls=cls) + '</testsuite>')


class RedCheck(Case):
    def runner(self, reports=None, output="", code=0, sleep=0):
        """A test command that writes exactly the reports it is told to — and sometimes none at all."""
        path = os.path.join(self.dir, "run.sh")
        lines = ["#!/bin/bash", "set -e"]
        if sleep:
            lines.append(f"sleep {sleep}")
        for rel, xml in (reports or {}).items():
            full = os.path.join(self.dir, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            lines += [f"cat > {shlex.quote(full)} <<'XML'", xml, "XML"]
        if output:
            lines.append("printf '%s\\n' " + shlex.quote(output))
        lines.append(f"exit {code}")
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        os.chmod(path, 0o755)
        return path

    def test_a_green_says_what_it_does_not_prove(self):
        r = self.run_redcheck("--expect", "green", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(PASS)}))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertSaid(r, "GREEN")
        self.assertSaid(r, "not proof the test exercised the behaviour")

    def test_a_failed_check_is_red(self):
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(FAIL)}, code=1))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertSaid(r, "RED: 1 of 1 failed")

    def test_a_crash_is_not_a_red(self):
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(CRASH)}, code=1))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "NOT RED")

    def test_only_skipped_is_not_run(self):
        r = self.run_redcheck("--expect", "green", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(SKIP)}))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "were skipped")

    def test_a_report_this_run_did_not_write_does_not_count(self):
        stale = os.path.join(self.dir, "build/test-results/test/TEST-a.xml")
        os.makedirs(os.path.dirname(stale), exist_ok=True)
        with open(stale, "w") as fh:
            fh.write(junit(FAIL))                      # a red from a previous run, still on disk
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--", self.runner())
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "no report from this run")

    def test_a_task_from_the_cache_is_not_run(self):
        r = self.run_redcheck("--expect", "green", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(PASS)},
                                         output="> Task :feature:ui:testDebugUnitTest FROM-CACHE"))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "FROM-CACHE")

    def test_a_filter_that_matches_two_classes_is_not_run(self):
        r = self.run_redcheck("--expect", "green", "--test", "FooTest", "--",
                             self.runner({"a/build/test-results/test/TEST-a.xml": junit(PASS, "com.a.FooTest"),
                                          "b/build/test-results/test/TEST-b.xml": junit(PASS, "com.b.FooTest")}))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "matched 2 different classes")

    def test_one_class_counted_from_two_report_files_is_said_out_loud(self):
        r = self.run_redcheck("--expect", "green", "--test", "com.a.FooTest", "--",
                             self.runner({"a/build/test-results/test/TEST-a.xml": junit(PASS),
                                          "a/build/outputs/androidTest-results/TEST-b.xml": junit(PASS)}))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertSaid(r, "counted from 2 report files")

    def test_a_break_is_undone_byte_for_byte(self):
        source = os.path.join(self.dir, "Repo.kt")
        original = "class Repo {\n    fun save() = dao.insert(item)\n}\n"
        with open(source, "w") as fh:
            fh.write(original)
        r = self.run_redcheck("--expect", "green", "--test", "FooTest",
                             "--break", source, "dao.insert(item)", "Unit",
                             "--", self.runner({"build/test-results/test/TEST-a.xml": junit(PASS)}))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertSaid(r, "break undone")
        with open(source) as fh:
            self.assertEqual(original, fh.read())

    def test_a_break_that_is_not_unique_changes_nothing(self):
        source = os.path.join(self.dir, "Repo.kt")
        original = "fun a() = save()\nfun b() = save()\n"
        with open(source, "w") as fh:
            fh.write(original)
        r = self.run_redcheck("--expect", "red", "--test", "FooTest",
                             "--break", source, "save()", "Unit",
                             "--", self.runner({"build/test-results/test/TEST-a.xml": junit(FAIL)}, code=1))
        self.assertEqual(2, r.returncode, "a break that cannot be made is NOT RUN, not a colour")
        with open(source) as fh:
            self.assertEqual(original, fh.read())

    def test_a_report_whose_own_clock_predates_the_run_is_not_this_runs(self):
        # The mtime only says the file changed while the run was going: a restore, an rsync or an editor
        # save does that to a report from another run entirely.
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml":
                                          junit(FAIL, timestamp="2020-01-01T10:00:00")}, code=1))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "it did not write it")

    def test_two_report_files_that_disagree_are_not_a_colour(self):
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--",
                             self.runner({"a/build/test-results/test/TEST-a.xml": junit(FAIL),
                                          "b/build/test-results/test/TEST-b.xml": junit(PASS)}, code=1))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "disagree")

    def test_reports_from_something_else_running_are_named(self):
        r = self.run_redcheck("--expect", "green", "--test", "FooTest", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(PASS),
                                          "other/build/test-results/test/TEST-z.xml":
                                              junit(PASS, "com.z.OtherTest")}))
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertSaid(r, "something else is writing reports")

    def test_a_break_that_only_moves_whitespace_is_refused(self):
        source = os.path.join(self.dir, "Repo.kt")
        original = "class Repo {\n    fun save() = dao.insert(item)\n}\n"
        with open(source, "w") as fh:
            fh.write(original)
        r = self.run_redcheck("--expect", "red", "--test", "FooTest",
                             "--break", source, "dao.insert(item)", "dao.insert( item )",
                             "--", self.runner({"build/test-results/test/TEST-a.xml": junit(FAIL)}, code=1))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "differ only in whitespace")
        with open(source) as fh:
            self.assertEqual(original, fh.read())

    def test_a_break_that_leaves_it_green_is_a_mutation_that_proved_nothing(self):
        source = os.path.join(self.dir, "Repo.kt")
        with open(source, "w") as fh:
            fh.write("class Repo {\n    fun save() = dao.insert(item)\n}\n")
        r = self.run_redcheck("--expect", "red", "--test", "FooTest",
                             "--break", source, "dao.insert(item)", "Unit",
                             "--", self.runner({"build/test-results/test/TEST-a.xml": junit(PASS)}))
        self.assertEqual(1, r.returncode, "green where red was expected is still the other colour")
        self.assertSaid(r, "MUTATION NOT VALIDATED")

    def test_a_restore_that_cannot_be_done_exits_three(self):
        source = os.path.join(self.dir, "Repo.kt")
        with open(source, "w") as fh:
            fh.write("class Repo {\n    fun save() = dao.insert(item)\n}\n")
        runner = self.runner({"build/test-results/test/TEST-a.xml": junit(FAIL)}, code=1)
        wrapper = os.path.join(self.dir, "wrap.sh")      # the run leaves the source unwritable
        with open(wrapper, "w") as fh:
            fh.write(f"#!/bin/bash\n{shlex.quote(runner)}\ncode=$?\nchmod 444 {shlex.quote(source)}\nexit $code\n")
        os.chmod(wrapper, 0o755)
        r = self.run_redcheck("--expect", "red", "--test", "FooTest",
                             "--break", source, "dao.insert(item)", "Unit", "--", wrapper)
        os.chmod(source, 0o644)
        self.assertEqual(3, r.returncode, "a source left broken is the worst outcome and has its own code")
        self.assertSaid(r, "BREAK NOT UNDONE")
        self.assertSaid(r, "original kept at")

    def test_a_test_that_never_ends_is_not_red(self):
        r = self.run_redcheck("--expect", "red", "--test", "FooTest", "--timeout", "1", "--",
                             self.runner({"build/test-results/test/TEST-a.xml": junit(FAIL)}, sleep=5, code=1))
        self.assertEqual(2, r.returncode)
        self.assertSaid(r, "no end after")


if __name__ == "__main__":
    unittest.main()
