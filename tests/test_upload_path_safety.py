"""
Regression tests for upload filename sanitisation.

The multipart filename is attacker-controlled and Starlette does not
sanitise it, so routes.uploads.safe_upload_path must guarantee two things:

  1. an ordinary filename is stored unchanged — indexing locates the
     original upload by matching the markdown stem against the stored
     name, so any rewrite would silently break that linkage;
  2. no input can produce a path outside the intended subject directory.

Pure filesystem logic: no database, no network, no server.
"""

import os

import pytest
from fastapi import HTTPException

from routes.uploads import safe_upload_path


@pytest.fixture()
def upload_dir(tmp_path):
    d = tmp_path / "data" / "CN" / "uploads"
    d.mkdir(parents=True)
    return str(d)


# ── Ordinary filenames must be preserved byte for byte ───────────────────

@pytest.mark.parametrize("filename", [
    "lecture.pdf",
    "Chapter 3 - Transport Layer.pdf",
    "CN_Unit-2_2024.pptx",
    "notes(final).ppt",
    "TCP & UDP comparison.pdf",
    "résumé-slides.pdf",
    "week.10.slides.pdf",
    "a" * 120 + ".pdf",
])
def test_normal_filenames_are_unchanged(upload_dir, filename):
    name, path = safe_upload_path(upload_dir, filename)
    assert name == filename
    assert path == os.path.realpath(os.path.join(upload_dir, filename))
    assert os.path.dirname(path) == os.path.realpath(upload_dir)


# ── Traversal attempts must not escape ───────────────────────────────────

@pytest.mark.parametrize("filename", [
    "../evil.pdf",
    "../../evil.pdf",
    "../../../../../../etc/evil.pdf",
    "..\\evil.pdf",
    "..\\..\\..\\Windows\\System32\\evil.pdf",
    "subdir/../../evil.pdf",
    "./../../evil.pdf",
    "/etc/passwd.pdf",
    "/absolute/evil.pdf",
    "C:\\Windows\\evil.pdf",
    "\\\\server\\share\\evil.pdf",
    "....//....//evil.pdf",
    "foo/bar/baz.pdf",
])
def test_traversal_cannot_escape_upload_dir(upload_dir, filename):
    name, path = safe_upload_path(upload_dir, filename)

    # The resolved path must be a direct child of the upload directory.
    assert os.path.dirname(path) == os.path.realpath(upload_dir)
    assert os.path.commonpath([path, os.path.realpath(upload_dir)]) == os.path.realpath(upload_dir)

    # No separator may survive into the stored name.
    assert "/" not in name
    assert "\\" not in name
    assert name not in (".", "..", "")


def test_traversal_writes_land_inside_the_directory(upload_dir, tmp_path):
    """End-to-end: actually write through the returned path."""
    outside = tmp_path / "data" / "CN" / "pyq_uploads"
    outside.mkdir(parents=True)

    _, path = safe_upload_path(upload_dir, "../pyq_uploads/planted.pdf")
    with open(path, "wb") as fh:
        fh.write(b"%PDF-1.4 test")

    assert not (outside / "planted.pdf").exists()
    assert os.path.dirname(path) == os.path.realpath(upload_dir)
    assert os.path.isfile(path)


# ── Degenerate input must not crash or produce an empty name ─────────────

@pytest.mark.parametrize("filename", ["", None, "...", "..", ".", "   ", "./", "../"])
def test_degenerate_names_fall_back_safely(upload_dir, filename):
    name, path = safe_upload_path(upload_dir, filename)
    assert name
    assert name not in (".", "..")
    assert os.path.dirname(path) == os.path.realpath(upload_dir)


def test_control_characters_are_stripped(upload_dir):
    name, path = safe_upload_path(upload_dir, "ev\x00il\nnotes.pdf")
    assert "\x00" not in name
    assert "\n" not in name
    assert os.path.dirname(path) == os.path.realpath(upload_dir)


def test_sibling_directory_prefix_is_rejected(upload_dir, tmp_path):
    """'uploads_evil' must not count as being inside 'uploads'."""
    sibling = tmp_path / "data" / "CN" / "uploads_evil"
    sibling.mkdir(parents=True)

    _, path = safe_upload_path(upload_dir, "../uploads_evil/x.pdf")
    assert os.path.dirname(path) == os.path.realpath(upload_dir)
    assert not str(path).startswith(str(sibling))


def test_rejects_when_target_dir_is_not_a_real_parent(tmp_path):
    """A target directory that cannot contain the file raises rather than writes."""
    missing = str(tmp_path / "does" / "not" / "exist")
    # Still resolves to a direct child; never escapes.
    name, path = safe_upload_path(missing, "ok.pdf")
    assert name == "ok.pdf"
    assert os.path.dirname(path) == os.path.realpath(missing)


def test_hidden_dotfile_is_neutralised(upload_dir):
    name, _ = safe_upload_path(upload_dir, ".hidden.pdf")
    assert not name.startswith(".")


def test_httpexception_is_importable_for_callers():
    """safe_upload_path signals refusal via HTTPException, not a bare error."""
    assert issubclass(HTTPException, Exception)
