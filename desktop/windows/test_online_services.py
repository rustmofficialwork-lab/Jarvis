import io
import json
import unittest
from urllib.parse import urlparse, parse_qs

from online_services import (
    get_news,
    get_weather,
    handle_online_command,
    parse_online_command,
    web_search,
)


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        payload = self.responses.pop(0)
        return io.BytesIO(payload if isinstance(payload, bytes) else payload.encode("utf-8"))


class OnlineServicesTests(unittest.TestCase):
    def test_search_command_parsing(self):
        self.assertEqual(parse_online_command("Search web for Python 3.13"), ("search", "Python 3.13"))
        self.assertEqual(parse_online_command("google latest AI news"), ("search", "latest AI news"))
        self.assertIsNone(parse_online_command("open notepad"))

    def test_weather_command_parsing_and_missing_city_prompt(self):
        self.assertEqual(parse_online_command("weather in Bhopal"), ("weather", "Bhopal"))
        self.assertEqual(parse_online_command("mausam"), ("weather", ""))
        self.assertIn("city batao", handle_online_command("weather").casefold())

    def test_news_command_parsing(self):
        self.assertEqual(parse_online_command("latest news"), ("news", ""))
        self.assertEqual(parse_online_command("news about technology"), ("news", "technology"))

    def test_web_search_formats_results_and_uses_encoded_query(self):
        html = """
        <div class="result">
          <a class="result__a" href="https://example.com/page">Example result</a>
          <a class="result__snippet">A useful summary.</a>
        </div>
        """
        opener = FakeOpener([html])
        result = web_search("python & windows", opener)
        self.assertIn("Example result", result)
        self.assertIn("A useful summary.", result)
        self.assertIn("https://example.com/page", result)
        request, timeout = opener.requests[0]
        self.assertEqual(parse_qs(urlparse(request.full_url).query)["q"], ["python & windows"])
        self.assertEqual(timeout, 12)

    def test_search_rejects_empty_or_oversized_queries(self):
        with self.assertRaises(ValueError):
            web_search(" ")
        with self.assertRaises(ValueError):
            web_search("x" * 241)

    def test_weather_uses_geocoding_then_current_forecast(self):
        geocoding = json.dumps({"results": [{
            "name": "Bhopal", "admin1": "Madhya Pradesh", "country": "India",
            "latitude": 23.25, "longitude": 77.41,
        }]})
        forecast = json.dumps({
            "timezone": "Asia/Kolkata",
            "current": {
                "temperature_2m": 31.2, "apparent_temperature": 33.0,
                "relative_humidity_2m": 48, "wind_speed_10m": 8.5,
                "time": "2026-10-31T13:00",
            },
            "current_units": {
                "temperature_2m": "°C", "apparent_temperature": "°C",
                "relative_humidity_2m": "%", "wind_speed_10m": "km/h",
            },
        })
        opener = FakeOpener([geocoding, forecast])
        result = get_weather("Bhopal", opener)
        self.assertIn("Bhopal, Madhya Pradesh, India", result)
        self.assertIn("31.2°C", result)
        self.assertIn("Humidity: 48%", result)
        self.assertEqual(len(opener.requests), 2)

    def test_weather_reports_unknown_city(self):
        opener = FakeOpener([json.dumps({"results": []})])
        self.assertIn("location nahi mili", get_weather("NoSuchCity", opener))

    def test_news_parses_headlines_and_sources(self):
        rss = """<?xml version="1.0"?>
        <rss><channel><item>
          <title>Sample headline</title><source>Example News</source>
          <link>https://example.com/story</link><pubDate>Sat, 31 Oct 2026 08:00:00 GMT</pubDate>
        </item></channel></rss>"""
        result = get_news("technology", FakeOpener([rss]))
        self.assertIn("Sample headline", result)
        self.assertIn("Example News", result)
        self.assertIn("https://example.com/story", result)

    def test_unmatched_prompt_does_not_call_online_service(self):
        self.assertIsNone(handle_online_command("Tell me a joke"))


if __name__ == "__main__":
    unittest.main()
