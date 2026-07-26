import urllib.error
import urllib.request
import threading
import json
from sfxforge.server import create_server
import unittest

from tests.http_harness import request


class ServerTests(unittest.TestCase):
    def test_editor_assets_and_preset_api_are_served(self) -> None:
        page_response = request("/")
        self.assertEqual(page_response.status, 200)
        page = page_response.body.decode("utf-8")
        self.assertIn("SFX Forge", page)
        self.assertIn("Export WAV bank", page)

        script_response = request("/app.js")
        self.assertEqual(script_response.status, 200)
        self.assertIn(b"/api/render", script_response.body)
        self.assertIn(b'invalidateRenderedSound("Surface changed.', script_response.body)
        self.assertIn(b"revision !== state.revision", script_response.body)

        preset_response = request("/api/presets")
        self.assertEqual(preset_response.status, 200)
        payload = json.loads(preset_response.body)
        self.assertIn("footstep", payload["presets"])
        self.assertIn("metal", payload["surfaces"])

    def test_render_api_returns_wav_audio(self) -> None:
        response = request(
            "/api/render",
            {
                "kind": "impact",
                "seed": 91,
                "sample_rate": 8_000,
                "duration": 0.07,
                "brightness": 0.4,
                "resonance": 0.7,
                "variation": 0.3,
            },
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertTrue(response.body.startswith(b"RIFF"))

    def test_bad_request_returns_json_error(self) -> None:
        response = request("/api/render", {"kind": "unknown"})
        self.assertEqual(response.status, 400)
        payload = json.loads(response.body)
        self.assertIn("unknown effect", payload["error"])


if __name__ == "__main__":
    unittest.main()

class CrossOriginTests(unittest.TestCase):
    """The server binds loopback, which stops other machines but not this one's browser.

    A page on any site can POST to localhost. Choosing Content-Type: text/plain keeps the
    request "simple", so no CORS preflight is sent and the browser never asks permission,
    and /api/bank then performs synchronous synthesis. An independent review confirmed a
    request with Origin: https://attacker.example and Content-Type: text/plain returned
    200 with a ZIP.
    """

    def setUp(self):
        self.srv = create_server("127.0.0.1", 0)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)

    def post(self, headers, body=None):
        body = body or {"kind": "footstep", "count": 2, "seed": 1}
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/bank",
            data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_text_plain_with_foreign_origin_is_refused(self):
        # The review's exact reproduction.
        self.assertEqual(403, self.post(
            {"Content-Type": "text/plain", "Origin": "https://attacker.example"}))

    def test_foreign_origin_is_refused_even_with_json_content_type(self):
        self.assertEqual(403, self.post(
            {"Content-Type": "application/json", "Origin": "https://attacker.example"}))

    def test_missing_content_type_is_refused(self):
        self.assertEqual(403, self.post({}))

    def test_same_origin_request_still_works(self):
        # The guards must not break the editor they protect.
        self.assertEqual(200, self.post(
            {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}))

    def test_a_request_with_no_origin_still_works(self):
        # curl and the CLI send no Origin. Only a browser does, so absence is not suspicious.
        self.assertEqual(200, self.post({"Content-Type": "application/json"}))

