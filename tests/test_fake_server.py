"""fake_server.py's contract: it answers like a server, and it never prints a credential back."""
import http.client
import json
import os
import socket
import subprocess
import time
import unittest

from harness import Case, FAKE_SERVER


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeServer(Case):
    def server(self, *args):
        port = free_port()
        self.out = os.path.join(self.dir, "server.log")
        fh = open(self.out, "w")
        self.addCleanup(fh.close)
        proc = subprocess.Popen(["python3", "-u", FAKE_SERVER, "--port", str(port), *args],
                                stdout=fh, stderr=subprocess.STDOUT)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            self.fail("the fake server never came up")
        return http.client.HTTPConnection("127.0.0.1", port, timeout=5)

    def printed(self):
        for _ in range(20):
            with open(self.out) as fh:
                text = fh.read()
            if text.count("\n") > 1:
                return text
            time.sleep(0.1)
        return text

    def test_head_answers_the_headers_and_no_body(self):
        conn = self.server("--status", "200", "--body", '{"ok":true}')
        conn.request("HEAD", "/api/items")
        r = conn.getresponse()
        body = r.read()
        self.assertEqual(200, r.status)
        self.assertEqual(b"", body, "a HEAD with a body hangs a real client")
        self.assertEqual("11", r.getheader("Content-Length"))

    def test_two_headers_with_the_same_name_both_arrive(self):
        conn = self.server("--status", "200", "--header", "Set-Cookie: a=1",
                           "--header", "Set-Cookie: b=2")
        conn.request("GET", "/")
        r = conn.getresponse()
        r.read()
        self.assertEqual(2, len([v for k, v in r.getheaders() if k.lower() == "set-cookie"]))

    def test_options_is_answered(self):
        conn = self.server("--status", "200")
        conn.request("OPTIONS", "/api/items")
        r = conn.getresponse()
        r.read()
        self.assertEqual(200, r.status)

    def test_a_route_answers_its_own_status_and_everything_else_gets_the_default(self):
        routes = os.path.join(self.dir, "routes.json")
        with open(routes, "w") as fh:
            json.dump({"GET /api/items": {"status": 200, "body": "[]"}}, fh)
        conn = self.server("--routes", routes, "--status", "500")
        conn.request("GET", "/api/items")
        r = conn.getresponse()
        self.assertEqual((200, b"[]"), (r.status, r.read()))
        conn.request("GET", "/api/other")
        r = conn.getresponse()
        r.read()
        self.assertEqual(500, r.status)

    def test_a_credential_in_the_request_is_not_printed_back(self):
        conn = self.server("--status", "401")
        conn.request("POST", "/login", body=json.dumps({"user": "ana", "password": "hunter2"}),
                     headers={"Content-Type": "application/json"})
        conn.getresponse().read()
        printed = self.printed()
        self.assertIn("POST /login", printed)
        self.assertNotIn("hunter2", printed, "the request log is evidence for the report: no credentials in it")
        self.assertIn("ana", printed)


if __name__ == "__main__":
    unittest.main()
