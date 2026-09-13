"""
P2 — Ollama concurrency benchmark.

Question: does raising concurrency against Ollama increase useful throughput,
and where does it stop helping? This is the suspected reason the system
becomes unhealthy above ~3 Celery workers.

Isolated: talks only to the Ollama HTTP API. Touches no database, no
production module, no user data.

Usage:  python experiments/concurrency/p2_ollama_concurrency.py
Writes: experiments/benchmarks/p2_ollama_concurrency.json
"""

import json
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

OLLAMA = "http://127.0.0.1:11434"
MODEL = "llama3"
LEVELS = [1, 2, 3, 4, 5, 6, 8]
REQUESTS_PER_SLOT = 2          # each concurrency slot handles this many
NUM_PREDICT = 128
TIMEOUT = 300

OUT = Path(__file__).resolve().parents[1] / "benchmarks" / "p2_ollama_concurrency.json"

# Representative of the real ingest-cleanup call, trimmed so a sweep is
# affordable. What matters here is the SHAPE of the throughput curve.
PROMPT = (
    "You are a strict transcription cleaner. Clean this lecture slide text, "
    "output only the cleaned text.\n---\nTheta Notation: It is denoted by O, a "
    "method of representing running time between upper and lower bound. Let f(n) "
    "and g(n) be non-negative functions.\n---\nCleaned text:"
)


def ram_available_gib():
    """Available system RAM. Ollama needs ~4.3 GiB of SYSTEM memory to load
    llama3 even though it executes on the GPU, so this is a confound that has
    to be recorded alongside every level rather than assumed constant."""
    try:
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "[math]::Round((Get-CimInstance Win32_OperatingSystem)."
            "FreePhysicalMemory/1MB,2)"], text=True).strip()
        return float(out)
    except Exception:
        return None


def gpu_sample():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
             "--format=csv,noheader,nounits"], text=True).strip()
        u, m = [int(x) for x in out.split(",")]
        return u, m
    except Exception:
        return None, None


class GpuMonitor:
    """Samples GPU utilisation and VRAM while a level runs."""

    def __init__(self, interval=0.25):
        self.interval = interval
        self._stop = threading.Event()
        self.util, self.vram = [], []

    def __enter__(self):
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            u, m = gpu_sample()
            if u is not None:
                self.util.append(u)
                self.vram.append(m)
            time.sleep(self.interval)

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(timeout=2)

    def summary(self):
        if not self.util:
            return {}
        return {
            "gpu_util_mean": round(statistics.mean(self.util), 1),
            "gpu_util_max": max(self.util),
            "vram_mb_max": max(self.vram),
        }


def one_request():
    t = time.perf_counter()
    try:
        r = requests.post(f"{OLLAMA}/api/generate", json={
            "model": MODEL, "prompt": PROMPT, "stream": False,
            "options": {"temperature": 0.0, "num_predict": NUM_PREDICT},
        }, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return {"ok": True, "sec": time.perf_counter() - t,
                "eval_count": d.get("eval_count", 0)}
    except Exception as exc:
        return {"ok": False, "sec": time.perf_counter() - t,
                "error": type(exc).__name__, "eval_count": 0}


def run_level(concurrency: int) -> dict:
    n = concurrency * REQUESTS_PER_SLOT
    ram_before = ram_available_gib()
    with GpuMonitor() as mon:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(pool.map(lambda _: one_request(), range(n)))
        wall = time.perf_counter() - start

    ok = [r for r in results if r["ok"]]
    errors = {}
    for r in results:
        if not r["ok"]:
            errors[r["error"]] = errors.get(r["error"], 0) + 1
    lat = sorted(r["sec"] for r in ok)
    tokens = sum(r["eval_count"] for r in ok)
    row = {
        "concurrency": concurrency,
        "ram_avail_gib_before": ram_before,
        "ram_avail_gib_after": ram_available_gib(),
        "requests": n,
        "succeeded": len(ok),
        "failed": n - len(ok),
        "wall_sec": round(wall, 2),
        "throughput_rps": round(len(ok) / wall, 3) if wall else 0,
        "tokens_per_sec": round(tokens / wall, 1) if wall else 0,
        "p50_sec": round(statistics.median(lat), 2) if lat else None,
        "p95_sec": round(lat[int(len(lat) * 0.95)], 2) if lat else None,
        "max_sec": round(lat[-1], 2) if lat else None,
        "errors": errors,
        **mon.summary(),
    }
    return row


def main():
    print(f"P2 — Ollama concurrency, model={MODEL}, {REQUESTS_PER_SLOT} req/slot\n")
    # Warm the model so level 1 is not penalised by a cold load.
    one_request()

    rows = []
    hdr = (f"{'C':>2s} {'reqs':>5s} {'wall_s':>7s} {'rps':>6s} {'tok/s':>7s} "
           f"{'p50_s':>6s} {'p95_s':>6s} {'gpu%':>5s} {'vram':>6s} {'ramGiB':>7s} {'fail':>5s}")
    print(hdr)
    print("-" * len(hdr))
    for c in LEVELS:
        row = run_level(c)
        rows.append(row)
        if row["errors"]:
            print(f"     errors at C={row['concurrency']}: {row['errors']}")
        print(f"{row['concurrency']:>2d} {row['requests']:>5d} {row['wall_sec']:>7.1f} "
              f"{row['throughput_rps']:>6.2f} {row['tokens_per_sec']:>7.1f} "
              f"{(row['p50_sec'] if row['p50_sec'] is not None else float('nan')):>6.2f} "
              f"{(row['p95_sec'] if row['p95_sec'] is not None else float('nan')):>6.2f} "
              f"{row.get('gpu_util_mean', 0):>5.0f} {row.get('vram_mb_max', 0):>6d} "
              f"{(row['ram_avail_gib_before'] or 0):>7.1f} {row['failed']:>5d}")

    rows_ok = [r for r in rows if r["succeeded"]]
    if not rows_ok:
        print("\nEVERY level failed - see errors above (likely host RAM exhaustion)")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"levels": rows}, indent=2), encoding="utf-8")
        return
    best = max(rows_ok, key=lambda r: r["throughput_rps"])
    base = rows_ok[0]["throughput_rps"]
    print(f"\npeak throughput at concurrency={best['concurrency']} "
          f"({best['throughput_rps']} rps, {best['throughput_rps']/base:.2f}x over C=1)")
    print("latency cost at peak: p50 "
          f"{rows[0]['p50_sec']}s -> {best['p50_sec']}s")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"levels": rows, "model": MODEL,
                               "requests_per_slot": REQUESTS_PER_SLOT,
                               "num_predict": NUM_PREDICT}, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
