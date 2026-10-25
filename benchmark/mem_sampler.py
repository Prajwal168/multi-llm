"""
Background sampler for memory consumption on both inference hosts
(paper Section VI: latency, memory, token cost across BOTH hosts).

Polls Ollama's /api/ps on each host: `size` = total loaded model size,
`size_vram` = the part resident in GPU memory. The Ollama hosts' own OS
RAM is not visible through the API; if you need that, run
`nvidia-smi` / `free` on the hosts alongside. The harness process RSS
is recorded too when psutil is installed.
"""

import json
import threading
import time

from ollama import Client


class MemSampler:

    def __init__(self, hosts, path, interval=2.0):
        self.hosts = dict(hosts)   # {"control": url, "executor": url}
        self.path = path
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        try:
            import psutil
            proc = psutil.Process()
        except Exception:
            proc = None
        clients = {n: Client(host=h) for n, h in self.hosts.items()}
        with open(self.path, "a", encoding="utf-8") as f:
            while not self._stop.is_set():
                now = time.time()
                for name, c in clients.items():
                    try:
                        for m in c.ps().models:
                            f.write(json.dumps({
                                "t": now, "host": name,
                                "model": getattr(m, "model", None),
                                "size": getattr(m, "size", None),
                                "size_vram": getattr(m, "size_vram", None),
                            }) + "\n")
                    except Exception:
                        pass
                if proc is not None:
                    f.write(json.dumps({
                        "t": now, "host": "harness_process",
                        "rss": proc.memory_info().rss}) + "\n")
                f.flush()
                self._stop.wait(self.interval)
