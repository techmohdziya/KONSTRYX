"""A local proxy that signs requests as a demo user, so the screens can be seen.

The service requires an authenticated user for every entity, so a browser
pointed at it gets a password box. This forwards to it on 8091 and adds the
same basic-auth header the verification suites already use, with the mock
credentials that live in those suites — nothing here is a secret that was not
already in test/verify. It exists so a screen can be looked at rather than
inferred from its manifest, which is how every action dialog in the product
came to be labelled with its own parameter names.

    python tools/dev_proxy.py [user]

Stop it when you are done: a listener that signs every request as an
administrator is not something to leave running.
"""
import base64
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "http://localhost:8090"
USER = sys.argv[1] if len(sys.argv) > 1 else "admin"
AUTH = "Basic " + base64.b64encode(("%s:%s" % (USER, USER)).encode()).decode()
HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade",
       "proxy-authenticate", "proxy-authorization", "te", "trailer",
       "content-encoding", "content-length"}


class Proxy(BaseHTTPRequestHandler):
    # One request per connection. A launchpad opens several counts at once and
    # a reused connection here drops them.
    protocol_version = "HTTP/1.0"

    def log_message(self, *args):
        pass

    def forward(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        request = urllib.request.Request(UPSTREAM + self.path, data=body,
                                         method=self.command)
        for name, value in self.headers.items():
            if name.lower() not in HOP and name.lower() != "authorization":
                request.add_header(name, value)
        request.add_header("Authorization", AUTH)
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                status, headers = response.status, response.headers
        except urllib.error.HTTPError as error:
            payload = error.read()
            status, headers = error.code, error.headers
        except Exception as error:  # upstream down, or a dropped socket
            payload = str(error).encode()
            status, headers = 502, {}
        self.send_response(status)
        for name, value in (headers.items() if headers else []):
            if name.lower() not in HOP:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except Exception:
            pass

    do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = do_HEAD = forward


print("signing every request as %s, forwarding 8091 -> 8090" % USER)
ThreadingHTTPServer(("127.0.0.1", 8091), Proxy).serve_forever()
