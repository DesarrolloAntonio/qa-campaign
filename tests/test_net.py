"""net.sh's contract: a network state is only reported when it was proved, and from the app's side."""
import unittest

from harness import Case


class Reach(Case):
    def test_an_open_port_that_answers_no_http_is_not_a_server(self):
        # Measured on API 37: a dangling `adb reverse` takes the connection and exits 0.
        r = self.run_net("reach", STUB_NC_EXIT=0, STUB_HTTP="")
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "answers no HTTP")

    def test_the_http_status_is_reported_whatever_it_is(self):
        r = self.run_net("reach", STUB_NC_EXIT=0, STUB_HTTP="HTTP/1.0 401 Unauthorized")
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertSaid(r, "HTTP 401 from the server")

    def test_a_refused_connection_says_the_computer_proves_nothing(self):
        r = self.run_net("reach", STUB_NC_EXIT=1)
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "cannot connect")
        self.assertSaid(r, "The computer reaching it proves nothing")

    def test_without_nc_it_says_it_could_not_check(self):
        r = self.run_net("reach", STUB_NC="no")
        self.assertEqual(2, r.returncode, "2 is 'could not check', not 'unreachable'")
        self.assertSaid(r, "not the same as unreachable")


class Offline(Case):
    def test_offline_is_proved_from_the_apps_side_too(self):
        r = self.run_net("off", STUB_AIRPLANE=1, STUB_VALIDATED="no", STUB_NC_EXIT=1)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertSaid(r, "offline (airplane_mode_on=1)")
        self.assertSaid(r, "cannot reach 10.0.2.2:18099")

    def test_a_server_the_app_still_reaches_is_not_offline(self):
        self.write_config(server={"url": "http://192.168.1.50:8085"})
        r = self.run_net("off", STUB_AIRPLANE=1, STUB_VALIDATED="no", STUB_NC_EXIT=0)
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "NOT offline for the app")

    def test_a_fake_server_on_this_computer_is_named_not_refused(self):
        self.write_config(server={"url": "http://127.0.0.1:18099"})
        r = self.run_net("off", STUB_AIRPLANE=1, STUB_VALIDATED="no", STUB_NC_EXIT=0)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertSaid(r, "relay or the fake server on this computer")

    def test_adb_losing_the_device_is_not_offline(self):
        r = self.run_net("off", STUB_VALIDATED="no", STUB_SETTINGS_LOST=1)
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "adb lost the device")

    def test_something_else_taking_the_network_down_is_not_offline(self):
        r = self.run_net("off", STUB_AIRPLANE=0, STUB_VALIDATED="no")
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "something else took the network down")


class Guards(Case):
    def test_a_device_that_is_not_on_the_allow_list_is_refused(self):
        r = self.run_net("status", STUB_SERIAL="RFCRB0XRA7R")
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "refusing RFCRB0XRA7R")

    def test_a_throttle_the_emulator_refused_is_not_a_throttle(self):
        r = self.run_net("slow", "edge", STUB_EMU="KO: unknown network speed")
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "the emulator refused")

    def test_no_device_at_all_exits_one(self):
        r = self.run_net("status", STUB_STATE="none")
        self.assertEqual(1, r.returncode)
        self.assertSaid(r, "no device reachable")


if __name__ == "__main__":
    unittest.main()
