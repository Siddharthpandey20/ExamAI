"""
Shared pytest configuration and fixtures.

Every test in this suite is deterministic and hermetic: no Ollama, no Redis,
no Celery worker, no network, no API keys, and no dependency on the
developer's own corpus. A clean clone can run the whole suite.

Anything that genuinely needs a live service belongs behind the `integration`
marker (see pytest.ini) and must be skipped by default.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make the repository importable without every test file repeating this.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from indexing.models import Base, Document, Slide  # noqa: E402


@pytest.fixture()
def sqlite_session(tmp_path):
    """An empty throwaway database with the real schema.

    Returns a factory so a test can open more than one session against the
    same file when it needs to model concurrent access.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    session = Factory()
    session.info["factory"] = Factory
    session.info["engine"] = engine
    yield session
    session.close()


@pytest.fixture()
def seed_slides():
    """Insert a document and its slides for one subject.

    Kept as a helper rather than a fixed dataset: the suite's tests need
    deliberately different shapes (two subjects sharing concept text, a
    single subject with scored slides, and so on).
    """
    def _seed(session, subject, pages=3, *, file_hash=None, **slide_kwargs):
        doc = Document(
            filename=f"{subject}.md",
            file_hash=file_hash or f"hash-{subject}",
            status="processed",
            subject=subject,
        )
        session.add(doc)
        session.flush()
        made = []
        for page in range(1, pages + 1):
            fields = dict(
                doc_id=doc.id,
                page_number=page,
                subject=subject,
                slide_type="concept",
                chapter=f"{subject} chapter",
                summary=f"{subject} summary page {page}",
                concepts="tcp, udp",
                raw_text=f"{subject} body text page {page}",
                is_embedded=True,
                importance_score=0.5,
            )
            fields.update(slide_kwargs)
            slide = Slide(**fields)
            session.add(slide)
            made.append(slide)
        session.commit()
        return doc, made

    return _seed


@pytest.fixture()
def no_network(monkeypatch):
    """Hard-fail any test that tries to make a real HTTP call.

    The suite mocks its LLM boundaries; this makes an accidental live call a
    loud failure instead of a slow, flaky pass.
    """
    import requests

    def _blocked(*args, **kwargs):
        raise AssertionError(
            "a test attempted a real network call - mock the LLM boundary instead"
        )

    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "get", _blocked)
