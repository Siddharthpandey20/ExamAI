"""
Q9 — profile the indexing half of ingestion.

SCOPE, stated honestly up front. The brief asked for the whole pipeline:
upload -> parsing -> extraction -> OCR -> chunking -> embedding -> Chroma ->
BM25 -> DB -> total. The repository contains no source PDF or PPTX and the
knowledge/ directory is empty, so the parsing, OCR and table-extraction stages
CANNOT be measured on representative input. Fabricating a synthetic PDF would
produce a number about the synthetic PDF, not about this system's workload, so
those stages are reported as NOT MEASURED rather than estimated.

What can be measured exactly, from the 690 real slides already in the database:

  embedding      encode 690 passages, batched as production does
  Chroma writes  upsert 690 vectors into a TEMPORARY collection
  BM25 build     tokenise the corpus and construct the index
  DB writes      insert 690 slide rows into a TEMPORARY database

Together these are everything between "text has been extracted" and "the
document is searchable", which is the half a re-index has to repeat.

The AI-cleanup stage is not re-measured: P2 already established Ollama at
0.56 req/s, and at one LLM call per page that stage alone dominates everything
below by orders of magnitude. That comparison is drawn at the end.

SAFETY: writes go to a temporary SQLite file and a temporary Chroma collection
in the system temp directory. examai.db and the production Chroma collection
are opened read-only and never modified. No document is re-ingested.
"""

import json
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "experiments" / "benchmarks" / "q9_indexing_profile.json"


def main():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool
    from indexing.database import SessionFactory
    from indexing.models import Base, Document, Slide
    from indexing.embedder import Embedder, build_embed_text
    from engine.tools import _tokenize
    from rank_bm25 import BM25Okapi
    import chromadb

    # ── read the real corpus (read-only) ─────────────────────────────────
    src = SessionFactory()
    try:
        slides = src.query(Slide).filter(Slide.is_embedded == True).all()  # noqa: E712
        corpus = [{
            "doc_id": s.doc_id, "page_number": s.page_number,
            "subject": s.subject, "slide_type": s.slide_type,
            "summary": s.summary, "concepts": s.concepts,
            "chapter": s.chapter, "raw_text": s.raw_text,
            "importance_score": s.importance_score,
        } for s in slides]
    finally:
        src.close()

    texts = [build_embed_text(c["summary"], c["concepts"], c["raw_text"])
             for c in corpus]
    n = len(corpus)
    chars = sum(len(t) for t in texts)
    print(f"corpus: {n} slides, {chars:,} chars "
          f"({chars/n:.0f} chars/slide), {len(set(c['doc_id'] for c in corpus))} documents")
    print("writes go to temporary storage; examai.db and production Chroma "
          "are read-only here\n")

    tmp = Path(tempfile.mkdtemp(prefix="examai_idx_"))
    timings = {}
    try:
        # ── 1. embedding ─────────────────────────────────────────────────
        emb = Embedder()
        t0 = time.perf_counter()
        vecs = emb.embed_passages(texts)
        timings["embedding"] = time.perf_counter() - t0

        # ── 2. Chroma writes (temporary collection) ──────────────────────
        client = chromadb.PersistentClient(path=str(tmp / "chroma"))
        coll = client.get_or_create_collection(
            name="profile_tmp", metadata={"hnsw:space": "cosine"})
        ids = [f"doc{c['doc_id']}_page{c['page_number']}" for c in corpus]
        metas = [{"subject": c["subject"] or "", "source_file": "x.md",
                  "page": c["page_number"]} for c in corpus]
        t0 = time.perf_counter()
        B = 256
        for i in range(0, n, B):
            coll.upsert(ids=ids[i:i+B], embeddings=vecs[i:i+B],
                        documents=texts[i:i+B], metadatas=metas[i:i+B])
        timings["chroma_write"] = time.perf_counter() - t0

        # ── 3. BM25 build ────────────────────────────────────────────────
        t0 = time.perf_counter()
        toks = [_tokenize(f"{c['summary'] or ''} {c['concepts'] or ''} "
                          f"{c['raw_text'] or ''}") for c in corpus]
        tok_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        BM25Okapi(toks)
        timings["bm25_build"] = time.perf_counter() - t0
        timings["bm25_tokenise"] = tok_s

        # ── 4. DB writes (temporary sqlite, production PRAGMAs) ──────────
        dbp = tmp / "profile.db"
        eng = create_engine(f"sqlite:///{dbp}", poolclass=NullPool)
        Base.metadata.create_all(eng)
        S = sessionmaker(bind=eng)
        s2 = S()
        doc_ids = {}
        for did in sorted({c["doc_id"] for c in corpus}):
            d = Document(filename=f"d{did}.md", original_filename=f"d{did}.pdf",
                         file_hash=f"h{did}", status="processed", subject="X")
            s2.add(d)
            s2.flush()
            doc_ids[did] = d.id
        s2.commit()

        t0 = time.perf_counter()
        for i, c in enumerate(corpus):
            s2.add(Slide(doc_id=doc_ids[c["doc_id"]], page_number=c["page_number"],
                         subject=c["subject"], slide_type=c["slide_type"],
                         summary=c["summary"], concepts=c["concepts"],
                         chapter=c["chapter"], raw_text=c["raw_text"],
                         is_embedded=True,
                         importance_score=c["importance_score"] or 0.0))
            if i % 100 == 99:
                s2.commit()
        s2.commit()
        timings["db_write"] = time.perf_counter() - t0
        s2.close()
        eng.dispose()

        # ── report ───────────────────────────────────────────────────────
        measured = ["embedding", "chroma_write", "bm25_tokenise", "bm25_build",
                    "db_write"]
        total = sum(timings[k] for k in measured)
        print("=" * 74)
        print("MEASURED STAGES - text already extracted, 690 slides")
        print("=" * 74)
        print(f"{'stage':22s} {'seconds':>9s} {'% of measured':>14s} "
              f"{'ms/slide':>10s} {'slides/s':>10s}")
        for k in measured:
            v = timings[k]
            print(f"{k:22s} {v:>9.2f} {v/total*100:>13.1f}% "
                  f"{v/n*1000:>10.2f} {n/v:>10.0f}")
        print(f"{'TOTAL (measured)':22s} {total:>9.2f} {'100.0':>13s}% "
              f"{total/n*1000:>10.2f} {n/total:>10.0f}")

        # ── the comparison that matters ──────────────────────────────────
        OLLAMA_RPS = 0.56          # measured in P2
        ai_s = n / OLLAMA_RPS
        print("\n" + "=" * 74)
        print("AGAINST THE STAGE THAT WAS NOT RE-MEASURED")
        print("=" * 74)
        print(f"AI cleanup, 1 LLM call per slide at the 0.56 req/s measured in P2:")
        print(f"  {n} slides -> {ai_s:>8.0f} s  ({ai_s/60:.1f} min)")
        print(f"  everything measured above -> {total:>8.2f} s")
        print(f"\n  AI cleanup is {ai_s/total:.0f}x the cost of embedding, Chroma,")
        print(f"  BM25 and SQLite put together.")
        print(f"  Removing ALL other stages entirely would cut a "
              f"{(ai_s+total)/60:.1f} min ingest by "
              f"{total/(ai_s+total)*100:.1f}%.")

        print("\n" + "=" * 74)
        print("NOT MEASURED - no source document available in the repository")
        print("=" * 74)
        for s in ("upload / file receipt", "PDF or PPTX parsing",
                  "image extraction", "OCR", "table extraction",
                  "page segmentation", "markdown writing"):
            print(f"  {s}")
        print("\nThese are reported as unmeasured rather than estimated. The")
        print("knowledge/ directory is empty and no PDF or PPTX is present, so")
        print("any number here would describe a synthetic file, not this workload.")

        timings["n_slides"] = n
        timings["total_measured"] = total
        timings["ai_cleanup_projected_s"] = ai_s
        OUT.write_text(json.dumps(timings, indent=2), encoding="utf-8")
        print(f"\nsaved -> {OUT}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
