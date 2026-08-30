"""
The model adapter.

One job: send a prompt, get text back, and record everything so the run can be
replayed later without an API key. That recording is what protects the pass or
fail reproducibility gate. A judge with no key runs the same command, the cached
responses replay, and the headline number comes out identical.

Modes:
  live    always call the API and write the response to the cache
  replay  never call the API, fail loudly if a response is not cached
  auto    replay when cached, otherwise call the API (the default while building)
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

from . import providers

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CACHE_DIR = os.path.join(_PROJECT_ROOT, "data", "model_cache")
MANIFEST_NAME = "manifest.json"


_SUPPORTED_KWARGS_CACHE = {}


def supported_create_kwargs(client):
    """Ask the installed SDK which optional arguments messages.create accepts.

    The SDK changed between major versions: temperature and the other sampling
    controls were removed in 1.x. Rather than pin ourselves to one SDK, we look
    at the real signature and send only what it understands. This keeps the
    project runnable on whatever version a judge happens to install.
    """
    key = type(client).__name__
    if key in _SUPPORTED_KWARGS_CACHE:
        return _SUPPORTED_KWARGS_CACHE[key]
    try:
        import inspect

        names = set(inspect.signature(client.messages.create).parameters)
    except (TypeError, ValueError):
        names = set()
    _SUPPORTED_KWARGS_CACHE[key] = names
    return names


class ModelError(RuntimeError):
    pass


@dataclass
class ModelResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    from_cache: bool

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_seconds": round(self.latency_seconds, 3),
            "from_cache": self.from_cache,
            "text": self.text,
        }


class ModelClient:
    def __init__(self, model=None, mode="auto", cache_dir=None, max_retries=3,
                 provider=None, region=None):
        if mode not in ("live", "replay", "auto"):
            raise ValueError("mode must be live, replay or auto")
        self.provider = (provider or providers.DEFAULT_PROVIDER).strip().lower()
        self.region = region
        self.mode = mode
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        # Replaying must not require a judge to know which provider recorded the
        # run. The cache key includes the model name, so a judge who simply runs
        # --mode replay would otherwise miss every entry and see a failure. The
        # manifest records which model the recordings came from, and replay uses
        # it unless a model was named explicitly.
        if model is None and mode == "replay":
            recorded = self._recorded_model()
            if recorded:
                model = recorded
        self.model = model or providers.default_model(self.provider)
        self.max_retries = max_retries
        self.nonce = ""  # set per sample so repeat runs do not overwrite each other
        self.calls_made = 0
        self.cache_hits = 0
        self._client = None
        os.makedirs(self.cache_dir, exist_ok=True)

    def _manifest_path(self):
        return os.path.join(self.cache_dir, MANIFEST_NAME)

    def _recorded_model(self):
        """Which model produced the responses sitting in the cache."""
        path = os.path.join(self.cache_dir or DEFAULT_CACHE_DIR, MANIFEST_NAME)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle).get("model") or None
        except (OSError, ValueError, AttributeError):
            return None

    def _write_manifest(self):
        try:
            with open(self._manifest_path(), "w", encoding="utf-8") as handle:
                json.dump({"model": self.model, "provider": self.provider}, handle, indent=2)
        except OSError:
            pass  # a missing manifest degrades replay, it must never break a run

    def _key(self, system, user, max_tokens, temperature):
        payload = {
            "model": self.model,
            "system": system,
            "user": user,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.nonce:
            payload["nonce"] = self.nonce
        blob = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def _cache_path(self, key):
        return os.path.join(self.cache_dir, key + ".json")

    def _read_cache(self, key) -> Optional[ModelResponse]:
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return None
        return ModelResponse(
            text=payload["text"],
            model=payload.get("model", self.model),
            input_tokens=int(payload.get("input_tokens", 0)),
            output_tokens=int(payload.get("output_tokens", 0)),
            latency_seconds=float(payload.get("latency_seconds", 0.0)),
            from_cache=True,
        )

    def _write_cache(self, key, response, system, user):
        payload = response.to_dict()
        payload["from_cache"] = False
        payload["prompt_sha256"] = key
        payload["system_preview"] = system[:400]
        payload["user_preview"] = user[:400]
        with open(self._cache_path(key), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self._write_manifest()

    def _api(self):
        if self._client is not None:
            return self._client
        try:
            self._client = providers.build_client(self.provider, self.region)
        except providers.ProviderError as exc:
            raise ModelError(str(exc)) from exc
        return self._client

    def _call_live(self, system, user, max_tokens, temperature) -> ModelResponse:
        client = self._api()
        supported = supported_create_kwargs(client)
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        # Older SDKs take temperature. 1.x removed it. Send it only if it fits.
        if "temperature" in supported:
            kwargs["temperature"] = temperature

        last_error = None
        for attempt in range(self.max_retries):
            started = time.time()
            try:
                message = client.messages.create(**kwargs)
                text = "".join(
                    block.text
                    for block in message.content
                    if getattr(block, "type", "") == "text"
                )
                self.calls_made += 1
                return ModelResponse(
                    text=text,
                    model=self.model,
                    input_tokens=message.usage.input_tokens,
                    output_tokens=message.usage.output_tokens,
                    latency_seconds=time.time() - started,
                    from_cache=False,
                )
            except TypeError as exc:
                raise ModelError(
                    "This SDK version rejected an argument: %s. The call was built "
                    "from its own signature, so this is a bug worth reporting." % exc
                ) from exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                text = str(exc).lower()
                if "use case details" in text or "use case form" in text:
                    raise ModelError(
                        "Bedrock is holding this account back, not the code.\n\n"
                        "Amazon requires an Anthropic use case details form per AWS "
                        "account before it will serve Anthropic models. Open the "
                        "Bedrock console, go to Model access, and submit it:\n"
                        "  https://us-east-1.console.aws.amazon.com/bedrock/home"
                        "?region=us-east-1#/modelaccess\n\n"
                        "Approval is usually minutes, and Amazon itself says to retry "
                        "after 15. Nothing in this project needs changing.\n"
                        "Model attempted: %s" % self.model
                    ) from exc
                # Credentials first. A missing AWS profile raises ProfileNotFound,
                # whose class name contains "NotFound", so the model name branch
                # below used to catch it and blame the model. An error message
                # that names the wrong cause costs more time than no message.
                if "profile" in text and ("not found" in text or "could not be found" in text):
                    raise ModelError(
                        "AWS cannot find that profile, so nothing was sent to Bedrock.\n\n"
                        "Original error: %s\n\n"
                        "List the profiles you actually have with:\n"
                        "  aws configure list-profiles\n"
                        "then set the one you want BEFORE running the command:\n"
                        '  $env:AWS_PROFILE = "the-real-name"\n'
                        "The model name was never the problem." % exc
                    ) from exc
                if "unable to locate credentials" in text or "nocredential" in text.replace(" ", ""):
                    raise ModelError(
                        "AWS has no credentials in this terminal.\n\n"
                        "Original error: %s\n\n"
                        'Set a profile with $env:AWS_PROFILE = "your-profile", or run '
                        "aws configure, or switch to --provider anthropic with an API key, "
                        "or run with --mode replay and use the recorded responses." % exc
                    ) from exc
                if ("not_found" in text or "NotFound" in type(exc).__name__) and "model" in text:
                    raise ModelError(
                        "The API rejected the model name %r. Set CLOUDFIX_MODEL or pass "
                        "--model with a model your account can reach. Original error: %s"
                        % (self.model, exc)
                    ) from exc
                if attempt == self.max_retries - 1:
                    break
                time.sleep(2 ** attempt)
        raise ModelError(
            "Model call failed after %d attempts: %s" % (self.max_retries, last_error)
        )

    def complete(self, system, user, max_tokens=2000, temperature=0.0) -> ModelResponse:
        key = self._key(system, user, max_tokens, temperature)

        if self.mode in ("auto", "replay"):
            cached = self._read_cache(key)
            if cached is not None:
                self.cache_hits += 1
                return cached
            if self.mode == "replay":
                raise ModelError(
                    "No recorded response for this prompt (%s) and mode is replay. "
                    "Run once with --mode live to record it." % key
                )

        response = self._call_live(system, user, max_tokens, temperature)
        self._write_cache(key, response, system, user)
        return response


# Published rates in USD per million tokens, used only for the cost per review
# line in the evaluation report. Override with CLOUDFIX_PRICE_IN and
# CLOUDFIX_PRICE_OUT.
PRICE_PER_MTOK_INPUT = float(os.environ.get("CLOUDFIX_PRICE_IN", "3.0"))
PRICE_PER_MTOK_OUTPUT = float(os.environ.get("CLOUDFIX_PRICE_OUT", "15.0"))


def estimate_cost_usd(input_tokens, output_tokens):
    return (
        input_tokens / 1000000.0 * PRICE_PER_MTOK_INPUT
        + output_tokens / 1000000.0 * PRICE_PER_MTOK_OUTPUT
    )
