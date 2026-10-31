"""Keyless live web search, weather and headlines for JARVIS Desktop."""
from __future__ import annotations

from html.parser import HTMLParser
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


USER_AGENT = "JARVIS-Desktop/1.0 (Windows; personal assistant)"
MAX_RESPONSE_BYTES = 1_500_000
TIMEOUT_SECONDS = 12


def _read_url(url: str, opener=None, timeout: int = TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/rss+xml,application/json"})
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Online service returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Internet service is unavailable: {getattr(exc, 'reason', exc)}") from exc
    if len(payload) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Online response was too large; please narrow the request.")
    return payload


class _SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._active = None
        self._snippet = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        if tag == "a" and "result__a" in classes and len(self.results) < 6:
            href = attrs.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            parsed = urllib.parse.urlparse(href)
            if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
                target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
                href = target
                parsed = urllib.parse.urlparse(href)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                self._active = {"title": "", "url": href, "snippet": ""}
                self.results.append(self._active)
        elif self.results and "result__snippet" in classes:
            self._snippet = self.results[-1]

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return
        if self._active is not None:
            self._active["title"] = (self._active["title"] + " " + value).strip()
        elif self._snippet is not None:
            self._snippet["snippet"] = (self._snippet["snippet"] + " " + value).strip()

    def handle_endtag(self, tag):
        if tag == "a":
            self._active = None
        if tag in {"div", "td"}:
            self._snippet = None


def web_search(query: str, opener=None) -> str:
    query = " ".join(query.split()).strip()
    if not query or len(query) > 240:
        raise ValueError("Search query 1–240 characters ka hona chahiye.")
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    parser = _SearchParser()
    parser.feed(_read_url(url, opener).decode("utf-8", errors="replace"))
    results = [item for item in parser.results if item["title"]][:5]
    if not results:
        return f'Web search mein "{query}" ke liye readable results nahi mile. Browser mein search try karo.'
    lines = [f'Web results for: {query}']
    for index, item in enumerate(results, 1):
        title = re.sub(r"\s+", " ", item["title"]).strip()
        snippet = re.sub(r"\s+", " ", item["snippet"]).strip()
        lines.append(f"{index}. {title}")
        if snippet:
            lines.append(f"   {snippet[:350]}")
        lines.append(f"   {item['url']}")
    return "\n".join(lines)


def _xml_text(element, path: str) -> str:
    node = element.find(path)
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def get_news(query: str = "", opener=None) -> str:
    query = " ".join(query.split()).strip()
    if len(query) > 180:
        raise ValueError("News topic 180 characters se chhota rakho.")
    params = {"hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    base = "https://news.google.com/rss"
    if query:
        base += "/search"
        params["q"] = query
    url = base + "?" + urllib.parse.urlencode(params)
    try:
        root = ET.fromstring(_read_url(url, opener))
    except ET.ParseError as exc:
        raise RuntimeError("News feed ka response samajh nahi aaya.") from exc
    items = root.findall("./channel/item")[:6]
    if not items:
        return "Abhi news feed mein koi headline nahi mili."
    heading = "Latest India headlines" + (f" — {query}" if query else "")
    lines = [heading]
    for index, item in enumerate(items, 1):
        title = _xml_text(item, "title")
        source = _xml_text(item, "source")
        link = _xml_text(item, "link")
        published = _xml_text(item, "pubDate")
        if title:
            suffix = f" ({source})" if source else ""
            lines.append(f"{index}. {title}{suffix}")
            if published:
                lines.append(f"   {published[:45]}")
            if link and urllib.parse.urlparse(link).scheme == "https":
                lines.append(f"   {link}")
    return "\n".join(lines)


def get_weather(city: str, opener=None) -> str:
    city = " ".join(city.split()).strip(" ,.")
    if not city:
        return "Weather ke liye city batao — jaise: weather in Bhopal."
    if len(city) > 100:
        raise ValueError("City name bahut lamba hai.")
    geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": city, "count": 1, "language": "en", "format": "json"}
    )
    try:
        geo = json.loads(_read_url(geo_url, opener))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("Weather location service ka response invalid tha.") from exc
    places = geo.get("results") or []
    if not places:
        return f'"{city}" location nahi mili. City ka naam dobara check karo.'
    place = places[0]
    forecast_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m",
        "timezone": "auto",
    })
    try:
        forecast = json.loads(_read_url(forecast_url, opener))
        current = forecast["current"]
        units = forecast.get("current_units", {})
        temp = current["temperature_2m"]
        feels = current["apparent_temperature"]
        humidity = current["relative_humidity_2m"]
        wind = current["wind_speed_10m"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Weather data abhi available nahi hai.") from exc
    location = ", ".join(str(x) for x in [place.get("name"), place.get("admin1"), place.get("country")] if x)
    return (
        f"Current weather — {location}\n"
        f"Temperature: {temp}{units.get('temperature_2m', '°C')} "
        f"(feels like {feels}{units.get('apparent_temperature', '°C')})\n"
        f"Humidity: {humidity}{units.get('relative_humidity_2m', '%')}\n"
        f"Wind: {wind} {units.get('wind_speed_10m', 'km/h')}\n"
        f"Updated: {current.get('time', 'now')} ({forecast.get('timezone', 'local time')})"
    )


def parse_online_command(prompt: str) -> tuple[str, str] | None:
    text = " ".join(prompt.strip().split())
    lowered = text.casefold().strip(" ?.!।")
    for prefix in ("search web for ", "web search for ", "search the web for ",
                   "google search for ", "search for ", "search "):
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip()
            return ("search", query) if query else ("search", "")
    if lowered.startswith("google "):
        query = text[7:].strip()
        return ("search", query) if query else ("search", "")
    weather_prefixes = ("weather in ", "weather for ", "what is the weather in ",
                        "what's the weather in ", "mausam in ", "mausam ")
    if lowered in {"weather", "what is the weather", "what's the weather", "mausam", "aaj ka mausam"}:
        return ("weather", "")
    for prefix in weather_prefixes:
        if lowered.startswith(prefix):
            return ("weather", text[len(prefix):].strip())
    if lowered in {"latest news", "news", "headlines", "india news", "latest india news"}:
        return ("news", "")
    for prefix in ("news about ", "latest news about ", "headlines about ", "news on "):
        if lowered.startswith(prefix):
            return ("news", text[len(prefix):].strip())
    return None


def handle_online_command(prompt: str, opener=None) -> str | None:
    parsed = parse_online_command(prompt)
    if parsed is None:
        return None
    action, query = parsed
    if action == "search":
        if not query:
            return "Kya search karna hai? Example: search web for Python tutorials."
        return web_search(query, opener)
    if action == "weather":
        return get_weather(query, opener)
    return get_news(query, opener)
