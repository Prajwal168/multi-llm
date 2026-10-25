"""
Non-invasive instrumentation. Nothing in the pipeline source is edited.

* Wraps ollama.Client.chat so EVERY model call (mediator, planner LLM,
  relevance gate, executor, verifier, baseline) logs prompt/completion
  tokens, latency, model and error. This closes the gap that only the
  Executor and Verifier printed token counts.
* Optional fault hook: raise an injected error before a call.
* Wraps requests.get/post to log web traffic, snapshot fetched pages
  (so web runs can be re-scored later), and optionally block DuckDuckGo
  to force the Tavily fallback.
"""

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

_lock = threading.Lock()
_calls = []
_web = []

fault_hook = None      # callable(stage) -> Exception | None
WEB_FAULTS = set()     # {"ddg"} blocks DuckDuckGo

_llm_installed = False
_web_installed = False
_snapshot_dir = None


def reset():
    with _lock:
        _calls.clear()
        _web.clear()


def snapshot():
    with _lock:
        return list(_calls), list(_web)


def _get(obj, key):
    if obj is None:
        return None
    try:
        return obj.get(key)
    except Exception:
        return getattr(obj, key, None)


def _record(stage, model, last, t0, err):
    with _lock:
        _calls.append({
            "stage": stage,
            "model": model,
            "prompt_tokens": _get(last, "prompt_eval_count"),
            "completion_tokens": _get(last, "eval_count"),
            "seconds": round(time.monotonic() - t0, 3),
            "error": None if err is None else f"{type(err).__name__}: {err}",
        })


def install_llm():
    global _llm_installed
    if _llm_installed:
        return
    import ollama

    orig = ollama.Client.chat

    def wrapped(self, *args, **kwargs):
        stage = os.path.basename(sys._getframe(1).f_code.co_filename)
        model = kwargs.get("model")
        t0 = time.monotonic()

        if fault_hook is not None:
            exc = fault_hook(stage)
            if exc is not None:
                _record(stage, model, None, t0, exc)
                raise exc

        if kwargs.get("stream"):
            inner = orig(self, *args, **kwargs)

            def gen():
                last, err = None, None
                try:
                    for chunk in inner:
                        last = chunk
                        yield chunk
                except Exception as e:
                    err = e
                    raise
                finally:
                    _record(stage, model, last, t0, err)

            return gen()

        try:
            res = orig(self, *args, **kwargs)
        except Exception as e:
            _record(stage, model, None, t0, e)
            raise
        _record(stage, model, res, t0, None)
        return res

    ollama.Client.chat = wrapped
    _llm_installed = True


def _log_web(method, url, status, t0, err):
    with _lock:
        _web.append({
            "method": method,
            "url": url,
            "status": status,
            "seconds": round(time.time() - t0, 3),
            "error": None if err is None else f"{type(err).__name__}: {err}",
        })


def install_web(snapshot_dir=None):
    global _web_installed, _snapshot_dir
    if snapshot_dir:
        _snapshot_dir = Path(snapshot_dir)
        _snapshot_dir.mkdir(parents=True, exist_ok=True)
    if _web_installed:
        return
    import requests

    orig_get, orig_post = requests.get, requests.post

    def get(url, *a, **kw):
        t0 = time.time()
        try:
            r = orig_get(url, *a, **kw)
        except Exception as e:
            _log_web("GET", url, None, t0, e)
            raise
        _log_web("GET", url, r.status_code, t0, None)
        if _snapshot_dir is not None and r.status_code == 200:
            key = hashlib.sha1(url.encode()).hexdigest()
            (_snapshot_dir / f"{key}.html").write_text(
                r.text, encoding="utf-8", errors="replace")
            (_snapshot_dir / f"{key}.json").write_text(json.dumps({
                "url": url,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }))
        return r

    def post(url, *a, **kw):
        t0 = time.time()
        if "ddg" in WEB_FAULTS and "duckduckgo" in url:
            e = requests.ConnectionError("injected DuckDuckGo outage")
            _log_web("POST", url, None, t0, e)
            raise e
        try:
            r = orig_post(url, *a, **kw)
        except Exception as e:
            _log_web("POST", url, None, t0, e)
            raise
        _log_web("POST", url, r.status_code, t0, None)
        return r

    requests.get, requests.post = get, post
    _web_installed = True
