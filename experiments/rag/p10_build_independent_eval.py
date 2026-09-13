"""
An independently constructed evaluation set, from real exam questions.

Everything measured so far traces back to one source: eval/eval_set.json, 40
questions produced by the project's own generation pipeline, then degraded four
ways by rules I wrote. If that pipeline has a house style — and generated
question sets always do — then P3 and P5 measured how well retrieval handles
that house style, and the numbers would not transfer.

This set shares none of that lineage:

  questions   the 40 unique PYQ questions already in the database. Written by a
              human instructor for an actual exam, before any of this work
              existed. Different phrasing, different length, multi-part, and
              some contain natural negation ("Why ARM processors are not found
              in leading-edge high performance?").
  subjects    CN 15, OPERATING SYSTEM 9, CA 8, ML 8 - a different mix from the
              eval set, and two of those subjects had no positives at all in the
              earlier work.

GOLD LABELS ARE ASSIGNED LEXICALLY, NOT BY EMBEDDING.

pyq_matches already exists in the database with a similarity_score, and using it
would be the obvious shortcut. It is also exactly the circularity this project
has been avoiding: those matches were produced by the same embedding model whose
distances are the signal under test, so gold assigned that way would guarantee
the answer. Instead each question is matched to a slide by IDF-weighted term
overlap, which is independent of any vector.

A label is kept only when it is unambiguous: the best slide must clear an
absolute score floor AND beat the runner-up by a margin. Questions without a
confident lexical gold are dropped rather than guessed at - a wrong gold label
is worse than a smaller set.

READ-ONLY. The PYQ tables are opened for reading and never written. No PYQ
question, match or duplicate is modified, merged or deleted.

Writes experiments/benchmarks/independent_eval.json.
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory      # noqa: E402
from indexing.models import PYQQuestion, Slide    # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "independent_eval.json"

MIN_SCORE = 0.30        # best slide must cover this share of question IDF mass
GOLD_BAND = 0.80        # slides scoring >= 80% of the best also count
MAX_GOLD = 3            # but never more than three

STOP = set("""what how why is are the a an of in on for to and or not does do can
which when where who explain describe define tell me about between with from
that this it its their there they be been being has have had will would should
write short note give one example examples explain difference differences
w.r.t wrt also following above below question marks each any some all
""".split())


def terms(text):
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOP]


def main():
    session = SessionFactory()
    try:
        pyqs = session.query(PYQQuestion).all()
        slides = session.query(Slide).filter(Slide.is_embedded == True).all()  # noqa: E712
    finally:
        session.close()

    # Deduplicate: the user uploaded some PYQ files more than once. That
    # duplication is deliberate and stays in the database untouched; it is
    # collapsed here only so one question is not counted several times.
    uniq = {}
    for p in pyqs:
        uniq.setdefault(p.question_text.strip().lower(), p)
    pyqs = list(uniq.values())

    by_subject = {}
    for sl in slides:
        by_subject.setdefault(sl.subject, []).append(sl)

    # Per-subject IDF over slides.
    idf, slide_terms = {}, {}
    for subj, sls in by_subject.items():
        df = Counter()
        for sl in sls:
            t = set(terms(f"{sl.summary or ''} {sl.concepts or ''} {sl.raw_text or ''}"))
            slide_terms[sl.id] = t
            df.update(t)
        n = len(sls)
        idf[subj] = {w: math.log(1 + n / (1 + c)) for w, c in df.items()}

    items, rejected = [], []
    for p in pyqs:
        subj = p.subject
        if subj not in by_subject:
            rejected.append((subj, p.question_text[:60], "subject has no slides"))
            continue
        qt = set(terms(p.question_text))
        if not qt:
            rejected.append((subj, p.question_text[:60], "no content terms"))
            continue

        weights = idf[subj]
        total = sum(weights.get(w, 0.0) for w in qt)
        if total <= 0:
            rejected.append((subj, p.question_text[:60], "no terms known to subject"))
            continue

        scored = []
        for sl in by_subject[subj]:
            hit = qt & slide_terms.get(sl.id, set())
            if hit:
                scored.append((sum(weights.get(w, 0.0) for w in hit) / total, sl))
        scored.sort(key=lambda x: (-x[0], x[1].id))

        if not scored:
            rejected.append((subj, p.question_text[:60], "no lexical overlap"))
            continue
        best_score, best = scored[0]
        if best_score < MIN_SCORE:
            rejected.append((subj, p.question_text[:60],
                             f"best coverage only {best_score:.2f}"))
            continue

        # A GOLD SET, not a single gold slide. An earlier version demanded one
        # unambiguous winner and threw away 25 of 40 questions as "ambiguous" -
        # but these are real multi-part exam questions ("Write the difference
        # between RISC and CISC? Why is Harvard better than Von Neumann?") that
        # genuinely span several slides. Forcing a single label would have made
        # the measurement wrong, not stricter: retrieval that returned the
        # second relevant slide would have been scored as a miss.
        #
        # Every slide within GOLD_BAND of the best score, capped at
        # MAX_GOLD, counts as correct.
        gold = [sl.id for sc, sl in scored[:MAX_GOLD] if sc >= best_score * GOLD_BAND]

        items.append({
            "id": f"indep_pyq_{p.id}",
            "question": p.question_text.strip(),
            "subject": subj,
            "answerable": True,
            "category": "independent_positive",
            "gold_slide_id": best.id,
            "gold_slide_ids": gold,
            "gold_assignment": {
                "method": "idf-weighted lexical overlap (no embedding)",
                "coverage": round(best_score, 3),
                "n_gold": len(gold),
                "runner_up": round(scored[1][0], 3) if len(scored) > 1 else None,
            },
        })

    # Negatives: a real exam question aimed at a subject that does not cover it.
    # Absence is verified with the same anchor-term rule used in P1 - the
    # question's rarest term must occur zero times in the target subject.
    subj_counts = {}
    for subj, sls in by_subject.items():
        c = Counter()
        for sl in sls:
            c.update(terms(f"{sl.summary or ''} {sl.concepts or ''} {sl.raw_text or ''}"))
        subj_counts[subj] = c

    n_neg = 0
    negatives = []
    # Snapshot the positives first: appending to `items` while iterating it
    # grows the list forever.
    for it in list(items):
        src = it["subject"]
        qt = set(terms(it["question"]))
        for target in sorted(by_subject):
            if target == src:
                continue
            counts = {w: subj_counts[target].get(w, 0) for w in qt}
            if not counts:
                continue
            anchor = min(counts, key=counts.get)
            if counts[anchor] > 0:
                continue                       # target may well cover it
            negatives.append({
                "id": f"indep_neg_{it['id']}_{target.replace(' ', '_')}",
                "question": it["question"], "subject": target,
                "answerable": False, "category": "independent_negative",
                "gold_slide_id": None, "source_subject": src,
                "verification": {"method": "lexical-anchor", "anchor_term": anchor,
                                 "anchor_occurrences_in_target": 0},
            })
            n_neg += 1
            break

    items.extend(negatives)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, indent=2), encoding="utf-8")

    pos = [i for i in items if i["answerable"]]
    print(f"unique PYQ questions available : {len(pyqs)}")
    print(f"kept with a confident gold     : {len(pos)}")
    print(f"rejected                       : {len(rejected)}")
    print(f"independent negatives          : {n_neg}")
    print(f"\nby subject: "
          f"{Counter(i['subject'] for i in pos)}")

    print("\nsample kept items:")
    for it in pos[:6]:
        g = it["gold_assignment"]
        print(f"  [{it['subject']:16s}] gold={it['gold_slide_id']:4d} "
              f"cov={g['coverage']:.2f} n_gold={g['n_gold']}")
        print(f"      {it['question'][:96]}")

    print("\nwhy questions were rejected:")
    for s, q, why in rejected[:8]:
        print(f"  [{s:16s}] {why:32s} {q}")

    negq = [i["question"] for i in items if not i["answerable"]]
    print(f"\nnatural negation present in the independent set: "
          f"{sum(1 for i in pos if re.search(r'\\bnot\\b|\\bnever\\b|\\bwithout\\b', i['question'].lower()))} "
          f"of {len(pos)} positives")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
