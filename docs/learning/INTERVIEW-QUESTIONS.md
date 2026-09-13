# ExamPrep AI — interview preparation

> Questions an interviewer will actually ask about **this** repository, with
> answers grounded in what was built and measured.
>
> Use it as a self-test: read the question, answer out loud, *then* look.

Background: [`AI-RAG.md`](AI-RAG.md) · [`SYSTEM-DESIGN.md`](SYSTEM-DESIGN.md)

---

## How to use the strongest material

Three stories are worth having ready, because they demonstrate judgement rather
than knowledge:

1. **"I found a confidence gate that mathematically could not return low
   confidence."** (the RRF bug — §AI 5)
2. **"My best result vanished on an independent evaluation set."** (query
   rewriting — §AI 11)
3. **"Raising concurrency made it slower, and the reason was memory, not
   contention."** (Ollama — §SD 11)

Each is: hypothesis → measurement → surprising result → decision.

---

# Part 1 — AI / ML

### Why RAG instead of fine-tuning?

The corpus changes every time a student uploads a deck — fine-tuning per upload
is absurd. More importantly, **the product is provenance.** A student needs
"page 62 of CH2.pdf says this", because the exam is set from the slides. A
fine-tuned model gives you fluent text with no citation. RAG keeps the evidence
addressable.

### Why hybrid retrieval? Isn't dense enough?

They fail in **opposite directions**. Dense handles paraphrase ("avoid network
overload" → congestion control) and is vague on rare exact tokens. BM25 nails
`FIQ` and scores zero on paraphrase.

Measured over 114 questions: dense alone R@1 **0.640**, sparse alone **0.640**,
hybrid **0.667** with MRR 0.723 vs 0.687/0.696. Neither is redundant.

### Why embeddings? What does the model actually do?

It maps text to a 1024-dim vector so similar meanings land near each other, and
similarity becomes geometry. We use `intfloat/e5-large-v2`, which requires
instruction prefixes — `query: ` and `passage: ` — because it was trained that
way; omitting them degrades quality.

### Why ChromaDB?

Embedded, zero-ops, metadata filtering inside the query (critical — every search
is subject-filtered *before* vectors are compared). At this scale a managed
vector DB would be operational overhead for no benefit.
**Limitation:** approximate search, and changing the embedding model invalidates
every stored vector because the spaces are unrelated.

### Explain RRF.

`score(doc) = Σ 1 / (K + rank_in_that_list)`, K = 60. It fuses ranked lists
using only **rank**, never score — because a cosine distance and a BM25 score
aren't comparable units, and normalising them is corpus-dependent and fiddly.

### 🔑 Is the RRF score a confidence score?

**No, and assuming it was is a real bug I found in this codebase.**

A rank-1 hit scores `1/61 = 0.0164`, or `2/61 = 0.0328` if both retrievers found
it — **regardless of whether the match is perfect or absurd.** Rank 1 is rank 1
even when every candidate is garbage.

Production had a coverage gate thresholding that score at 0.025/0.015. The
`"low"` branch was **unreachable**, because the minimum rank-1 score (0.0164) is
already above 0.015. Replaying 31 real user queries: `covered=true` for **31/31**,
including "kaju katli" (an Indian sweet) against the Machine Learning corpus.

The signal that *does* separate them — raw cosine distance — was being discarded
by the fusion. Nonsense queries sat at 0.206–0.299; real ones at 0.125–0.163.

### Did you tune RRF's K?

Yes, and it didn't matter — flat from K=5 to K=120. Same for candidate pool size
(flat from 5 to 120) and weighted fusion (ties RRF at best). **Three tuning
avenues closed with measurements**, which is worth as much as a win: nobody
should spend time there.

### Why not use a cross-encoder reranker?

Tested and rejected: **quality went down and latency went up.** A reranker is
the textbook next move, which is exactly why measuring it mattered.

### Why did query rewriting fail? (the best story)

Hypothesis: strip conversational filler and retrieval improves. Five
deterministic rewrites, paired bootstrap over 250 items: the best variant showed
+0.027 balanced accuracy, 95% CI [+0.009, +0.051], P(better) **99.9%**.
Established, by any normal standard.

Then I built an evaluation set from real instructor-written exam questions —
sharing no lineage with my generated set. **The effect was exactly zero**, and
R@1 moved the wrong way (0.706 → 0.676).

The mechanism, in hindsight: the measured gain came from stripping filler out of
*verbose* test queries — filler **I had written into the test set**. Real exam
questions have no padding, so there was nothing to remove except signal.

**The arithmetic was right; the question was too narrow.**

### How do you evaluate retrieval?

- **Recall@K** — is the right slide in the top K?
- **Gold-in-context** — did it survive into the prompt? (0.842 at top-6) This is
  the true ceiling on answer quality.
- **MRR** — 1/rank of the first hit; rewards ranking it *first*.
- **nDCG@5** — position-discounted, handles multiple relevant slides.

Critically: **never label evaluation data with the signal you're testing.** To
test whether dense distance detects absent topics, absence was verified
*lexically* — the term occurs zero times in the slide text. Labelling with
distance would have guaranteed the answer.

### How do you evaluate grounding, and how is it different from correctness?

An answer can be **correct but ungrounded**: true, but the model knew it and the
slide never said it. For exam prep that's dangerous — the student thinks they're
reading their syllabus.

Measured over 45 answers: correctness **96%** when the gold slide reached the
LLM, but only **8/30** answers fully grounded, **83%** carrying at least one
unsupported claim, and **97** unsupported claims total.

**So retrieval bounds correctness; generation bounds trustworthiness.**

### How can citation hallucination happen? How would you prevent it?

It happened here. Asked about absent topics, the model invented
`sdn_chapter.pdf` and `cap_theory.pdf` — documents that never existed.

**Why it's possible:** the citation is free text in prose. Nothing constrains it
to a document that was supplied.

**The fix:** label supplied sources `[S1]…[S6]`, instruct the model to cite only
those labels, and have the backend map a label to the real file and page. A
citation to something not supplied becomes **unrepresentable** rather than
discouraged — and any stray label is mechanically detectable. The general
principle: *don't ask a model to be disciplined about something you can make
structurally impossible.*

### What should happen when evidence is insufficient?

Currently the system answers anyway **33%** of the time, with citations. Three
obvious fixes were tested and rejected:

- **Dense-distance threshold** — 0.941 balanced accuracy on constructed data,
  but real student queries are short (median **5 words** vs 13) and short queries
  sit further from the corpus. At the fitted threshold, **52% of genuinely
  answerable real queries would be refused.** Unshippable.
- **RRF threshold** — it's a rank. No information.
- **Agentic RAG as default** — worse at answering (below).

One promising signal: an agent declined **75%** of absent-topic questions where
baseline declined **0%**. Adding the agent's "you may decline" sentence to the
baseline prompt did *not* reproduce it (0/4), so the advantage looks
architectural — but **n=4**, so it's suggestive, not proven.

### Why did agentic RAG fail?

Three systems on 17 hard queries, same model:

| | Correct | Grounded | Citations | Tokens |
|---|---|---|---|---|
| baseline | **1.53** | **2.00** | **3.0** | 1.00× |
| iterative | 1.47 | 1.94 | 3.6 | 1.19× |
| agentic | 0.94 | 0.94 | 0.1 | **2.36×** |

It lost **9 of 17** head-to-head, was *worse* on the multi-slide questions that
were its best case, and nearly stopped citing slides — which for a study tool is
its own failure.

### So when *would* you use an agent?

As a **detector, not a generator.** The architecture is good at noticing it has
nothing and bad at everything else. "Is this answerable?" is a different problem
from "write the answer", and only the first plays to its strength — at 2.36×
cost for a check that fires rarely, which is a very different trade from paying
it on every query.

### Why Gemini *and* Groq *and* Ollama?

Different jobs, different constraints:

| | Job | Why |
|---|---|---|
| **Ollama** (local) | Per-slide cleanup at ingestion | 690 calls per corpus — no quota, no per-call cost |
| **Gemini** | Structured slide classification | Large context, structured output, generous free tier |
| **Groq** | Answering user questions | Latency — the user is waiting |

### How do you control token cost?

Context capped at **6 slides** (~743 tokens) — measured knee: top-10 buys 1.8
points of recall for 63% more tokens. Two-level caching so repeats and
paraphrases never reach an LLM. And rejecting agentic RAG saved 2.36× on every
query it would have touched.

### How do you measure latency, and what dominates?

Retrieval ~95 ms p50; LLM generation 1.3–12 s. **The LLM is 10–100× everything
else.**

One honest caveat: absolute latency on this machine is **not reproducible** — I
measured retrieval p50 at 88.6, 95.7, 97.6, 101.0 and 116.9 ms across one
session, because the GPU clocks down to 600 MHz (from 2100 MHz) when idle. Only
paired, same-process comparisons are trustworthy, so that's what conclusions
rest on.

---

# Part 2 — Backend / SDE

### Why FastAPI?

Async-native (an answer is mostly *waiting* on an LLM — `await` frees the thread),
Pydantic validation at the boundary so bad input fails with 422 instead of a
`KeyError` deep in a handler, and free OpenAPI docs.

**Honest caveat:** retrieval underneath is synchronous CPU/GPU work and does not
yield. That's deliberate — retrieval is ~1% of request time.

### Why Celery? What if a worker crashes mid-task?

Ingestion takes minutes; an HTTP request can't wait, and the job must survive a
restart.

On crash: `task_acks_late=True` means the broker never got an acknowledgement,
so the message is redelivered. `task_reject_on_worker_lost=True` makes that
happen on a hard kill. If nothing picks it up, a recovery pass marks it failed
so the UI stops showing false progress. **The cost:** tasks must be safe to run
twice.

### Why `prefetch_multiplier=1`?

By default a worker reserves a batch of tasks. With long jobs, one worker hoards
several while another idles. Fetching one at a time gives fair scheduling.

### Why Redis? What if it goes down?

Separate processes need somewhere to **agree**. Two workers each tracking "I've
made 5 of 10 allowed calls" are both right locally and wrong globally.

On outage: **uploads break** (no broker), **questions degrade** (the limiter and
semaphore fall back to in-process versions — still working, but limits are now
per-process), **cache misses** (slower, still correct). The fallback is
deliberate: *a cache outage should not be an outage*.

### How does your rate limiting work?

Sliding window on a Redis **sorted set** scored by timestamp: prune entries older
than the window, count what's left, add yourself if there's room. A fixed window
would allow 2× the limit across a boundary.

### 🔑 Is there a race condition in it?

**Yes — and it's a textbook check-then-act.** The prune-and-count is one
pipeline; the `zadd` is a separate command. Between them another worker can also
count, also see room, and also add. The limit is briefly exceeded.

**The correct pattern is already in the same file.** The distributed semaphore
uses a Lua script — Redis executes Lua atomically, so prune, check and claim are
one indivisible operation:

```lua
redis.call('ZREMRANGEBYSCORE', key, '-inf', stale_thr)
if redis.call('ZCARD', key) < max_c then
    redis.call('ZADD', key, now, holder)
    return 1
end
return 0
```

I'd move the limiter to the same approach.

### How do you avoid deadlock if a semaphore holder dies?

Entries are scored by timestamp and **pruned if older than the TTL**. A crashed
holder releases its slot automatically. Without that, one hard kill permanently
reduces capacity.

### Why SQLite? Why not PostgreSQL?

Because I measured it. 960 transactions across 1–8 concurrent writers:
**zero lock failures at every level**, throughput rising to **91 txn/s**.
Against an LLM stage consuming **0.56 req/s**, SQLite has ~**163×** the headroom
the pipeline can use.

Postgres would add an operational dependency for capacity that isn't needed.
**I'd switch when** multiple API hosts need shared access, or replication/
failover matters — neither of which is a throughput argument.

### What is WAL and why use it?

Write-Ahead Logging. In the default rollback journal a writer blocks readers. In
WAL, writes append to a separate log so **readers never block**. Measured at 8
writers: WAL's worst-case latency 1492 ms vs the rollback journal's 3122 ms —
about half the tail.

### What's `busy_timeout`?

When the write lock is held, wait up to 30 s instead of immediately raising
"database is locked". One line that removes most transient failures — and it's
why the contention benchmark saw zero errors.

### Why `NullPool` instead of connection pooling?

Deliberate. SQLite connections are cheap, and sharing one across threads causes
subtle corruption. With a `threads` Celery pool, giving each thread a fresh
connection is the safe choice.

### Why these indexes?

Index what you filter on. `subject` on documents and slides (**every** query is
subject-filtered — the hottest filter), `file_hash` unique (dedup on every
upload), `query_hash` unique (the L1 cache lookup), `doc_id` (fetch a document's
slides).

**The interesting one:** `pyq_matches.slide_id` has its own index even though
it's part of the composite primary key `(pyq_id, slide_id)`. A composite index
on `(A, B)` can serve lookups by `A` — not by `B` alone, the same way a phone
book sorted by surname can't find people by first name.

**Cost:** every index is updated on every write and consumes disk.

### How does caching work? What about invalidation?

L1 hashes the exact normalised query. L2 embeds the query and matches
paraphrases by cosine similarity above 0.85. Invalidation is by **content
fingerprint** — when a subject's slides change, its cached answers are stale. A
cache keyed only on the query would serve answers about deleted documents.

**Cache stampede is not handled** — 50 simultaneous misses would all call the
LLM. At this traffic it's never been the constraint, and the distributed
semaphore caps concurrent LLM calls, which blunts the worst case.

### Why SSE and not WebSockets?

Progress flows **one way**. SSE is plain HTTP, reconnects automatically, and
passes proxies cleanly. WebSockets add bidirectional machinery for a
unidirectional problem.

**Limitations:** each stream holds a connection, browsers cap concurrent
connections per origin on HTTP/1.1, and the implementation polls the DB every
~2 s — so freshness is bounded by the poll, not true push.

### What happens when an LLM call fails?

Depends on **why**, and that distinction is the fix I shipped:

| | 429 | 404 |
|---|---|---|
| Means | too fast right now | model no longer exists |
| Recovers alone? | yes, seconds | **never** |
| Response | block 60 s, try next | retire it, fall through, surface it |

Two of three configured Groq models were decommissioned and returned 404. The
pool caught 429 and **re-raised everything else** — so **67% of requests failed**
(measured: 4 of 6), and reasoning mode failed **100%** because it was
initialised with the dead model and had no round-robin.

Fix: treat 404 as fallback-worthy, retire the model for the process, never hand
a known-dead model to the agent, and add `GET /api/health/models` comparing
configured ids against the provider's live list. **Verified: 6/6 succeed.**

### How would you scale this 100×?

The honest answer is that **the database is not what breaks first — the GPU is.**
Ingestion is LLM-bound (per-slide cleanup is ~**25×** all other indexing stages
combined) and one process already saturates the card at 97% utilisation.

So: separate **model serving** from application serving first (vLLM/TGI on a
dedicated host). Then object storage for uploads (local disk stops being shared
the moment there's a second worker host), then Postgres when multiple API hosts
need shared writes, then a managed vector DB, Redis cluster, and distributed
tracing.

**Resisting the rewrite is the point.** I have measurements saying SQLite,
Chroma and BM25 have enormous headroom.

### What are the actual bottlenecks?

1. **GPU inference** — ingestion LLM calls, 25× everything else
2. **LLM generation latency** — 10–100× retrieval on the query path
3. **Retrieval quality ceiling** — gold-in-context 0.842; the remaining 16% is
   the real quality limit
4. Nothing else is close — SQLite 0.5% of indexing, BM25 0.2%

### Why is Celery concurrency 2 and not 8?

Measured: throughput peaks at 2 (0.56 rps, 1.27× over 1) then **declines** while
p50 latency grows 4.9×, because one request already occupies 97% of the GPU.

Above ~3 workers it wasn't contention at all —
`model requires more system memory (4.3 GiB) than is available (3.4 GiB)`.
Ollama plus one embedder already holds 95% of a 6 GB card. **More workers would
have been strictly worse.**

### How do you test something that calls an LLM?

You don't — you stub the boundary. The model-fallback suite proves the 404 path
with a stub client that raises whatever status you ask for: no key, no network,
milliseconds, deterministic. A test that hits Groq isn't a test, it's a network
check that fails when the provider hiccups.

**Test vs benchmark:** retrieval *quality* is a benchmark (a number, corpus-
dependent, lives in `experiments/`); retrieval *determinism* is a test
(pass/fail, lives in `tests/`). Mixing them gives a suite that fails for no
reason.

### What's a bug you found that surprised you?

Two, both about **non-determinism and false confidence**:

**RRF ties are structural.** A slide found only by dense at rank *i* scores
exactly the same as one found only by sparse at rank *i*. Python's sort is
stable, so ordering depended on set iteration order — which depends on
`PYTHONHASHSEED`. **The same query returned different results in different
processes.** Fixed with an explicit tie-break on `(doc_id, page_number)`.

**A health probe taking 2 seconds.** Not Redis — `localhost` resolves to IPv6
`::1` first, Redis isn't listening there, and each new connection waited for
that to time out. 2053 ms via `localhost`, 29 ms via `127.0.0.1`.

---

# Part 3 — Architecture trade-offs

For each: *why this, why not X, benefit, drawback, failure mode, scaling limit.*

| Choice | Why | Why not the alternative | Drawback | Fails when | Scaling limit |
|---|---|---|---|---|---|
| **FastAPI** | Async, validation, docs | Flask: no async, no validation | Retrieval still sync | — | Fine for a long time |
| **Celery + Redis** | Durable queue, crash recovery | In-process threads lose work on restart | Another service | Redis down → no uploads | Single broker |
| **SQLite + WAL** | Zero-ops, ACID, measured 163× headroom | Postgres: ops cost for unneeded capacity | Single writer, single host | Multiple API hosts | ~91 txn/s |
| **ChromaDB** | Embedded, metadata filtering in-query | Managed: overhead at this scale | Model change ⇒ full re-embed | Corpus > memory | Single node |
| **BM25 in-memory** | Simple, fast, cached on content hash | Elasticsearch: heavyweight | Rebuilt on start | Corpus growth | Memory |
| **RRF** | Rank-based, no score normalisation | Weighted: measured to tie | **Discards magnitude** — no confidence | Needing a confidence signal | — |
| **e5-large-v2** | Strong quality, local, no API cost | Smaller: −0.125 R@1 measured | 24 layers ⇒ launch-bound | — | GPU-bound |
| **Ollama local** | No quota, no per-call cost for 690 calls | API: expensive at ingestion scale | Slow, shares the GPU | GPU contention | Concurrency 2 |
| **Groq pool** | Low latency for user-facing answers | Single model: no fallback | Provider-side model churn | **404s — happened** | Rate limits |
| **SSE** | One-way, auto-reconnect, plain HTTP | WebSockets: bidirectional machinery unused | Holds a connection | Many concurrent streams | Connections per origin |
| **No auth** | Single-user tool | — | **Cannot deploy multi-tenant** | Any second user | Immediate |

---

## The closing question: what would you do next?

In order, and each justified by a measurement rather than a preference:

1. **Ship the source-ID citation scheme** — citation hallucination is the
   failure with the clearest user harm and the cleanest structural fix.
2. **Re-measure not-found detection at a larger sample** — the 75%-vs-0% result
   is the most promising open signal and rests on n=4.
3. **Fix the coverage boolean** — it's right 38% of the time while the LLM's own
   prose in the same response is right 67%, at zero extra cost.
4. **Make the rate limiter atomic** — the correct pattern is already in the file.

And what I would **not** do: tune RRF, enlarge the candidate pool, add a
reranker, add query rewriting, or make the agent the default. All measured, all
rejected.
