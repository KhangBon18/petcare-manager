import base64
import json
import unittest
from unittest.mock import patch

from flask import Flask

from petcare import create_app
from petcare.ai import client as ai_client


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.payload


class _Opener:
    def __init__(self, payload):
        self.payload = payload
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return _Response(self.payload)


class AIClientTests(unittest.TestCase):
    def _app(self, **overrides):
        config = {
            "TESTING": True,
            "APP_ENV": "test",
            "SECRET_KEY": "ai-client-tests-secret",
            "AI_API_BASE_URL": "http://127.0.0.1:45555/v1",
            "AI_API_KEY": "unit-test-key",
            "AI_MODEL": "vision-test-model",
            "AI_TIMEOUT_SECONDS": 7,
            "AI_VISION_MAX_RETRIES": 1,
            "AI_TEST_ALLOW_LOOPBACK_PROVIDER": True,
        }
        config.update(overrides)
        return create_app(config)

    def test_builds_openai_compatible_multimodal_request(self):
        body = {
            "choices": [{"message": {"content": "  Mô tả kiểm thử  "}}]
        }
        opener = _Opener(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        messages = [
            {"role": "system", "content": "Phân tích ngoại hình."},
            {"role": "user", "content": "Ảnh này có đặc điểm nào?"},
        ]
        with self._app().app_context(), patch(
            "petcare.ai.client.build_opener", return_value=opener
        ) as build_opener:
            response = ai_client.complete(messages, image_bytes=b"normalized-image")

        self.assertEqual(response, "Mô tả kiểm thử")
        self.assertEqual(opener.request.full_url, "http://127.0.0.1:45555/v1/chat/completions")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer unit-test-key")
        self.assertEqual(opener.timeout, 7)
        payload = json.loads(opener.request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "vision-test-model")
        self.assertEqual(payload["max_tokens"], 700)
        image = payload["messages"][-1]["content"][1]["image_url"]["url"]
        self.assertEqual(image, "data:image/jpeg;base64," + base64.b64encode(b"normalized-image").decode("ascii"))
        redirect_handler = build_opener.call_args.args[0]
        self.assertIsNone(redirect_handler.redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example"))

    def test_explicit_reasoning_effort_uses_completion_token_limit(self):
        opener = _Opener(b'{"choices":[{"message":{"content":"{}"}}]}')
        config = self._app(AI_REASONING_EFFORT="none")
        with config.app_context(), patch("petcare.ai.client.build_opener", return_value=opener):
            ai_client.complete([{"role": "user", "content": "test"}])
        payload = json.loads(opener.request.data.decode("utf-8"))
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(payload["max_completion_tokens"], 700)
        self.assertNotIn("max_tokens", payload)

    def test_rejects_insecure_production_endpoint_without_opening_connection(self):
        app = Flask("ai-client-test")
        app.config.update(
            APP_ENV="production",
            AI_API_BASE_URL="http://internal.example/v1",
            AI_ALLOW_HTTP_ENDPOINT=False,
            AI_MODEL="test-model",
        )
        with app.app_context(), patch("petcare.ai.client.build_opener") as build_opener:
            with self.assertRaisesRegex(ai_client.AIProviderError, "HTTPS"):
                ai_client.complete([{"role": "user", "content": "test"}])
        build_opener.assert_not_called()

    def test_rejects_endpoint_embedded_credentials(self):
        with self._app(AI_API_BASE_URL="https://user:secret@provider.example/v1").app_context():
            with self.assertRaisesRegex(ai_client.AIProviderError, "http hoặc https"):
                ai_client.complete([{"role": "user", "content": "test"}])

    def test_rejects_endpoint_query_parameters(self):
        with self._app(AI_API_BASE_URL="https://provider.example/v1?token=secret").app_context():
            with self.assertRaisesRegex(ai_client.AIProviderError, "http hoặc https"):
                ai_client.complete([{"role": "user", "content": "test"}])

    def test_rejects_oversized_provider_response(self):
        opener = _Opener(b"x" * 512_001)
        with self._app().app_context(), patch(
            "petcare.ai.client.build_opener", return_value=opener
        ):
            with self.assertRaisesRegex(ai_client.AIProviderError, "vượt giới hạn"):
                ai_client.complete([{"role": "user", "content": "test"}])

    def test_rejects_malformed_completion_payload(self):
        opener = _Opener(b'{"choices":[]}')
        with self._app().app_context(), patch(
            "petcare.ai.client.build_opener", return_value=opener
        ):
            with self.assertRaisesRegex(ai_client.AIProviderError, "không đúng định dạng"):
                ai_client.complete([{"role": "user", "content": "test"}])

    def test_test_environment_blocks_external_provider_before_transport(self):
        app = self._app(AI_API_BASE_URL="https://provider.example/v1", AI_TEST_ALLOW_LOOPBACK_PROVIDER=False)
        with app.app_context(), patch("petcare.ai.client.build_opener") as build_opener:
            with self.assertRaisesRegex(ai_client.AIProviderError, "disabled in tests"):
                ai_client.complete([{"role": "user", "content": "test"}], image_bytes=b"synthetic")
        build_opener.assert_not_called()

    def test_request_size_is_bounded_before_transport(self):
        with self._app().app_context(), patch("petcare.ai.client.build_opener") as build_opener:
            with self.assertRaisesRegex(ai_client.AIProviderError, "vượt giới hạn"):
                ai_client.complete([{"role": "user", "content": "test"}], image_bytes=b"x" * (8 * 1024 * 1024 + 1))
        build_opener.assert_not_called()

    def test_vision_retry_is_bounded_to_one_transient_retry(self):
        with self._app().app_context(), patch(
            "petcare.ai.client.complete",
            side_effect=[ai_client.AIProviderError("offline", retryable=True), "{}"],
        ) as complete, patch("petcare.ai.client.time.sleep") as sleep:
            response = ai_client.complete_vision([{"role": "user", "content": "inspect"}], b"synthetic")
        self.assertEqual(response, "{}")
        self.assertEqual(complete.call_count, 2)
        sleep.assert_called_once_with(0.1)

    def test_vision_does_not_retry_non_transient_errors(self):
        with self._app().app_context(), patch(
            "petcare.ai.client.complete", side_effect=ai_client.AIProviderError("bad request")
        ) as complete, patch("petcare.ai.client.time.sleep") as sleep:
            with self.assertRaisesRegex(ai_client.AIProviderError, "bad request"):
                ai_client.complete_vision([{"role": "user", "content": "inspect"}], b"synthetic")
        complete.assert_called_once()
        sleep.assert_not_called()

    def test_reasoning_effort_rejects_unknown_values_at_app_configuration(self):
        with self.assertRaisesRegex(RuntimeError, "AI_REASONING_EFFORT"):
            self._app(AI_REASONING_EFFORT="surprise")


if __name__ == "__main__":
    unittest.main()
