import json
import unittest
from unittest.mock import patch
from synthesizer.generator import CandidateSynthesizer, NoRedirect


class Response:
    def __init__(self, content):
        self.content = content
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.content[:count]


class ModelAdapterTests(unittest.TestCase):
    def test_source_usage_and_request_contract(self):
        payload = {"choices": [{"message": {"content": "```python\ndef gcd(a, b):\n    return 1\n```"}}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 12}}
        with patch.dict("os.environ", {"LAB_MODEL_URL": "http://localhost:8000/v1/chat/completions", "LAB_MODEL_NAME": "test-model"}, clear=True), patch("synthesizer.generator.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response(json.dumps(payload).encode())
            model = CandidateSynthesizer("api")
            source = model.generate("direct", {"specification": "test"}, 1)
            self.assertTrue(source.startswith("def gcd"))
            self.assertEqual(model.last_usage["completion_tokens"], 12)
            args, kwargs = opener.return_value.open.call_args
            body = json.loads(args[0].data)
            self.assertEqual(body["max_tokens"], 2048)
            self.assertEqual(kwargs["timeout"], 60)
            self.assertNotIn("Authorization", args[0].headers)

    def test_insecure_remote_endpoint_rejected(self):
        with patch.dict("os.environ", {"LAB_MODEL_URL": "http://example.com/v1/chat/completions"}, clear=True):
            with self.assertRaises(ValueError):
                CandidateSynthesizer("api").generate("direct", {}, 1)

    def test_redirect_rejected(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://example.com")

    def test_oversized_response_rejected(self):
        with patch.dict("os.environ", {"LAB_MODEL_URL": "https://example.com/v1/chat/completions", "LAB_MODEL_NAME": "test-model"}, clear=True), patch("synthesizer.generator.urllib.request.build_opener") as opener:
            opener.return_value.open.return_value = Response(b"x" * 131073)
            with self.assertRaisesRegex(ValueError, "too large"):
                CandidateSynthesizer("api").generate("direct", {}, 1)


if __name__ == "__main__":
    unittest.main()
