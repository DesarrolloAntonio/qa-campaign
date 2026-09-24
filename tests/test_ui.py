"""ui.py's contract: what it refuses, and what it never sends to a device."""
import os
import subprocess
import sys
import unittest

from harness import Case, PKG, UI

HEAD = "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n<hierarchy rotation=\"0\">"
TAIL = "</hierarchy>"


def node(cls, bounds, text="", desc="", clickable="false", children=""):
    x1, y1, x2, y2 = bounds
    return (f'<node index="0" text="{text}" resource-id="" class="{cls}" package="{PKG}" '
            f'content-desc="{desc}" checkable="false" checked="false" clickable="{clickable}" '
            f'enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" '
            f'password="false" selected="false" bounds="[{x1},{y1}][{x2},{y2}]">{children}</node>')


def row(title, y, label="Delete"):
    """A list item with its own title and its own Delete — the shape that makes a selector ambiguous."""
    inner = (node("android.widget.TextView", (20, y + 20, 500, y + 180), text=title)
             + node("android.widget.TextView", (900, y + 20, 1060, y + 180), text=label))
    return node("android.view.View", (0, y, 1080, y + 200), clickable="true", children=inner)


TWO_ROWS = HEAD + node("android.widget.FrameLayout", (0, 0, 1080, 2400),
                       children=row("QA_Item1", 200) + row("QA_Item2", 500)) + TAIL

# One control, its label repeated inside it: a chip and a title that say the same word.
ONE_CONTROL_TWICE = HEAD + node(
    "android.widget.FrameLayout", (0, 0, 1080, 2400),
    children=node("android.view.View", (0, 200, 1080, 400), clickable="true",
                  children=node("android.widget.TextView", (20, 220, 500, 380), text="Partial")
                  + node("android.widget.TextView", (600, 220, 800, 380), text="Partial"))) + TAIL


class Selectors(Case):
    def test_a_selector_that_is_two_different_controls_is_refused(self):
        r = self.run_ui("tap", "text=Delete", STUB_DUMP=self.with_dump(TWO_ROWS))
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "refusing")
        self.assertSaid(r, "2 different controls")
        self.assertNoInput()

    def test_index_names_one_of_them(self):
        r = self.run_ui("tap", "text=Delete", "--index", "1", STUB_DUMP=self.with_dump(TWO_ROWS))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("shell input tap 540 600", self.adb_calls())   # the second row, not the first

    def test_any_takes_the_first_and_says_it_did(self):
        r = self.run_ui("tap", "text=Delete", "--any", STUB_DUMP=self.with_dump(TWO_ROWS))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertSaid(r, "--any took the first")
        self.assertIn("shell input tap 540 300", self.adb_calls())

    def test_the_same_control_matched_twice_is_not_ambiguous(self):
        r = self.run_ui("tap", "text=Partial", STUB_DUMP=self.with_dump(ONE_CONTROL_TWICE))
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertSaid(r, "first of 2 matches")
        self.assertEqual(1, len([c for c in self.adb_calls() if "input tap" in c]))

    def test_a_selector_that_matches_nothing_fails_and_says_what_is_there(self):
        r = self.run_ui("tap", "text=Publish", STUB_DUMP=self.with_dump(TWO_ROWS))
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "NOT found")
        self.assertSaid(r, "QA_Item1")
        self.assertNoInput()


class Guards(Case):
    def test_a_device_that_is_not_on_the_allow_list_is_refused(self):
        r = self.run_ui("dump", STUB_SERIAL="RFCRB0XRA7R")
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "refusing RFCRB0XRA7R")
        self.assertEqual([], [c for c in self.adb_calls() if c.startswith("shell")],
                         "nothing may be asked of a device the campaign was not given")

    def test_without_a_configuration_nothing_is_touched(self):
        os.remove(self.config_path)          # and nothing above the temp folder has one either
        env = self.env()
        del env["QA_CONFIG"]
        r = subprocess.run(["python3", UI, "dump"], capture_output=True, text=True, cwd=self.dir, env=env)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("qa.config.json", r.stdout + r.stderr)
        self.assertEqual([], self.adb_calls(), "the refusal must come before the first adb call")

    def test_input_is_refused_when_another_app_is_in_front(self):
        r = self.run_ui("tap", "text=Delete", "--index", "0",
                        STUB_DUMP=self.with_dump(TWO_ROWS), STUB_FRONT="com.android.chrome")
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "com.android.chrome is in front")
        self.assertNoInput()

    def test_a_dump_that_never_answers_is_not_an_empty_screen(self):
        r = self.run_ui("dump")                     # no STUB_DUMP: uiautomator keeps failing
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "did not answer")


class Measurements(Case):
    """The harness never replaces a measurement it could not take with a plausible number."""

    def test_an_unreadable_density_is_unproven_not_420(self):
        r = self.run_ui("a11y", STUB_DUMP=self.with_dump(TWO_ROWS), STUB_DENSITY="")
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "UNPROVEN")
        self.assertNotIn("420", r.stdout)

    def test_an_unreadable_screen_size_is_unproven_not_1080x2400(self):
        flat = HEAD + node("android.widget.FrameLayout", (0, 0, 0, 0),
                           children=row("QA_Item1", 200)) + TAIL
        r = self.run_ui("tap", "text=Delete", STUB_DUMP=self.with_dump(flat),
                        STUB_DISPLAYS="", STUB_WM_SIZE="")
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "UNPROVEN")
        self.assertNoInput("a tap needs coordinates, and there were none to read")


class WhichApp(Case):
    """R8: what the tree says is only evidence if it belongs to the app under test."""

    def test_a_prefix_that_matches_two_installed_apps_is_refused(self):
        self.write_config(android={"package": PKG, "packagePrefix": "com.example"})
        r = self.run_ui("dump", STUB_DUMP=self.with_dump(TWO_ROWS),
                        STUB_PACKAGES="com.example.app,com.example.other")
        self.assertNotEqual(0, r.returncode)
        self.assertSaid(r, "matches 2 installed packages")
        self.assertSaid(r, "packagePrefix")

    def test_an_explicit_list_of_packages_is_taken_as_given(self):
        self.write_config(android={"package": PKG, "packagePrefix": [PKG, PKG + ".debug"]})
        r = self.run_ui("tap", "text=Delete", "--index", "0", STUB_DUMP=self.with_dump(TWO_ROWS),
                        STUB_PACKAGES="com.example.app,com.example.other")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual([], [c for c in self.adb_calls() if "pm list packages" in c],
                         "a list needs no guessing, so the device is not asked")


class Secrets(Case):
    """R11: the STORE and LOG oracles never print a credential."""

    def test_secret_looking_values_are_hidden_and_the_rest_is_not(self):
        text = 'password=hunter2\n"pins": {"a": "1234"}\nuser=ana\ntoken=abc.def.ghi\n'
        code = ("import sys; sys.path.insert(0, %r); import ui; "
                "sys.stdout.write(ui.hide_secrets_in_text(sys.stdin.read()))"
                % os.path.dirname(UI))
        r = subprocess.run([sys.executable, "-c", code], input=text, capture_output=True, text=True,
                           env=self.env())
        self.assertEqual(0, r.returncode, r.stderr)
        for secret in ("hunter2", "1234", "abc.def.ghi"):
            self.assertNotIn(secret, r.stdout)
        self.assertIn("ana", r.stdout)


if __name__ == "__main__":
    unittest.main()
