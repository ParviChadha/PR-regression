"""Gemini client shared by generate.py, fix.py and classify.py. Standard library only (no SDK to install).

    from llm import call, QuotaExhausted
    r = call(prompt, system=..., schema=..., model=...)    # -> {"text", "usage", "model", "cached"}

* Key: GEMINI_API_KEY from the environment, else from a line `GEMINI_API_KEY=...` in the git-ignored `.env` at the
  repo root (only that one name is read from the file). It is sent in an HTTP header and never printed, logged,
  cached or written anywhere. Without it a call raises SystemExit (cached responses still work without a key).
* Cache: every response is stored in cache/llm/responses/<sha256 of the request>.json (git-ignored). An identical
  request is answered from disk, so reruns cost nothing and a quota stop can be resumed the next day.
* Budget: calls are spaced to stay under the model's requests per minute, and counted per Pacific-time day
  (quotas reset at midnight Pacific) in cache/llm/usage.json. When the daily budget is spent, QuotaExhausted is
  raised BEFORE any call is made; a 429 that names a per-day quota raises it too. Per-minute 429s are waited out.
  Single process at a time: the usage file is not locked.
* Limits are the free-tier numbers third-party sites reported reading AI Studio in Oct 2026; Google's docs do not
  print them (see https://aistudio.google.com/rate-limit for your project). Override with PRH_LLM_RPM / PRH_LLM_RPD.
* Default model gemini-3.5-flash-lite (free tier); PRH_LLM_MODEL or the model argument change it.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "llm"
ENV_FILE = ROOT / ".env"
KEY_NAME = "GEMINI_API_KEY"


def api_key():
    """The key from the environment, else from .env (simple KEY=VALUE lines, optional quotes/`export`). None if absent."""
    key = os.environ.get(KEY_NAME)
    if key:
        return key
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, sep, value = line.partition("=")
            if sep and name.strip() == KEY_NAME:
                value = value.strip()
                if value[:1] in "\"'" and len(value) > 1 and value[-1] == value[0]:
                    value = value[1:-1]
                else:
                    value = value.split(" #")[0].strip()
                return value or None
    return None
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = os.environ.get("PRH_LLM_MODEL", "gemini-3.5-flash-lite")
LIMITS = {  # model -> (requests per minute, requests per day), free tier
    "gemini-3.8-flash": (5, 20),
    "gemini-3.5-flash-lite": (15, 500),
    "gemini-3.1-flash-lite": (15, 500),
}
PACIFIC = ZoneInfo("America/Los_Angeles")


class QuotaExhausted(Exception):
    """The daily request budget for this model is spent; rerun after midnight Pacific (cache makes that cheap)."""


def limits(model):
    rpm, rpd = LIMITS.get(model, (5, 20))  # unknown model: assume the strictest known limits
    return int(os.environ.get("PRH_LLM_RPM", rpm)), int(os.environ.get("PRH_LLM_RPD", rpd))


def _key(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


def _usage():
    path = CACHE / "usage.json"
    try:
        calls = json.loads(path.read_text())["calls"]
    except (OSError, ValueError, KeyError):
        calls = []
    cutoff = time.time() - 3 * 86400
    return [c for c in calls if c["t"] > cutoff]


def _record(calls, model):
    calls.append({"t": time.time(), "model": model, "day": datetime.now(PACIFIC).date().isoformat()})
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / "usage.json.tmp"
    tmp.write_text(json.dumps({"calls": calls}))
    tmp.replace(CACHE / "usage.json")


def calls_today(model):
    day = datetime.now(PACIFIC).date().isoformat()
    return sum(1 for c in _usage() if c["model"] == model and c["day"] == day)


def _wait_for_rpm(calls, model, rpm):
    while True:
        recent = sorted(c["t"] for c in calls if c["model"] == model and c["t"] > time.time() - 60)
        if len(recent) < rpm:
            return
        pause = recent[len(recent) - rpm] + 60.5 - time.time()
        print(f"llm: {rpm} requests/min reached, waiting {pause:.0f}s", file=sys.stderr)
        time.sleep(max(pause, 1))


def _post(model, payload, key):
    """One HTTP call. -> (status, body text). Replaced by a fake in tests."""
    req = urllib.request.Request(API.format(model=model), data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def call(prompt, system=None, schema=None, model=None, temperature=0.2, max_output_tokens=32768, force=False):
    model = model or DEFAULT_MODEL
    request = {"model": model, "system": system, "prompt": prompt, "schema": schema,
               "temperature": temperature, "max_output_tokens": max_output_tokens}
    path = CACHE / "responses" / f"{_key(request)}.json"
    if path.is_file() and not force:
        hit = json.loads(path.read_text())
        return {**hit["response"], "model": model, "cached": True}

    key = api_key()
    if not key:
        raise SystemExit("llm: no API key. Put GEMINI_API_KEY=... in .env at the repo root (git-ignored) or export it.")
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens}}
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    if schema:
        payload["generationConfig"].update({"responseMimeType": "application/json", "responseSchema": schema})
    rpm, rpd = limits(model)

    for attempt in range(6):
        calls = _usage()
        if calls_today(model) >= rpd:
            raise QuotaExhausted(f"{model}: {rpd} requests used today (Pacific time); resumes after midnight Pacific. "
                                 f"Cached responses are kept, so rerun the same command then.")
        _wait_for_rpm(calls, model, rpm)
        status, body = _post(model, payload, key)
        _record(_usage(), model)
        if status == 200:
            break
        low = body.lower()
        if status == 429 and ("perday" in low.replace(" ", "").replace("_", "") or "per day" in low):
            raise QuotaExhausted(f"{model}: the API reports the daily quota is exhausted; rerun after midnight Pacific.")
        if status in (429, 500, 503) and attempt < 5:
            m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
            pause = float(m.group(1)) + 1 if m else 10 * (attempt + 1)
            print(f"llm: HTTP {status}, retrying in {pause:.0f}s", file=sys.stderr)
            time.sleep(pause)
            continue
        raise SystemExit(f"llm: HTTP {status} from {model}: {body[:600]}")

    data = json.loads(body)
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    response = {"text": text, "finish_reason": cand.get("finishReason"), "usage": data.get("usageMetadata", {})}
    if not text:
        raise SystemExit(f"llm: empty response from {model} (finishReason={cand.get('finishReason')}, "
                         f"promptFeedback={data.get('promptFeedback')})")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request": request, "response": response, "ts": time.time()}, indent=1))
    return {**response, "model": model, "cached": False}
