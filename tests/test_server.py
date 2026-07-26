import json
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
