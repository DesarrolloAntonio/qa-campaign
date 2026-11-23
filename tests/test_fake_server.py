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

    def test_a_chunked_body_is_printed_like_any_other(self):
        # A client that streams its body sends no Content-Length: the log showed a POST that sent nothing.
        conn = self.server("--status", "200")
        conn.request("POST", "/api/login", body=iter([b'{"user":"ana",', b'"password":"hunter2"}']),
                     headers={"Transfer-Encoding": "chunked"}, encode_chunked=True)
        conn.getresponse().read()
        printed = self.printed()
        self.assertIn('"user":"ana"', printed)
        self.assertNotIn("hunter2", printed)

    def test_a_content_length_that_is_not_a_number_still_gets_the_answer(self):
        conn = self.server("--status", "503")
        conn.putrequest("POST", "/api/items")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        self.assertEqual(503, conn.getresponse().status)
        self.assertIn("not a number", self.printed())

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

    def test_a_credential_in_the_query_string_is_not_printed_back(self):
        conn = self.server("--status", "200")
        conn.request("GET", "/api/items?api_key=QAsecretvalue123&page=2")
        conn.getresponse().read()
        printed = self.printed()
        self.assertIn("GET /api/items", printed)
        self.assertNotIn("QAsecretvalue123", printed, "a key in the URL is a credential like one in the body")
        self.assertIn("page=2", printed)

    def test_a_secret_is_hidden_before_the_body_is_cut_not_after(self):
        # Cut first, the object under a secret key never closes, and what was inside it printed.
        body = json.dumps({"pins": {"pad": "x", "user": "4321", "more": "y" * 400}})
        conn = self.server("--status", "200")
        conn.request("POST", "/api/pins", body=body, headers={"Content-Type": "application/json"})
        conn.getresponse().read()
        printed = self.printed()
        self.assertIn("POST /api/pins", printed)
        self.assertNotIn("4321", printed)

    def refused_at_start(self, *args):
        r = subprocess.run(["python3", FAKE_SERVER, *args], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(0, r.returncode, r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        return r.stderr

    def test_a_port_already_taken_says_so(self):
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen()
            self.assertIn("in use", self.refused_at_start("--port", str(taken.getsockname()[1])))

    def test_a_routes_file_that_is_not_what_it_should_be_says_so(self):
        routes = os.path.join(self.dir, "routes.json")
        for text, said in (("{not json", "not valid JSON"), ("[1, 2]", "must be an object"),
                           ('{"GET /x": 200}', "must be an object")):
            with open(routes, "w") as fh:
                fh.write(text)
            self.assertIn(said, self.refused_at_start("--port", str(free_port()), "--routes", routes), text)

    def test_a_header_with_no_colon_is_refused_at_start(self):
        # It used to start, and then drop every connection: the app saw a network failure, not the
        # status the test asked for.
        proc = subprocess.Popen(["python3", "-u", FAKE_SERVER, "--port", str(free_port()),
                                 "--header", "X-No-Colon"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            out, _ = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("the server started with a header it cannot send")
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("X-No-Colon", out)


if __name__ == "__main__":
    unittest.main()
