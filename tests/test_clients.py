"""Offline transport/selection regression checks; no real API requests."""
import contextlib
import io
import json
import unittest
import urllib.error
from unittest.mock import Mock, patch

import gemini_helper
import multi_llm_client as client


def response(body):
    result = Mock()
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.read.return_value = json.dumps(body).encode("utf-8")
    return result


def gemini_body(text="Bản dịch", finish="STOP"):
    return {
        "modelVersion": "actual-gemini-version",
        "candidates": [{"finishReason": finish,
                        "content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 9},
    }


def openai_body(text="Bản dịch", finish="stop"):
    return {"model": "actual-openai-version", "choices": [{
        "finish_reason": finish, "message": {"content": text}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 9}}


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"api_keys": ["test-secret"], "models": ["requested-gemini"]}
        self.openai_cfg = {"api_key": "test-secret", "models": ["requested-openai"]}
        self.settings = {"max_retries": 1}
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.sleep = patch.object(client.time, "sleep").start()
        self.addCleanup(patch.stopall)
        # Default rejects any attempted network unless a test installs its mock.
        self.transport = patch.object(client.urllib.request, "urlopen",
                                      side_effect=AssertionError("Unexpected HTTP call")).start()

    def test_gemini_excludes_thought_and_records_actual_model(self):
        body = gemini_body()
        body["candidates"][0]["content"]["parts"].insert(
            0, {"text": "Private reasoning", "thought": True})
        self.transport.side_effect = None
        self.transport.return_value = response(body)
        text, usage, model = client.call_gemini("source", None, self.cfg, self.settings)
        self.assertEqual(text, "Bản dịch")
        self.assertEqual(model, "gemini/actual-gemini-version")
        self.assertEqual(usage["model_used"], "actual-gemini-version")
        self.assertEqual(usage["requested_model"], "requested-gemini")
        self.assertTrue(usage["model_reported"])
        self.assertEqual(usage["finish_reason"], "STOP")
        self.assertEqual(usage["promptTokenCount"], 7)
        req = self.transport.call_args.args[0]
        self.assertNotIn("test-secret", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "test-secret")

    def test_gemini_rejects_incomplete_empty_and_thought_only(self):
        bodies = [gemini_body(finish=reason) for reason in (
            "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER", None)]
        bodies.extend([gemini_body(" "), {"candidates": []}, {}])
        thought_only = gemini_body()
        thought_only["candidates"][0]["content"]["parts"][0]["thought"] = True
        bodies.append(thought_only)
        for body in bodies:
            with self.subTest(body=body):
                self.transport.side_effect = None
                self.transport.return_value = response(body)
                with self.assertRaises(RuntimeError):
                    client.call_gemini("source", None, self.cfg, self.settings)

    def test_openai_records_actual_model_and_ignores_reasoning_field(self):
        body = openai_body()
        body["choices"][0]["message"]["reasoning_content"] = "Private reasoning"
        self.transport.side_effect = None
        self.transport.return_value = response(body)
        text, usage, model = client.call_openai_compatible(
            "source", None, "openai", self.openai_cfg, self.settings)
        self.assertEqual(text, "Bản dịch")
        self.assertEqual(model, "openai/actual-openai-version")
        self.assertEqual(usage["requested_model"], "requested-openai")
        self.assertEqual(usage["finish_reason"], "stop")
        self.assertEqual(usage["completion_tokens"], 9)

    def test_openai_rejects_incomplete_empty_and_refusal(self):
        bodies = [openai_body(finish=reason) for reason in (
            "length", "content_filter", "tool_calls", None)]
        bodies.extend([openai_body(" "), openai_body(None), {"choices": []}, {}])
        refusal = openai_body()
        refusal["choices"][0]["message"]["refusal"] = "refused"
        bodies.append(refusal)
        for body in bodies:
            with self.subTest(body=body):
                self.transport.side_effect = None
                self.transport.return_value = response(body)
                with self.assertRaises(RuntimeError):
                    client.call_openai_compatible("source", None, "openai",
                                                  self.openai_cfg, self.settings)

    def test_openai_embedded_thought_is_excluded(self):
        self.transport.side_effect = None
        self.transport.return_value = response(openai_body(
            "<think>Private reasoning\nmore reasoning</think>Bản dịch"))
        text, _, _ = client.call_openai_compatible(
            "source", None, "openai", self.openai_cfg, self.settings)
        self.assertEqual(text, "Bản dịch")
        for text in ("<think>Unclosed reasoning", "<think>Only reasoning</think>"):
            with self.subTest(text=text):
                self.transport.return_value = response(openai_body(text))
                with self.assertRaises(RuntimeError):
                    client.call_openai_compatible("source", None, "openai",
                                                  self.openai_cfg, self.settings)

    def test_unreported_model_is_explicitly_marked(self):
        body = gemini_body()
        del body["modelVersion"]
        self.transport.side_effect = None
        self.transport.return_value = response(body)
        _, usage, model = client.call_gemini("source", None, self.cfg, self.settings)
        self.assertFalse(usage["model_reported"])
        self.assertEqual(model, "gemini/requested-gemini")

    def test_invalid_response_can_only_fallback_to_allowed_model(self):
        cfg = dict(self.cfg, models=["first", "second"])
        self.transport.side_effect = [response(gemini_body(finish="MAX_TOKENS")),
                                     response(gemini_body())]
        _, usage, _ = client.call_gemini("source", None, cfg, self.settings)
        self.assertEqual(usage["requested_model"], "second")
        self.assertEqual(self.transport.call_count, 2)

    def test_retry_index_is_bounded_beyond_delay_list(self):
        self.transport.side_effect = urllib.error.URLError("url?key=test-secret")
        with self.assertRaises(RuntimeError) as caught:
            client.call_gemini("source", None, self.cfg, {"max_retries": 8})
        self.assertEqual(self.transport.call_count, 8)
        self.assertEqual(self.sleep.call_count, 7)
        self.assertEqual(self.sleep.call_args.args[0], 16)
        self.assertNotIn("test-secret", self.output.getvalue() + str(caught.exception))

    def test_http_error_body_and_url_are_never_logged(self):
        for provider in ("gemini", "openai"):
            with self.subTest(provider=provider):
                self.transport.side_effect = urllib.error.HTTPError(
                    "https://example.invalid?key=test-secret", 400,
                    "test-secret", {}, io.BytesIO(b"credentials test-secret"))
                with self.assertRaises(RuntimeError) as caught:
                    if provider == "gemini":
                        client.call_gemini("source", None, self.cfg, self.settings)
                    else:
                        client.call_openai_compatible("source", None, provider,
                                                      self.openai_cfg, self.settings)
                self.assertNotIn("test-secret", self.output.getvalue() + str(caught.exception))
                self.assertNotIn("example.invalid", self.output.getvalue())

    def config(self):
        return {"active_provider": "gemini", "settings": {"auto_fallback_provider": True},
                "providers": {"gemini": self.cfg, "openai": self.openai_cfg},
                "quality_roles": {"auditor": {"provider": "openai", "models": ["auditor-only"]}}}

    def test_role_only_uses_explicit_provider_models(self):
        config = self.config()
        with patch.object(client, "load_config", return_value=config), \
                patch.object(client, "call_openai_compatible", return_value=("ok", {}, "model")) as api, \
                patch.object(client, "call_gemini") as gemini:
            self.assertEqual(client.ask_ai("source", role="auditor")[0], "ok")
            self.assertEqual(api.call_args.args[2], "openai")
            self.assertEqual(api.call_args.args[3]["models"], ["auditor-only"])
            gemini.assert_not_called()
            self.assertEqual(config["providers"]["openai"]["models"], ["requested-openai"])

    def test_missing_or_invalid_role_fails_before_transport(self):
        configs = [self.config(), self.config(), self.config(), self.config()]
        configs[1]["quality_roles"]["auditor"]["models"] = []
        del configs[2]["quality_roles"]["auditor"]["models"]
        configs[3]["quality_roles"]["auditor"]["provider"] = "missing"
        for idx, config in enumerate(configs):
            with self.subTest(config=idx), patch.object(client, "load_config", return_value=config):
                with self.assertRaises(ValueError):
                    client.ask_ai("source", role="missing" if idx == 0 else "auditor")
        self.transport.assert_not_called()

    def test_role_never_uses_general_fallback_on_failure(self):
        with patch.object(client, "load_config", return_value=self.config()), \
                patch.object(client, "call_openai_compatible", side_effect=RuntimeError("test-secret")) as api, \
                patch.object(client, "call_gemini") as gemini:
            with self.assertRaises(RuntimeError) as caught:
                client.ask_ai("source", role="auditor")
            api.assert_called_once()
            gemini.assert_not_called()
            self.assertNotIn("test-secret", self.output.getvalue() + str(caught.exception))

    def test_conflicting_preferred_provider_fails_before_transport(self):
        with patch.object(client, "load_config", return_value=self.config()):
            with self.assertRaises(ValueError):
                client.ask_ai("source", preferred_provider="gemini", role="auditor")
        self.transport.assert_not_called()

    def test_active_provider_not_repeated_by_boolean_precedence(self):
        with patch.object(client, "load_config", return_value=self.config()), \
                patch.object(client, "call_gemini", side_effect=RuntimeError("failed")) as gemini, \
                patch.object(client, "call_openai_compatible", side_effect=RuntimeError("failed")) as api:
            with self.assertRaises(RuntimeError):
                client.ask_ai("source")
            gemini.assert_called_once()
            api.assert_called_once()

    def test_invalid_retry_count_fails_without_http(self):
        for count in (0, -1, True, "5"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                client.call_gemini("source", None, self.cfg, {"max_retries": count})
        self.transport.assert_not_called()

    def test_helper_uses_env_key_and_configured_models(self):
        with patch.object(gemini_helper, "load_config", return_value=self.config()), \
                patch.dict(gemini_helper.os.environ, {"GEMINI_API_KEY": "env-test-key"}), \
                patch.object(gemini_helper, "call_gemini", return_value=("ok", {"finish_reason": "STOP"}, "model")) as api:
            self.assertEqual(gemini_helper.ask_gemini("source", return_usage=True),
                             ("ok", {"finish_reason": "STOP"}))
            self.assertEqual(api.call_args.args[2]["api_keys"], ["env-test-key"])
            self.assertEqual(api.call_args.args[2]["models"], ["requested-gemini"])

    def test_helper_without_credentials_raises_and_never_sends_http(self):
        with patch.object(gemini_helper, "load_config", return_value={}), \
                patch.object(gemini_helper, "GEMINI_API_KEY", ""), \
                patch.dict(gemini_helper.os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                gemini_helper.ask_gemini("source")
        self.transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
