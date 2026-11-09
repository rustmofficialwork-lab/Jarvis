import unittest

import httpx

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

    def test_rejects_invalid_provider_configuration(self):
        with self.assertRaises(ProviderConfigurationError):
            load_providers({"JARVIS_AI_PROVIDERS": "{not-json"})

    async def test_retries_rate_limited_provider_then_succeeds(self):
        env = {
            "JARVIS_AI_PROVIDERS": (
                '[{"name":"one","base_url":"https://one.example/v1/chat/completions",'
                '"api_key_env":"ONE_KEY","model":"model-one"},'
                '{"name":"two","base_url":"https://two.example/v1/chat/completions",'
                '"api_key_env":"TWO_KEY","model":"model-two"}]'
            ),
            "ONE_KEY": "secret-one",
            "TWO_KEY": "secret-two",
        }
        responses = [
            FakeResponse(429),
            FakeResponse(200, [b'{"choices":[] }']),
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
        self.assertEqual(result, b'{"choices":[] }')

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
