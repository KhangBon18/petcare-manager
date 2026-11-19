"""Loopback-only Vision response for isolated academic demonstrations."""

from __future__ import annotations

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json

from PIL import Image


class _Handler(BaseHTTPRequestHandler):
    server_version = "PetCareLocalVisionMock/1"

    def log_message(self, *_args):
        # Do not log image payloads, request headers, or mock API tokens.
        return

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"status": "ready"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8 * 1024 * 1024:
                self._json(413, {"error": "invalid local demo payload"})
                return
            request = json.loads(self.rfile.read(length))
            messages = request.get("messages")
            content = messages[-1].get("content") if isinstance(messages, list) and messages else None
            if not isinstance(content, list):
                self._json(200, self._completion(
                    "This local Vision mock returns fixed synthetic observations only."
                ))
                return
            image_url = next(
                (part.get("image_url", {}).get("url") for part in content
                 if isinstance(part, dict) and part.get("type") == "image_url"),
                None,
            )
            if not isinstance(image_url, str) or not image_url.startswith("data:image/jpeg;base64,"):
                self._json(400, {"error": "expected an in-memory JPEG data URL"})
                return
            raw = base64.b64decode(image_url.split(",", 1)[1], validate=True)
            with Image.open(BytesIO(raw)) as image:
                image.verify()
            suggestion = json.dumps({
                "species": "cat",
                "breed": "domestic shorthair",
                "coat_color": "gray",
                "eye_color": "green",
                "appearance_tags": ["synthetic demo image"],
            })
            self._json(200, self._completion(suggestion))
        except (ValueError, TypeError, KeyError, StopIteration, json.JSONDecodeError):
            self._json(400, {"error": "invalid local demo request"})
        except Exception:
            self._json(500, {"error": "local demo mock failed"})

    @staticmethod
    def _completion(content):
        return {"choices": [{"message": {"content": content}}]}

    def _json(self, status, value):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1" or not 1 <= args.port <= 65535:
        parser.error("the demo mock must bind to 127.0.0.1 on a valid port")
    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
