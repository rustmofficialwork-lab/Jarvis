import json
import unittest

from app.provider_router import (
    ProviderConfigurationError,
    ProviderUnavailable,
    load_providers,
    request_with_failover,
)


class FakeResponse:
    def __init__(self, status_code, chunks=()):
        self.status_code = status_code
        self.chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


class FakeClient:
    def __init__(self, responses):
        self.responses = responses

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, *args, **kwargs):
        return self.responses.pop(0)


class ProviderRouterTests(unittest.IsolatedAsyncioTestCase):
    def test_legacy_openrouter_configuration_is_preserved(self):
        providers = load_providers({
            "OPENROUTER_API_KEY": "secret",
            "OPENROUTER_MODEL": "openrouter/free",
        })
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].name, "openrouter")
        self.assertEqual(providers[0].model, "openrouter/free")

    def test_unconfigured_provider_keys_are_skipped(self):
        env = {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"ONE_KEY","model":"model-one"}]'
            )
        }
        self.assertEqual(load_providers(env), [])

    def test_rejects_deeply_nested_provider_configuration(self):
        with self.assertRaises(ProviderConfigurationError):
            load_providers({"JARVIS_AI_PROVIDERS": "[" * 1100 + "0" + "]" * 1100})

    def test_rejects_invalid_provider_configuration(self):
        with self.assertRaises(ProviderConfigurationError):
            load_providers({"JARVIS_AI_PROVIDERS": "{not-json"})

    def test_rejects_more_than_five_configured_providers(self):
        entries = [
            {
                "name": f"provider-{index}",
                "base_url": f"https://provider-{index}.example/v1/chat/completions",
                "api_key_env": f"KEY_{index}",
                "model": "test-model",
            }
            for index in range(6)
        ]
        with self.assertRaisesRegex(ProviderConfigurationError, "At most 5"):
            load_providers({"JARVIS_AI_PROVIDERS": json.dumps(entries)})

    def test_rejects_invalid_api_key_environment_variable_name(self):
        env = {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"BAD-KEY-NAME","model":"model-one"}]'
            ),
            "BAD-KEY-NAME": "secret",
        }
        with self.assertRaisesRegex(ProviderConfigurationError, "environment variable name"):
            load_providers(env)

    def test_rejects_duplicate_provider_names_case_insensitively(self):
        entries = [
            {
                "name": name,
                "base_url": f"https://provider-{index}.example/v1/chat/completions",
                "api_key_env": f"KEY_{index}",
                "model": "test-model",
            }
            for index, name in enumerate(("Primary", "primary"))
        ]
        env = {"JARVIS_AI_PROVIDERS": json.dumps(entries), "KEY_0": "a", "KEY_1": "b"}
        with self.assertRaisesRegex(ProviderConfigurationError, "unique"):
            load_providers(env)

    def test_rejects_provider_url_credentials_and_malformed_https_urls(self):
        for url in (
            "https://user:password@provider.example/v1/chat/completions",
            "https:///v1/chat/completions",
            "https://provider.example:99999/v1/chat/completions",
            "http://provider.example/v1/chat/completions",
        ):
            with self.subTest(url=url):
                env = {
                    "JARVIS_AI_PROVIDERS": (
                        '[{"name":"one","base_url":' + json.dumps(url) +
                        ',"api_key_env":"ONE_KEY","model":"model-one"}]'
                    ),
                    "ONE_KEY": "secret",
                }
                with self.assertRaises(ProviderConfigurationError):
                    load_providers(env)

    @staticmethod
    def _two_provider_environment():
        return {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"ONE_KEY","model":"model-one"},'
                '{"name":"two","base_url":"https://two.example/v1/chat/completions",'
                '"api_key_env":"TWO_KEY","model":"model-two"}]'
            ),
            "ONE_KEY": "secret-one",
            "TWO_KEY": "secret-two",
        }

    async def test_retries_rate_limited_provider_then_succeeds(self):
        env = self._two_provider_environment()
        expected = b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        responses = [FakeResponse(429), FakeResponse(200, [expected])]

        def factory(**kwargs):
            return FakeClient(responses)

        result = await request_with_failover(
            {"messages": [{"role": "user", "content": "hello"}]},
            timeout=5,
            max_response_bytes=1024,
            environ=env,
            client_factory=factory,
        )
        self.assertEqual(result, expected)

    async def test_retries_provider_specific_missing_model_then_succeeds(self):
        env = self._two_provider_environment()
        expected = b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        responses = [FakeResponse(404), FakeResponse(200, [expected])]

        def factory(**kwargs):
            return FakeClient(responses)

        result = await request_with_failover(
            {"messages": [{"role": "user", "content": "hello"}]},
            timeout=5,
            max_response_bytes=1024,
            environ=env,
            client_factory=factory,
        )
        self.assertEqual(result, expected)

    async def test_retries_malformed_success_response_then_succeeds(self):
        env = self._two_provider_environment()
        expected = b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        responses = [
            FakeResponse(200, [b"upstream proxy error page"]),
            FakeResponse(200, [expected]),
        ]

        def factory(**kwargs):
            return FakeClient(responses)

        result = await request_with_failover(
            {"messages": [{"role": "user", "content": "hello"}]},
            timeout=5,
            max_response_bytes=1024,
            environ=env,
            client_factory=factory,
        )
        self.assertEqual(result, expected)

    async def test_retries_empty_message_response_then_succeeds(self):
        env = self._two_provider_environment()
        expected = b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}'
        responses = [
            FakeResponse(200, [b'{"choices":[{"message":{}}]}']),
            FakeResponse(200, [expected]),
        ]

        def factory(**kwargs):
            return FakeClient(responses)

        result = await request_with_failover(
            {"messages": [{"role": "user", "content": "hello"}]},
            timeout=5,
            max_response_bytes=1024,
            environ=env,
            client_factory=factory,
        )
        self.assertEqual(result, expected)

    async def test_rejects_malformed_success_when_no_fallback_is_configured(self):
        env = {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"ONE_KEY","model":"model-one"}]'
            ),
            "ONE_KEY": "secret-one",
        }

        def factory(**kwargs):
            return FakeClient([FakeResponse(200, [b"not-json"])])

        with self.assertRaisesRegex(ProviderUnavailable, "temporarily unavailable"):
            await request_with_failover(
                {"messages": [{"role": "user", "content": "hello"}]},
                timeout=5,
                max_response_bytes=1024,
                environ=env,
                client_factory=factory,
            )

    async def test_stops_on_non_retryable_bad_request(self):
        env = {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"ONE_KEY","model":"model-one"}]'
            ),
            "ONE_KEY": "secret-one",
        }

        def factory(**kwargs):
            return FakeClient([FakeResponse(400)])

        with self.assertRaises(ProviderUnavailable):
            await request_with_failover(
                {"messages": [{"role": "user", "content": "hello"}]},
                timeout=5,
                max_response_bytes=1024,
                environ=env,
                client_factory=factory,
            )


if __name__ == "__main__":
    unittest.main()
