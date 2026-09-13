"""
Phase 1 — build a substantially harder evaluation set.

The previous negative set was too easy: out-of-domain questions ("how long to
roast a chicken") sit far from any slide by construction, so separating them
proves little. This builds negatives that share vocabulary with the corpus.

METHODOLOGY NOTE — absence is verified LEXICALLY, never with dense similarity.
Dense distance is the signal under test in Phase 3; using it to label the data
would guarantee separation by construction and prove nothing. Every negative
here is labelled by checking that the required terms appear ZERO times in the
target subject's slide text, which is independent of any embedding.

Negative classes, hardest last:
  out_of_domain          another field entirely (kept as a control)
  cross_subject_overlap  a real question from subject A asked against B, where
                         the query shares vocabulary with B but B contains none
                         of the gold slide's actual concepts
  in_subject_absent      a topic that plausibly belongs to the subject but does
                         not occur in the corpus at all

Positive classes (gold slide unchanged, so no new labels are invented):
  positive               the original evaluation question
  positive_noisy         typos and informal phrasing, as a student would type
  positive_keyword       reduced to bare keywords
  positive_verbose       padded with filler

Read-only against the corpus. Writes only to experiments/benchmarks/.
"""

import json
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory   # noqa: E402
from indexing.models import Slide              # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
EVAL_SET = REPO / "eval" / "eval_set.json"
RNG = random.Random(20260913)

# Topics that plausibly belong to each subject. Every one is CHECKED against
# the corpus below; only those that genuinely do not occur are kept.
CANDIDATE_ABSENT = {
    "CN": ["QUIC protocol", "HTTP/3", "BGP hijacking", "MPLS label switching",
           "software defined networking", "OpenFlow", "DNSSEC validation",
           "WebRTC signalling", "VLAN trunking", "NAT traversal"],
    "DBMS": ["CAP theorem", "multiversion concurrency control", "database sharding",
             "LSM tree compaction", "two-phase commit protocol", "columnar storage",
             "materialized view refresh", "vector clocks"],
    "ML": ["transformer attention", "generative adversarial network", "dropout regularization",
           "batch normalization", "LSTM gating", "word2vec embeddings",
           "reinforcement learning reward", "BERT pretraining"],
    "OPERATING SYSTEM": ["container namespaces", "cgroups resource limits",
                         "copy-on-write fork", "NUMA memory locality",
                         "type-1 hypervisor", "microkernel message passing"],
    "DAA": ["Dijkstra shortest path", "Floyd-Warshall algorithm", "red-black tree balancing",
            "suffix array construction", "maximum network flow", "NP-completeness reduction"],
    "CA": ["MESI cache coherence", "branch prediction", "superscalar issue",
           "out-of-order execution", "SIMD vectorization", "speculative execution"],
    "SE": ["continuous integration pipeline", "pair programming", "technical debt",
           "code review checklist", "scrum sprint planning"],
}

STOP = set("what how why is are the a an of in on for to and or not does do can which "
           "when where who explain describe define tell me about between with from that "
           "this it its their there they be been being has have had will would should".split())


def terms(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 3 and w not in STOP}


# ── deterministic query degradations (gold slide is unchanged) ───────────

def make_noisy(q):
    """Typos and informal phrasing, as a student actually types."""
    out = q.lower().replace("what is", "whats").replace("explain", "expalin")
    words = out.split()
    if len(words) > 4:
        i = RNG.randrange(2, len(words))
        w = words[i]
        if len(w) > 4:                      # transpose two characters
            j = RNG.randrange(1, len(w) - 2)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words).rstrip("?")


def make_keyword(q):
    ws = [w for w in re.findall(r"[A-Za-z0-9]+", q) if w.lower() not in STOP]
    return " ".join(ws[:6])


def make_verbose(q):
    return ("hi, i was going through the slides for my exam and i got a bit confused, "
            f"could you please help me understand this: {q} thanks a lot")


def main():
    session = SessionFactory()
    subjects = sorted({r[0] for r in session.query(Slide.subject)
                       .filter(Slide.is_embedded == True).distinct().all() if r[0]})  # noqa: E712

    # Lexical inventory per subject — the independent basis for every
    # absence claim in this file.
    vocab, slide_terms, freq = {}, {}, {}
    for s in subjects:
        rows = session.query(Slide.id, Slide.summary, Slide.concepts, Slide.raw_text).filter(
            Slide.subject == s, Slide.is_embedded == True).all()  # noqa: E712
        words, counter = set(), {}
        for r in rows:
            toks = re.findall(r"[a-z0-9]+",
                              f"{r[1] or ''} {r[2] or ''} {r[3] or ''}".lower())
            for tk in toks:
                counter[tk] = counter.get(tk, 0) + 1
            tset = terms(f"{r[1] or ''} {r[2] or ''} {r[3] or ''}")
            slide_terms[r[0]] = tset
            words |= tset
        vocab[s] = words
        freq[s] = counter
    print(f"subjects: {len(subjects)}, vocabulary sizes: "
          f"{ {s: len(v) for s, v in vocab.items()} }\n")

    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    items = []

    # ── positives, four phrasings of each ────────────────────────────────
    for qa in eval_set:
        base = dict(subject=qa["subject"], answerable=True,
                    gold_slide_id=qa["gold_slide_id"])
        items.append({**base, "id": f"pos_{qa['id']}", "category": "positive",
                      "question": qa["question"]})
        items.append({**base, "id": f"noisy_{qa['id']}", "category": "positive_noisy",
                      "question": make_noisy(qa["question"])})
        items.append({**base, "id": f"kw_{qa['id']}", "category": "positive_keyword",
                      "question": make_keyword(qa["question"])})
        items.append({**base, "id": f"verb_{qa['id']}", "category": "positive_verbose",
                      "question": make_verbose(qa["question"])})

    # ── in_subject_absent — hardest negatives ────────────────────────────
    kept_absent, rejected_absent = 0, []
    for subject, topics in CANDIDATE_ABSENT.items():
        if subject not in vocab:
            continue
        for topic in topics:
            tt = terms(topic)
            if not tt:
                continue
            # Anchor on the topic's RAREST term - the one carrying its identity.
            # "MPLS label switching" is absent when 'mpls' is absent, even though
            # 'switching' is common; "QUIC protocol" is NOT absent because 'quic'
            # occurs 65 times. Judging on any-overlap discarded good negatives.
            counts = {w: freq[subject].get(w, 0) for w in tt}
            anchor = min(counts, key=counts.get)
            if counts[anchor] > 0:           # the corpus DOES cover it
                rejected_absent.append((subject, topic,
                                        f"anchor '{anchor}' occurs {counts[anchor]}x"))
                continue
            items.append({
                "id": f"neg_absent_{subject.replace(' ', '_')}_{kept_absent}",
                "question": f"Explain {topic} as covered in this subject.",
                "subject": subject, "answerable": False,
                "category": "in_subject_absent", "gold_slide_id": None,
                "verification": {"method": "lexical-anchor", "terms": sorted(tt),
                                 "anchor_term": anchor,
                                 "anchor_occurrences_in_subject": 0},
            })
            kept_absent += 1

    # ── cross_subject_overlap — query overlaps target, content does not ──
    kept_cross = 0
    for qa in eval_set:
        src, gold = qa["subject"], qa["gold_slide_id"]
        gold_terms = slide_terms.get(gold, set())
        if not gold_terms:
            continue
        q_terms = terms(qa["question"])
        for target in subjects:
            if target == src:
                continue
            # HARD: the question's wording overlaps the target subject ...
            q_overlap = q_terms & vocab[target]
            # ... but none of the gold slide's distinctive content is there.
            distinctive = gold_terms - vocab[target]
            coverage = 1 - (len(distinctive) / len(gold_terms))
            if len(q_overlap) >= 2 and coverage < 0.5:
                items.append({
                    "id": f"neg_cross_{qa['id']}_{target.replace(' ', '_')}",
                    "question": qa["question"], "subject": target,
                    "answerable": False, "category": "cross_subject_overlap",
                    "gold_slide_id": None, "source_subject": src,
                    "verification": {"method": "lexical",
                                     "query_terms_shared_with_target": sorted(q_overlap),
                                     "gold_content_coverage_in_target": round(coverage, 3)},
                })
                kept_cross += 1
                break

    # ── out_of_domain control ────────────────────────────────────────────
    prev = REPO / "experiments" / "benchmarks" / "r1_negative_probes.json"
    kept_ood = 0
    if prev.exists():
        for p in json.loads(prev.read_text(encoding="utf-8")):
            if p["category"] == "out_of_domain":
                items.append({"id": p["id"], "question": p["question"],
                              "subject": p["subject"], "answerable": False,
                              "category": "out_of_domain", "gold_slide_id": None,
                              "verification": {"method": "different field"}})
                kept_ood += 1

    session.close()

    counts = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    print("evaluation set built:")
    for c, n in sorted(counts.items()):
        print(f"  {c:24s} {n:4d}")
    n_pos = sum(1 for i in items if i["answerable"])
    print(f"\n  total {len(items)}  ({n_pos} answerable / {len(items)-n_pos} not)")

    print(f"\nin_subject_absent: {kept_absent} kept, {len(rejected_absent)} rejected "
          f"because the corpus DOES cover them:")
    for s, tp, why in rejected_absent[:8]:
        print(f"    {s:18s} {tp:34s} {why}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
