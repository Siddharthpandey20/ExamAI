"""
Step 0 — close the evaluation blind spot.

P5 found, and verification confirmed, that `content_only` inverts negated
questions: "Why is symmetric encryption not used for key exchange?" becomes
"symmetric encryption used key exchange". Every metric in P3/P5/P6 is blind to
this because not one of the 250 eval items contains a negation. Fixing the word
list without fixing the eval set would only move the blind spot, so the eval set
is fixed first and nothing is promoted on the strength of a metric that cannot
see the defect.

Two constructions, deliberately different in kind:

1. RETRIEVAL ITEMS (`positive_negation`) — negated phrasings of the existing 40
   questions, gold slide UNCHANGED.

   Justification for keeping the gold label: the label answers "which slide
   holds the evidence", and negating a question does not move the evidence.
   "What does TCP guarantee?" and "What does TCP not guarantee?" are both
   answered from the slide about TCP guarantees. The *ideal answer text*
   differs; the *retrieval target* does not. Recorded as a stated assumption
   rather than smuggled in.

2. MINIMAL PAIRS (`negation_minimal_pairs`) — an affirmative and a negated form
   differing by exactly one inserted word. These carry no gold slide and are not
   a retrieval measurement at all; they are a PROPERTY test. A transform that
   maps both members of a pair to the same string has provably destroyed the
   distinction, and no amount of good retrieval scores can rehabilitate it.

   This is the part that actually catches the bug. Retrieval metrics can only
   ever show that negation handling is mediocre; a minimal pair shows that it is
   wrong.

Read-only against the corpus. Writes experiments/benchmarks/negation_eval.json.
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

EVAL_SET = REPO / "eval" / "eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "negation_eval.json"

# Words whose removal changes truth conditions. The point of the exercise.
NEGATION_TERMS = ["not", "no", "never", "except", "unless", "without",
                  "neither", "nor", "cannot", "isn't", "doesn't", "won't"]
CONTRAST_TERMS = ["versus", "vs", "unlike", "instead", "rather", "opposed"]

# Conversational scaffolding and generic verbs. A first attempt that simply took
# the first N non-stopword tokens produced word salad ("why is you UDP TCP
# handle process sending not always the right choice?"), which would have
# measured the extractor rather than negation handling.
GENERIC = set("""
i im ive my me you your we our us they them it its this that these those there
building build new needs need send sending sent using use used uses make makes
help helps explain describe define tell show give given get gets handle handles
process processes work works happen happens occur occurs mean means
application applications concepts concept slide slides mentioned relevant
basic characteristics different difference differences
what how why when where which who is are was were be been being am
does do did can could would should will shall may might must have has had
the a an of in on for to and or not with from between about across same
if any some all each other another such more most less least very
question questions answer answers example examples case cases way ways
""".split())


def core_terms(q, limit=5):
    """The technical spine of a question: acronyms first, then domain nouns.

    Acronyms are prioritised because they carry the most retrieval signal and
    are never conversational filler.
    """
    toks = [t.strip(".,;:") for t in re.findall(r"[A-Za-z0-9/+._-]+", q)]
    acro = [t for t in toks if len(t) > 1 and t.isupper()]
    rest = [t for t in toks
            if t.lower() not in GENERIC and len(t) > 3 and not t.isupper()]
    seen, out = set(), []
    for t in acro + rest:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
        if len(out) >= limit:
            break
    return " ".join(out)


# Negated phrasings. Each is a natural question a student would ask, and each
# contains at least one term from NEGATION_TERMS.
NEG_TEMPLATES = [
    "Which of these is not true about {core}?",
    "Why is {core} not always the right choice?",
    "When should {core} not be used?",
    "What does {core} not guarantee?",
    "Explain {core} without referring to an example.",
    "What problem does {core} never solve?",
    "Which cases does {core} not cover, except the trivial one?",
    "Is there any situation where {core} cannot be applied?",
]

# Minimal pairs: exactly one inserted word separates the members.
MINIMAL_PAIR_TEMPLATES = [
    ("Is {core} used here?", "Is {core} not used here?"),
    ("Does {core} guarantee ordering?", "Does {core} never guarantee ordering?"),
    ("Can {core} be applied to this case?", "Can {core} be applied to no case?"),
    ("Should {core} be preferred?", "Should {core} be preferred, unless it is slow?"),
    ("Describe {core} with an example.", "Describe {core} without an example."),
    ("Is {core} correct?", "Is {core} incorrect except in one case?"),
]


def main():
    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    items, pairs = [], []

    for i, qa in enumerate(eval_set):
        core = core_terms(qa["question"])
        if not core:
            continue

        tmpl = NEG_TEMPLATES[i % len(NEG_TEMPLATES)]
        question = tmpl.format(core=core)
        present = sorted({t for t in NEGATION_TERMS + CONTRAST_TERMS
                          if re.search(rf"\b{re.escape(t)}\b", question.lower())})
        assert present, f"template produced no negation term: {question}"

        items.append({
            "id": f"neg_q_{qa['id']}",
            "question": question,
            "subject": qa["subject"],
            "answerable": True,
            "category": "positive_negation",
            "gold_slide_id": qa["gold_slide_id"],
            "source_question": qa["question"],
            "negation_terms": present,
            "assumption": ("gold slide is unchanged: negating a question does "
                           "not move the evidence that answers it"),
        })

        aff_t, neg_t = MINIMAL_PAIR_TEMPLATES[i % len(MINIMAL_PAIR_TEMPLATES)]
        aff, neg = aff_t.format(core=core), neg_t.format(core=core)
        a_words = aff.lower().replace("?", "").replace(".", "").split()
        n_words = neg.lower().replace("?", "").replace(".", "").split()
        pairs.append({
            "id": f"pair_{qa['id']}",
            "subject": qa["subject"],
            "affirmative": aff,
            "negated": neg,
            "edit_distance_words": abs(len(n_words) - len(a_words)),
            "differing_terms": sorted(set(n_words) ^ set(a_words)),
        })

    payload = {
        "retrieval_items": items,
        "minimal_pairs": pairs,
        "negation_terms": NEGATION_TERMS,
        "contrast_terms": CONTRAST_TERMS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"negation retrieval items : {len(items)}")
    print(f"minimal pairs            : {len(pairs)}")
    print(f"subjects                 : "
          f"{sorted({i['subject'] for i in items})}\n")

    print("sample negated questions (gold slide unchanged):")
    for it in items[:5]:
        print(f"  [{it['subject']:5s}] {it['question']}")
        print(f"          terms={it['negation_terms']} gold={it['gold_slide_id']}")

    print("\nsample minimal pairs (a safe transform must keep these distinct):")
    for p in pairs[:5]:
        print(f"  +  {p['affirmative']}")
        print(f"  -  {p['negated']}")
        print(f"     differing: {p['differing_terms']}")

    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
