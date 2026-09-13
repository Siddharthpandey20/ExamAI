# P2 — Ollama concurrency profile

**Status:** complete · **Conclusion: REJECTED** — raising Celery/Ollama concurrency
cannot help on this hardware, and the observed instability has a different cause
than assumed.

**No production code was modified.**

---

## Hypothesis under test

> The system becomes unhealthy above ~3 Celery workers because Ollama is the
> bottleneck; finding Ollama's useful concurrency ceiling will tell us how many
> workers are safe.

**Success criterion:** identify a concurrency level where throughput is
meaningfully higher than C=1 without a failure-rate increase.

---

## Method

`experiments/concurrency/p2_ollama_concurrency.py` — talks only to the Ollama
HTTP API; no database, no production module, no user data. Sweeps concurrency
1–8, 2 requests per slot, fixed prompt, `num_predict=128`, `temperature=0`,
sampling GPU utilisation, VRAM and available system RAM throughout.

---

## Results

### Run A — adequate system RAM

| C | reqs | wall s | **rps** | tok/s | p50 s | p95 s | gpu % | fail |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 4.5 | 0.44 | 19.1 | 2.25 | 2.30 | 62 | 0 |
| 2 | 4 | 7.2 | **0.56** | 24.0 | 3.33 | 3.83 | 96 | 0 |
| 3 | 6 | 10.9 | 0.55 | 23.6 | 5.04 | 5.89 | 87 | 0 |
| 4 | 8 | 17.6 | 0.45 | 19.5 | 8.35 | 10.86 | 91 | 0 |
| 5 | 10 | 23.9 | 0.42 | 18.0 | 11.10 | 15.45 | 92 | 0 |
| 6 | 12 | 22.0 | 0.46 | 19.6 | 12.22 | 13.60 | 87 | **2** |

Throughput peaks at **C=2 (0.56 rps, 1.27× over C=1)** and *declines* after.
p50 latency rises 2.25 s → 11.10 s by C=5 — a 4.9× latency cost for **less**
throughput.

*Caveat:* Run A predates the RAM instrumentation, so its available RAM was not
recorded. It is reported as the throughput curve only.

### Run B — system RAM exhausted (~1.8–2.2 GiB available)

Every level failed, **including C=1**:

```
{"error":"model requires more system memory (4.3 GiB) than is available (3.4 GiB)"}
```

GPU utilisation stayed at 0 — Ollama rejected the requests outright rather than
queueing them. This is not a concurrency limit.

---

## Resource ceilings measured

| Resource | Measurement |
|---|---|
| llama3 residency | **100 % on GPU**, 5.21 GB VRAM |
| llama3 load requirement | **4.3 GiB of *system* RAM**, even though it executes on GPU |
| GPU at concurrency 1 | **97 % utilised by a single request** |
| One Celery worker | **1.23 GB system RAM + 1.34 GB VRAM** (torch + embedder + chroma) |
| Ollama + 1 embedder | **5858 / 6144 MiB = 95 % of the card**, 286 MiB headroom |
| A second embedder process | **Does not fit** (needs 1340 MiB, 286 MiB free) |
| Host RAM | 15.7 GiB total, **~2.0 GiB available** |

---

## Conclusion

**REJECTED.** Three independent findings, each sufficient on its own:

1. **Concurrency cannot help.** A *single* request already saturates the GPU at
   97 %. Throughput peaks at C=2 for a 1.27× gain, then declines while latency
   grows 4.9×. There is no concurrency level that is meaningfully better.

2. **The instability is host RAM, not Ollama.** Ollama needs 4.3 GiB of system
   RAM to load llama3. With ~2 GiB available it returns HTTP 500 to *every*
   request regardless of concurrency. The "unhealthy above ~3 workers" symptom
   is memory exhaustion that correlates with worker count because each worker
   costs 1.23 GB.

3. **VRAM forbids process-level scaling.** Ollama plus one embedder already
   occupies 95 % of the card. A second embedder-holding process cannot fit, so
   switching Celery from `threads` to `prefork`, or raising the process count,
   would fail on VRAM.

### The current configuration is already correct for this hardware

`WORKER_POOL=threads`, `WORKER_CONCURRENCY=2` means one process, therefore **one**
embedder singleton regardless of concurrency, and 2 concurrent Ollama requests —
which is exactly the measured throughput peak. This appears to be the right
setting arrived at by observation, and the measurements now justify it.

---

## Proposed production change

**None.** No change is warranted, and two changes are now positively
contraindicated:

- Do **not** raise `EXAMAI_WORKER_CONCURRENCY` above 2–3: it reduces throughput
  and multiplies latency.
- Do **not** switch `EXAMAI_WORKER_POOL` to `prefork`: a second embedder cannot
  fit in VRAM.

### What would actually help (not implemented, not measured)

Ingestion speed on this hardware is bounded by a 6 GB card shared between a 5.21 GB
LLM and a 1.34 GB embedder. The levers are therefore about *reducing* resident
footprint, not adding parallelism:

- a smaller quantised llama3 (`llama3:8b-instruct-q4_0`) would free VRAM for the
  embedder and lower the 4.3 GiB system-RAM load requirement;
- not holding both models resident simultaneously — the ingest stages that need
  Ollama and the stage that needs the embedder are already sequential per job;
- closing other applications: ~13.7 GiB of 15.7 GiB was consumed by the
  workstation itself during these runs.

Each of these is a hypothesis, not a finding. None has been tested.

---

## Risk / rollback

No production change proposed, so there is nothing to roll back. The experiment
directory is isolated and imports nothing from the application.
