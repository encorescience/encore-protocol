"""Tests for tools/archives/dryad.py: staging a pinned version's files and checking them."""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from archives import dryad  # noqa: E402

NEW, OLD = b"a file Dryad lists with a SHA-256", b"a 2019 file Dryad lists with an MD5 only"


def _dryad(monkeypatch, md5=hashlib.md5(OLD).hexdigest()):
    """Dryad's API, offline: the version's public file list, and the downloads."""
    listing = {"_embedded": {"stash:files": [
        {"path": "new.csv", "digestType": "sha-256", "digest": hashlib.sha256(NEW).hexdigest(),
         "_links": {"self": {"href": "/api/v2/files/1"}}},
        {"path": "old.zip", "digestType": "md5", "digest": md5, "_links": {"self": {"href": "/api/v2/files/2"}}}]},
        "_links": {}}
    listed = []
    def urlopen(url, timeout=None):
        listed.append(url)
        return io.BytesIO(json.dumps(listing).encode())
    class Opener:
        def open(self, req, timeout=None):
            return io.BytesIO({"1": NEW, "2": OLD}[req.full_url.split("/")[-2]])
    monkeypatch.setattr(dryad.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(dryad.urllib.request, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(dryad, "_token", lambda: "token")
    return listed


def _target(old_sha256=None):
    return {"id": "m31b1h7", "published_version": "94811", "files": [
        {"path": "new.csv", "file_id": 1, "sha256": hashlib.sha256(NEW).hexdigest()},
        {"path": "old.zip", "file_id": 2, "sha256": old_sha256}]}


def test_a_file_dryad_lists_with_an_md5_only_is_checked_against_it(monkeypatch, tmp_path):
    # 2026-11-25: DRYAD:m31b1h7's one file, from 2019, has an MD5 in Dryad's file list and no SHA-256, so the
    # registry's list named its SHA-256 as None and staging refused the file ("not the listed None").
    listed = _dryad(monkeypatch)
    dest = dryad.stage(_target(), tmp_path)
    assert (dest / "old.zip").read_bytes() == OLD and (dest / "new.csv").read_bytes() == NEW
    assert listed == [f"{dryad.API}/versions/94811/files"]
    assert dryad.stage(_target(), tmp_path) == dest                 # staged files are checked, not downloaded again


def test_a_file_that_does_not_match_its_md5_is_refused(monkeypatch, tmp_path):
    _dryad(monkeypatch, md5=hashlib.md5(b"something else").hexdigest())
    with pytest.raises(RuntimeError, match="old.zip: MD5 .* not the listed"):
        dryad.stage(_target(), tmp_path)
    assert not (tmp_path / "dryad" / "m31b1h7" / "94811" / "old.zip").exists()


def test_the_file_list_is_not_read_when_every_file_has_a_sha256(monkeypatch, tmp_path):
    listed = _dryad(monkeypatch)
    dryad.stage(_target(old_sha256=hashlib.sha256(OLD).hexdigest()), tmp_path)
    assert listed == []
