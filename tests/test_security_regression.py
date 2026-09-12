"""
Security regression suite.

Two kinds of test live here and they must not be confused:

  * `test_*` — a protection that EXISTS and must not regress.
  * `test_KNOWN_GAP_*` — a protection that does NOT exist. These assert the
    current (weaker) behaviour so the gap is visible in the suite rather
    than silently forgotten. If someone later closes the gap, the matching
    test fails loudly and should be rewritten as a real protection test.

Path-traversal protection has its own file, tests/test_upload_path_safety.py.
Cache subject/endpoint isolation has its own file, tests/test_cache_key.py.

No database, network, Ollama, Redis or server required.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indexing.models import Base, Document, Slide  # noqa: E402
from engine.tools import search_by_type, search_by_concept, get_priority_slides  # noqa: E402
from routes.uploads import ALLOWED_EXTENSIONS, _validate_file, safe_upload_path  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture()
def two_subject_db(tmp_path):
    """Two subjects with deliberately similar content."""
    engine = create_engine(f"sqlite:///{tmp_path / 'iso.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    for idx, subject in enumerate(("CN", "ML"), start=1):
        doc = Document(filename=f"{subject}.md", file_hash=f"h{idx}",
                       status="processed", subject=subject)
        s.add(doc)
        s.flush()
        for page in range(1, 4):
            s.add(Slide(doc_id=doc.id, page_number=page, subject=subject,
                        slide_type="concept", chapter=f"{subject} chapter",
                        summary=f"{subject} gradient descent overview page {page}",
                        concepts="gradient descent, optimisation",
                        raw_text=f"{subject} body text about gradient descent",
                        is_embedded=True, importance_score=0.5))
    s.commit()
    yield s
    s.close()


class _Upload:
    """Minimal stand-in for starlette UploadFile."""
    def __init__(self, filename):
        self.filename = filename


# ── Subject isolation: protections that exist ────────────────────────────

def test_search_by_type_is_subject_scoped(two_subject_db):
    for subject in ("CN", "ML"):
        rows = search_by_type(subject, "concept", two_subject_db)
        assert rows, "fixture should return results"
        assert all(subject in r["summary"] for r in rows)


def test_search_by_concept_is_subject_scoped(two_subject_db):
    """Both subjects share the concept text; results must not bleed."""
    cn = search_by_concept("CN", "gradient", two_subject_db)
    ml = search_by_concept("ML", "gradient", two_subject_db)
    assert cn and ml
    assert {r["slide_id"] for r in cn}.isdisjoint({r["slide_id"] for r in ml})


def test_priority_tiers_are_subject_scoped(two_subject_db):
    cn = get_priority_slides("CN", two_subject_db)
    ids = {r["slide_id"] for tier in cn.values() for r in tier}
    ml_ids = {
        r[0] for r in two_subject_db.query(Slide.id).filter(Slide.subject == "ML").all()
    }
    assert ids.isdisjoint(ml_ids)


def test_bm25_corpus_query_is_subject_scoped(two_subject_db):
    """run_hybrid_search builds its sparse corpus from this exact query."""
    rows = (
        two_subject_db.query(Slide)
        .filter(Slide.subject == "CN", Slide.is_embedded == True)  # noqa: E712
        .all()
    )
    assert rows
    assert all(r.subject == "CN" for r in rows)


# ── Upload validation: protections that exist ────────────────────────────

def test_disallowed_extensions_are_rejected():
    from fastapi import HTTPException
    for name in ("payload.exe", "script.sh", "archive.zip", "notes.txt", "noext"):
        with pytest.raises(HTTPException) as exc:
            _validate_file(_Upload(name))
        assert exc.value.status_code == 400


def test_allowed_extensions_are_accepted():
    for name in ("lecture.pdf", "deck.pptx", "old.ppt", "UPPER.PDF"):
        _validate_file(_Upload(name))  # must not raise


def test_extension_check_sees_through_traversal_prefix():
    """A traversal payload must still be extension-validated."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        _validate_file(_Upload("../../../etc/passwd"))
    _validate_file(_Upload("../../../etc/evil.pdf"))  # allowed by extension...
    # ...but sanitisation strips the path, verified in test_upload_path_safety.py
    name, path = safe_upload_path(os.getcwd(), "../../../etc/evil.pdf")
    assert name == "evil.pdf"


def test_allowed_extension_set_is_narrow():
    assert ALLOWED_EXTENSIONS == {".pdf", ".pptx", ".ppt"}


# ── Documented gaps — these are NOT protections ──────────────────────────

def test_KNOWN_GAP_content_type_is_not_verified():
    """Validation is extension-only; file bytes are never inspected.

    A ZIP renamed to .pdf reaches PyMuPDF/python-pptx, both C-backed parsers.
    Recorded as a finding; fixing it is a separate task.
    """
    _validate_file(_Upload("actually-a-zip.pdf"))  # accepted purely on extension

    import inspect
    src = inspect.getsource(_validate_file)
    assert "splitext" in src
    for magic_check in ("%PDF", "magic", "mimetypes.guess_type", "read("):
        assert magic_check not in src, (
            f"content sniffing ({magic_check}) appears to have been added — "
            "close this gap properly and rewrite this test as a protection test"
        )


def test_KNOWN_GAP_upload_size_is_unbounded():
    """`content = await file.read()` buffers the whole upload in memory.

    No max size, no streaming, no rate limit. Recorded as a finding; fixing
    it is a separate task.
    """
    import inspect
    import routes.uploads as up
    src = inspect.getsource(up.upload_study_material)
    assert "await file.read()" in src
    for guard in ("max_size", "MAX_UPLOAD", "content-length", "content_length"):
        assert guard not in src, (
            "an upload size guard appears to have been added — "
            "close this gap properly and rewrite this test as a protection test"
        )


def test_KNOWN_GAP_cors_is_wildcard_with_credentials():
    """allow_origins=['*'] together with allow_credentials=True.

    Browsers reject that combination, so it does not do what it appears to,
    and it admits any origin. Recorded as a finding; fixing it is a separate
    task.
    """
    import main
    cors = [m for m in main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert len(cors) == 1
    kwargs = cors[0].kwargs
    assert kwargs["allow_origins"] == ["*"]
    assert kwargs["allow_credentials"] is True


def test_KNOWN_GAP_dense_retrieval_falls_back_to_unfiltered():
    """run_hybrid_search retries Chroma WITHOUT the subject filter on error.

    The fused loop then resolves slides by (doc_id, page_number) with no
    subject re-check, so a Chroma error can surface another subject's
    slides. Recorded as a finding; fixing it is a separate task.
    """
    import inspect
    import engine.tools as tools
    src = inspect.getsource(tools.run_hybrid_search)
    assert "except Exception:" in src
    assert "chroma.query(query_embedding=query_vec, n_results=fetch_n)" in src, (
        "the unfiltered fallback appears to have changed — re-verify subject "
        "isolation and rewrite this test as a protection test"
    )


def test_KNOWN_GAP_no_authentication_on_any_route():
    """No auth exists anywhere; every endpoint is open.

    Acceptable for a localhost single-user tool, disqualifying for a network
    deployment. Recorded as a finding; fixing it is a separate task.
    """
    import main
    names = {m.cls.__name__ for m in main.app.user_middleware}
    assert not any("auth" in n.lower() for n in names)

    # No route declares a security scheme (OAuth2/HTTPBearer/APIKey/...).
    schemes = []
    for route in main.app.routes:
        dep = getattr(route, "dependant", None)
        if dep is not None:
            schemes.extend(getattr(dep, "security_requirements", []) or [])
    assert schemes == [], (
        f"authentication appears to have been added ({len(schemes)} secured "
        "endpoints) — close this gap properly and rewrite this test"
    )

    # And the OpenAPI schema advertises no security schemes either.
    components = main.app.openapi().get("components", {})
    assert "securitySchemes" not in components
