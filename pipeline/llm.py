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
* Agent Platform (Vertex AI) route, for Google accounts whose API key is stuck on the free tier (Cornell): set
  GOOGLE_GENAI_USE_ENTERPRISE=true (or GOOGLE_GENAI_USE_VERTEXAI=true) and GOOGLE_CLOUD_PROJECT=<project id>, and
  optionally GOOGLE_CLOUD_LOCATION (default global), in the environment or in .env. Calls then go to
  aiplatform.googleapis.com with the access token of your Google sign-in (`gcloud auth application-default login`),
  read with the google-auth package if installed, else with `gcloud auth application-default print-access-token`.
  The API key is ignored on this route even when set. The token is kept in memory only, never printed or written.
  Same model IDs and the same cache (a cached response is reused whichever route made it). This route is billed
  per token and has no free-tier daily cap, so its default limits are 60 requests/min and 2000/day: set PRH_LLM_RPD
  lower as a spending guard. Token counts of every call are kept in cache/llm/usage.json (llm.tokens_today()).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
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


ROUTE_NAMES = ("GOOGLE_GENAI_USE_ENTERPRISE", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION")


def api_key():
    """The key from the environment, else from .env (simple KEY=VALUE lines, optional quotes/`export`). None if absent."""
    return _setting(KEY_NAME)


def _setting(name):
    """`name` from the environment, else from .env. Only KEY_NAME and ROUTE_NAMES are ever read from the file."""
    key = os.environ.get(name)
    if key:
        return key
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            key_name, sep, value = line.partition("=")
            if sep and key_name.strip() == name:
                value = value.strip()
                if value[:1] in "\"'" and len(value) > 1 and value[-1] == value[0]:
                    value = value[1:-1]
                else:
                    value = value.split(" #")[0].strip()
                return value or None
    return None


def route():
    """("agent_platform", project, location) when GOOGLE_GENAI_USE_ENTERPRISE/VERTEXAI is true and a project is set,
    else ("api_key", None, None)."""
    on = any((_setting(n) or "").strip().lower() in ("1", "true", "yes") for n in ROUTE_NAMES[:2])
    project = _setting("GOOGLE_CLOUD_PROJECT")
    if on and project:
        return "agent_platform", project.strip(), (_setting("GOOGLE_CLOUD_LOCATION") or "global").strip()
    return "api_key", None, None


def endpoint(model):
    kind, project, location = route()
    if kind == "api_key":
        return API.format(model=model)
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"


_TOKEN = {"value": None, "until": 0.0}


def access_token(refresh=False):
    """Access token of the Application Default Credentials (gcloud auth application-default login). Memory only."""
    if _TOKEN["value"] and not refresh and time.time() < _TOKEN["until"]:
        return _TOKEN["value"]
    token = None
    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        token = creds.token
    except Exception:  # noqa: BLE001  (package missing or no credentials: try gcloud)
        gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd")
        if gcloud:
            cp = subprocess.run([gcloud, "auth", "application-default", "print-access-token"],
                                capture_output=True, text=True)
            token = cp.stdout.strip() if cp.returncode == 0 else None
    if not token:
        raise SystemExit("llm: Agent Platform route is on (GOOGLE_GENAI_USE_ENTERPRISE) but no Google sign-in was found. "
                         "Run `gcloud auth application-default login` and `gcloud auth application-default "
                         "set-quota-project <project>` in this environment (WSL and Windows each keep their own).")
    _TOKEN.update(value=token, until=time.time() + 45 * 60)
    return token


def auth_headers(refresh=False):
    """Headers that authenticate one request on the active route, or None when there is no credential."""
    if route()[0] == "agent_platform":
        return {"Authorization": f"Bearer {access_token(refresh)}"}
    key = api_key()
    return {"x-goog-api-key": key} if key else None


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
    if route()[0] == "agent_platform":
        rpm, rpd = 60, 2000          # billed per token, no free-tier cap: PRH_LLM_RPD is the spending guard
    else:
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


def _record(calls, model, status=200, usage=None):
    calls.append({"t": time.time(), "model": model, "day": datetime.now(PACIFIC).date().isoformat(),
                  "status": status, "route": route()[0],
                  **({"in": usage.get("promptTokenCount", 0), "out": usage.get("candidatesTokenCount", 0)
                      + usage.get("thoughtsTokenCount", 0)} if usage else {})})
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / "usage.json.tmp"
    tmp.write_text(json.dumps({"calls": calls}))
    tmp.replace(CACHE / "usage.json")


def calls_today(model):
    """Requests that count against the daily budget. Server-side 5xx failures (model overloaded) are not counted;
    they are still recorded so RPM spacing sees them. Timeouts (status 0) are counted: the server may have finished."""
    day = datetime.now(PACIFIC).date().isoformat()
    return sum(1 for c in _usage() if c["model"] == model and c["day"] == day
               and not 500 <= c.get("status", 200) < 600)


def tokens_today(model=None):
    """(input tokens, output tokens incl. thinking) of today's (Pacific) uncached calls, for a cost estimate."""
    day = datetime.now(PACIFIC).date().isoformat()
    cs = [c for c in _usage() if c["day"] == day and (model is None or c["model"] == model)]
    return sum(c.get("in", 0) for c in cs), sum(c.get("out", 0) for c in cs)


def _wait_for_rpm(calls, model, rpm):
    while True:
        recent = sorted(c["t"] for c in calls if c["model"] == model and c["t"] > time.time() - 60)
        if len(recent) < rpm:
            return
        pause = recent[len(recent) - rpm] + 60.5 - time.time()
        print(f"llm: {rpm} requests/min reached, waiting {pause:.0f}s", file=sys.stderr)
        time.sleep(max(pause, 1))


def _post(model, payload, auth):
    """One HTTP call. -> (status, body text); status 0 = timeout or network error. Replaced by a fake in tests.
    auth: the headers from auth_headers() (a bare string is taken as an API key).
    Thinking models (e.g. gemini-3.8-flash) asked for 20 programs can take many minutes, hence the long timeout."""
    if isinstance(auth, str):
        auth = {"x-goog-api-key": auth}
    req = urllib.request.Request(endpoint(model), data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **auth})
    try:
        with urllib.request.urlopen(req, timeout=float(os.environ.get("PRH_LLM_TIMEOUT", 900))) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
        return 0, f"{type(e).__name__}: {e}"


def call(prompt, system=None, schema=None, model=None, temperature=0.2, max_output_tokens=32768, force=False):
    model = model or DEFAULT_MODEL
    request = {"model": model, "system": system, "prompt": prompt, "schema": schema,
               "temperature": temperature, "max_output_tokens": max_output_tokens}
    path = CACHE / "responses" / f"{_key(request)}.json"
    if path.is_file() and not force:
        hit = json.loads(path.read_text())
        return {**hit["response"], "model": model, "cached": True}

    auth = auth_headers()
    if not auth:
        raise SystemExit("llm: no API key. Put GEMINI_API_KEY=... in .env at the repo root (git-ignored) or export it, "
                         "or use the Agent Platform route (GOOGLE_GENAI_USE_ENTERPRISE=true, GOOGLE_CLOUD_PROJECT=...).")
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
        status, body = _post(model, payload, auth)
        if status == 401 and route()[0] == "agent_platform" and attempt < 5:   # token expired: get a fresh one
            _record(_usage(), model, status)
            auth = auth_headers(refresh=True)
            continue
        usage = None
        if status == 200:
            try:
                usage = json.loads(body).get("usageMetadata")
            except ValueError:
                pass
        _record(_usage(), model, status, usage)
        if status == 200:
            break
        low = body.lower()
        if status == 429 and ("perday" in low.replace(" ", "").replace("_", "") or "per day" in low):
            raise QuotaExhausted(f"{model}: the API reports the daily quota is exhausted; rerun after midnight Pacific.")
        if status in (0, 429, 500, 502, 503, 504) and attempt < 5:
            m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
            if m:
                pause = float(m.group(1)) + 1
            elif status == 429:
                pause = 10 * (attempt + 1)
            else:  # overloaded / timed out: back off exponentially so the model has time to recover
                pause = min(30 * 2 ** attempt, 300)
            what = "timeout/network error" if status == 0 else f"HTTP {status}"
            print(f"llm: {what}, retrying in {pause:.0f}s ({body[:120].strip()})", file=sys.stderr)
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
