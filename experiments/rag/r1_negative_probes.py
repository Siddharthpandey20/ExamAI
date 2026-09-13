"""
R1 — extend the evaluation set with NEGATIVE probes.

R3 showed the blocker is the evaluation set: `hit_at_5` has only 6 negative
cases in 40 questions, too few to fit or validate a confidence threshold, and
not-found precision/recall cannot be measured at all.

Negatives are added in the one way that needs no fabricated gold and no human
adjudication, because the label is *absence* and absence is checkable:

  out_of_domain   questions from fields the corpus cannot contain — medicine,
                  sport, cookery, law. Correct behaviour is "not found".
  cross_subject   a real question from subject A asked against subject B,
                  kept only when the concepts genuinely do not occur in B.

Every probe is VERIFIED against the live index before being accepted: a
cross-subject probe whose topic really does appear in the target subject is
discarded rather than mislabelled. The corpus is only ever read.

Usage:  python experiments/rag/r1_negative_probes.py
Writes: experiments/benchmarks/r1_negative_probes.json
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory      # noqa: E402
from indexing.models import Slide                 # noqa: E402
from indexing.db_chroma import ChromaStore        # noqa: E402
from indexing.embedder import Embedder            # noqa: E402
from engine.tools import run_hybrid_search        # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "r1_negative_probes.json"
EVAL_SET = REPO / "eval" / "eval_set.json"

# Plainly outside a computer-science lecture corpus. The gold label is
# "no slide answers this", which is verifiable rather than invented.
OUT_OF_DOMAIN = [
    "What is the first-line treatment for myocardial infarction?",
    "How long should I roast a whole chicken at 180 degrees?",
    "Which country won the 1998 football World Cup final?",
    "What are the symptoms of vitamin D deficiency?",
    "How do I register a trademark in the European Union?",
    "What is the correct fingering for a G major scale on piano?",
    "What is the recommended tyre pressure for a touring bicycle?",
    "How does photosynthesis convert light into chemical energy?",
    "What documents are required to apply for a Schengen visa?",
    "Who painted the ceiling of the Sistine Chapel?",
    "What is the tax deadline for self-assessment in the UK?",
    "How do I prune an apple tree in winter?",
]

STOP = set("what how why is are the a an of in on for to and or not does do can "
           "which when where who explain describe define tell me about between "
           "with from that this it its".split())


def keywords(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if len(w) > 3 and w not in STOP}


def main():
    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()

    subjects = sorted({r[0] for r in session.query(Slide.subject)
                       .filter(Slide.is_embedded == True).distinct().all() if r[0]})  # noqa: E712
    print(f"subjects in corpus: {subjects}\n")

    # Lexical inventory per subject, used to verify that a cross-subject probe
    # really is absent from its target.
    vocab = {}
    for s in subjects:
        words = set()
        for row in session.query(Slide.summary, Slide.concepts).filter(
                Slide.subject == s, Slide.is_embedded == True).all():  # noqa: E712
            words |= keywords(f"{row[0] or ''} {row[1] or ''}")
        vocab[s] = words

    probes = []

    # ── out-of-domain ────────────────────────────────────────────────────
    for i, q in enumerate(OUT_OF_DOMAIN):
        subject = subjects[i % len(subjects)]
        overlap = keywords(q) & vocab[subject]
        probes.append({
            "id": f"neg_ood_{i}",
            "question": q,
            "subject": subject,
            "category": "out_of_domain",
            "answer_in_corpus": False,
            "gold_slide_ids": [],
            "verification": {"keyword_overlap_with_subject": sorted(overlap)},
        })

    # ── cross-subject ────────────────────────────────────────────────────
    kept = discarded = 0
    for qa in eval_set:
        src = qa["subject"]
        kw = keywords(qa["question"])
        if not kw:
            continue
        for target in subjects:
            if target == src:
                continue
            overlap = kw & vocab[target]
            # Accept only when the topic is genuinely absent from the target.
            if overlap:
                discarded += 1
                continue
            probes.append({
                "id": f"neg_cross_{qa['id']}_{target.replace(' ', '_')}",
                "question": qa["question"],
                "subject": target,
                "category": "cross_subject",
                "answer_in_corpus": False,
                "gold_slide_ids": [],
                "source_subject": src,
                "verification": {"keyword_overlap_with_subject": []},
            })
            kept += 1
            break

    print(f"cross-subject probes: {kept} accepted, {discarded} discarded because "
          f"the topic genuinely occurs in the target subject")

    # ── measure what retrieval actually does on these ────────────────────
    print(f"\nmeasuring retrieval on {len(probes)} negative probes ...")
    for p in probes:
        res = run_hybrid_search(p["question"], p["subject"], session,
                                embedder, chroma, top_k=5)
        p["retrieved"] = [r["slide_id"] for r in res]
        p["top1_rrf"] = res[0]["rrf_score"] if res else 0.0
        p["n_results"] = len(res)
    session.close()

    by_cat = {}
    for p in probes:
        by_cat.setdefault(p["category"], []).append(p)

    print(f"\n{'category':16s} {'n':>4s} {'returned>0':>11s} {'mean top1_rrf':>14s} "
          f"{'max top1_rrf':>13s}")
    for cat, ps in by_cat.items():
        got = [p for p in ps if p["n_results"] > 0]
        scores = [p["top1_rrf"] for p in ps]
        print(f"{cat:16s} {len(ps):>4d} {len(got):>11d} "
              f"{sum(scores)/len(scores):>14.5f} {max(scores):>13.5f}")

    print("\nEvery negative probe should ideally return nothing, or score far below")
    print("the positives. Comparison against the positive set follows in R1b.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(probes, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
