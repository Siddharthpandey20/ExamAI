"""
G1c — corrected analysis of the grounding run.

Supersedes g1b, which had two measurement bugs that would have produced two
false findings. Both are recorded here rather than quietly fixed, because the
first version looked plausible and alarming:

  BUG 1 - citation matching. g1b reported that only 12.2% of citations matched
  the context exactly. The model writes "Page\\u202f62 of *CH2.pdf*" - a narrow
  no-break space after "Page" and markdown asterisks around the filename - so
  the captured filename was "*CH2.pdf*" and never matched "CH2.pdf". The page
  number matched 100% of the time, which should have been the clue. Citations
  are normalised here before comparison.

  BUG 2 - the grounding metric. g1b counted any word longer than three
  characters, so the "ungrounded" terms were 'able', 'above', 'after',
  'across', 'actual' - ordinary English absent from terse slide summaries, not
  hallucinated content. The metric measured prose style, not grounding.

  The corrected version scores only CHECKABLE SPECIFICS: numbers, acronyms and
  technical multi-character tokens. Those are the claims a student could look
  up and find wrong. Ordinary connective vocabulary is excluded because its
  absence from a summary means nothing.

Deterministic metrics and judged metrics are reported separately and never
blended. The judge is the same model that produced the answers, which biases
it lenient; where the two disagree, trust the mechanical one.

Computes only.
"""

import json
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "g1_grounding.json"
OUT = REPO / "experiments" / "benchmarks" / "g1c_corrected.json"


def norm(s):
    """Fold unicode punctuation and markdown so citations compare properly."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace(" ", " ").replace("‑", "-").replace("–", "-")
    return s


CITE = re.compile(r"[Pp]age\s*(\d+)\s*(?:of|in|,)?\s*[*_`\"']*"
                  r"([A-Za-z0-9][A-Za-z0-9 _.\-]*?\.(?:pdf|pptx|md|ppt))[*_`\"']*",
                  re.IGNORECASE)


def parse_citations(answer):
    out = []
    for m in CITE.finditer(norm(answer)):
        out.append((int(m.group(1)), m.group(2).strip(" *_`\"'.,;:").lower()))
    return out


SPECIFIC = re.compile(r"\b(?:\d+(?:\.\d+)?%?|[A-Z]{2,}[0-9]*|[A-Za-z]+\d+[A-Za-z0-9]*)\b")


def specifics(text):
    """Checkable claims: numbers, acronyms, alphanumeric identifiers."""
    t = norm(text)
    out = set()
    for m in SPECIFIC.finditer(t):
        tok = m.group(0).strip().lower()
        if tok in {"a", "i"} or len(tok) < 2:
            continue
        out.add(tok)
    return out


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    ans = [r for r in rows if r["kind"] == "answerable"]
    ins = [r for r in rows if r["kind"] == "insufficient"]
    print(f"{len(rows)} answers: {len(ans)} answerable, {len(ins)} insufficient\n")

    # Rebuild the context key set from what was recorded. The run stored the
    # retrieved slide ids; filenames come back from the citation text itself,
    # so validity is checked on (page, file) pairs seen in the context string.
    # The run did not store the context, so page-level validity is the strongest
    # mechanical check available retrospectively - stated plainly rather than
    # overclaimed.
    corrected = []
    for r in rows:
        c = parse_citations(r["answer"])
        sp_ans = specifics(r["answer"])
        corrected.append({**r, "cites_fixed": c, "n_cites_fixed": len(c),
                          "n_specifics": len(sp_ans)})

    print("=" * 76)
    print("1. CITATIONS - after fixing the parser")
    print("=" * 76)
    print(f"{'group':16s} {'n':>4s} {'citations':>10s} {'per answer':>11s} "
          f"{'no citation':>12s} {'distinct files':>15s}")
    for label, grp in (("answerable", [c for c in corrected if c["kind"] == "answerable"]),
                       ("insufficient", [c for c in corrected if c["kind"] == "insufficient"])):
        tot = sum(c["n_cites_fixed"] for c in grp)
        none = sum(1 for c in grp if c["n_cites_fixed"] == 0)
        files = {f for c in grp for _, f in c["cites_fixed"]}
        print(f"{label:16s} {len(grp):>4d} {tot:>10d} {tot/len(grp):>11.1f} "
              f"{none}/{len(grp):<8} {len(files):>15d}")

    print(f"\n  g1b reported 12.2% exact-match citations. That was a parser bug:")
    print(f"  the model writes 'Page\\u202f62 of *CH2.pdf*'. Page numbers matched")
    print(f"  100% of the time, which was the tell. Citation FORMAT is fine.")

    # Fabricated files: a cited filename that does not exist in the corpus.
    from indexing.database import SessionFactory
    from indexing.models import Document
    s = SessionFactory()
    try:
        real_files = {d.filename.lower() for d in s.query(Document).all()}
        real_files |= {d.original_filename.lower() for d in s.query(Document).all()
                       if d.original_filename}
    finally:
        s.close()

    print("\n" + "=" * 76)
    print("2. FABRICATED SOURCES - cited a file that does not exist")
    print("=" * 76)
    bad = []
    for c in corrected:
        for page, f in c["cites_fixed"]:
            if f not in real_files:
                bad.append((c["kind"], c["question"][:46], page, f))
    print(f"  citations to non-existent files: {len(bad)}")
    for kind, q, page, f in bad[:8]:
        print(f"    [{kind:12s}] {q!r}")
        print(f"        cited page {page} of {f!r}  <- no such document")
    print(f"\n  real documents in the corpus: {len(real_files)}")

    # ── 3. grounding on checkable specifics ──────────────────────────────
    print("\n" + "=" * 76)
    print("3. GROUNDING - numbers, acronyms and identifiers only")
    print("=" * 76)
    print("   (g1b counted every word >3 chars, so 'able'/'after'/'across'")
    print("    scored as ungrounded. That measured prose, not grounding.)\n")
    print(f"{'group':16s} {'n':>4s} {'specifics/answer':>17s}")
    for label, grp in (("answerable", [c for c in corrected if c["kind"] == "answerable"]),
                       ("insufficient", [c for c in corrected if c["kind"] == "insufficient"])):
        v = [c["n_specifics"] for c in grp]
        print(f"{label:16s} {len(grp):>4d} {statistics.mean(v):>17.1f}")
    print("\n  NOTE: the run did not persist the context string, so specifics")
    print("  cannot be checked against it retrospectively. This is a gap in the")
    print("  experiment design, not a result. G3 records context and closes it.")

    # ── 4. the finding that survives ─────────────────────────────────────
    print("\n" + "=" * 76)
    print("4. BEHAVIOUR WHEN THE ANSWER IS NOT IN THE MATERIAL")
    print("=" * 76)
    declined = [r for r in ins if r.get("judge") and r["judge"].get("declines")]
    answered = [r for r in ins if not (r.get("judge") and r["judge"].get("declines"))]
    print(f"  questions whose answer is verifiably absent : {len(ins)}")
    print(f"  answers that said so                        : {len(declined)} "
          f"({len(declined)/len(ins):.0%})")
    print(f"  answers that answered anyway                : {len(answered)} "
          f"({len(answered)/len(ins):.0%})")
    cited_absent = sum(c["n_cites_fixed"] for c in corrected
                       if c["kind"] == "insufficient")
    print(f"  slide citations emitted for absent topics   : {cited_absent}")
    print("\n  This is unaffected by either bug: it comes from the judge's")
    print("  'declines' flag and the citation COUNT, not from matching.")
    if answered:
        print("\n  questions answered despite absent evidence:")
        for r in answered[:5]:
            print(f"    {r['question'][:64]}")

    # ── 5. judged metrics ────────────────────────────────────────────────
    print("\n" + "=" * 76)
    print("5. JUDGED METRICS - same model grading its own output; lenient")
    print("=" * 76)
    for label, grp in (("answerable", ans), ("insufficient", ins)):
        j = [r["judge"] for r in grp if r.get("judge")]
        if not j:
            continue
        c = Counter(x.get("correct") for x in j)
        g = Counter(x.get("grounded") for x in j)
        uns = [x.get("unsupported_claims", 0) or 0 for x in j]
        print(f"\n{label} (judged {len(j)}/{len(grp)}):")
        print(f"  correct  2={c.get(2,0)} 1={c.get(1,0)} 0={c.get(0,0)}  "
              f"mean {statistics.mean([x.get('correct',0) or 0 for x in j]):.2f}/2")
        print(f"  grounded 2={g.get(2,0)} 1={g.get(1,0)} 0={g.get(0,0)}  "
              f"mean {statistics.mean([x.get('grounded',0) or 0 for x in j]):.2f}/2")
        print(f"  unsupported claims: total {sum(uns)}, "
              f"answers with >=1: {sum(1 for u in uns if u)}/{len(j)}")

    # ── 6. retrieval or generation? ──────────────────────────────────────
    print("\n" + "=" * 76)
    print("6. IS THE BOTTLENECK RETRIEVAL OR GENERATION?")
    print("=" * 76)
    have = [r for r in ans if r.get("judge") and r["gold_in_context"] is not None]
    gold_in = [r for r in have if r["gold_in_context"]]
    gold_out = [r for r in have if not r["gold_in_context"]]
    print(f"{'case':40s} {'n':>4s} {'correct/2':>10s} {'grounded/2':>11s}")
    for label, grp in (("gold slide WAS in context", gold_in),
                       ("gold slide was NOT in context", gold_out)):
        if not grp:
            continue
        print(f"{label:40s} {len(grp):>4d} "
              f"{statistics.mean([r['judge'].get('correct',0) or 0 for r in grp]):>10.2f} "
              f"{statistics.mean([r['judge'].get('grounded',0) or 0 for r in grp]):>11.2f}")
    if gold_in:
        failed = [r for r in gold_in if (r["judge"].get("correct", 0) or 0) < 2]
        print(f"\n  Retrieval succeeded yet the answer was not fully correct: "
              f"{len(failed)}/{len(gold_in)} ({len(failed)/len(gold_in):.0%})")

    Path(OUT).write_text(json.dumps(
        [{k: v for k, v in c.items() if k != "answer"} for c in corrected],
        indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
