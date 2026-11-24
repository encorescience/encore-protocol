"""Tests for encore_science (`encore check`) and the registry's support for local and remote datasets."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import agent_run  # noqa: E402
import datasets  # noqa: E402
import entry  # noqa: E402
from encore_science import report, run  # noqa: E402


def test_a_directory_or_url_gets_a_plain_id():
    assert run.slug("Smith_2024 NWB files/") == "smith-2024-nwb-files"
    assert run.slug("***") == "dataset"


def test_a_directory_is_a_local_dataset_with_a_fingerprint(tmp_path):
    (tmp_path / "sub-1").mkdir()
    (tmp_path / "sub-1" / "a.nwb").write_bytes(b"x" * 10)
    d = run.dataset_of(str(tmp_path))
    assert (d.archive, d.location) == ("local", str(tmp_path.resolve()))
    assert d.folder == f"local-{d.id}" and d.fingerprint.startswith("files-")
    before = d.fingerprint
    (tmp_path / "sub-1" / "a.nwb").write_bytes(b"y" * 10)
    assert run.dataset_of(str(tmp_path)).fingerprint != before


def test_a_url_and_an_archive_dataset_are_told_apart():
    d = run.dataset_of("s3://bucket/smith-2024/")
    assert (d.archive, d.id) == ("remote", "smith-2024")
    assert run.dataset_of("DANDI:000147").folder == "000147"
    assert run.dataset_of("000147", "draft").version == "draft"
    assert run.dataset_of("CRCNS:ret-1").folder == "crcns-ret-1"
    with pytest.raises(run.Stop):
        run.dataset_of("not a dataset at all")


def test_the_doi_is_found_on_the_first_pages():
    assert run.find_doi(["Nature Neurosci 3, 211 (2000). doi:10.1038/72910."]) == "10.1038/72910"
    assert run.find_doi(["https://doi.org/10.1101/2024.01.02.123456v2 posted"]) == "10.1101/2024.01.02.123456v2"
    assert run.find_doi(["no identifier here"]) is None


@pytest.fixture
def local_target(monkeypatch, tmp_path):
    """A registry whose targets/local.json lists one local dataset, as `encore check` writes it."""
    root = tmp_path / "registry"
    (root / "targets").mkdir(parents=True)
    target = {"archive": "local", "id": "smith-2024", "name": "A paper", "path": "/data/smith-2024",
              "fingerprint": "files-0123456789ab", "papers": [{"doi": "10.1038/72910", "title": "A paper", "preprint": False}]}
    (root / "targets" / "local.json").write_text(json.dumps({"targets": [target, dict(target, archive="remote", id="r",
                                                                                         url="s3://b/r", path=None)]}))
    monkeypatch.setattr(datasets, "ROOT", root)
    return root


def test_local_and_remote_datasets_come_from_their_shared_list(local_target):
    found = {t["key"]: t for t in datasets.targets()}
    assert set(found) == {"local:smith-2024", "remote:r"}
    assert found["local:smith-2024"]["folder"] == "local-smith-2024"
    assert "/data/smith-2024" in datasets.access("local:smith-2024")
    assert "s3://b/r" in datasets.access("remote:r")
    assert datasets.folder(datasets.parse("local:smith-2024")) == "local-smith-2024"


def test_a_local_dataset_gets_its_fingerprint_as_its_version(local_target, monkeypatch):
    monkeypatch.setattr(agent_run, "ROOT", REPO)
    monkeypatch.setattr(agent_run, "attempt_of", lambda folder: None)
    prompt = agent_run.fill("author", "local-smith-2024", "claude-opus-5-5")
    assert "/data/smith-2024" in prompt and "files-0123456789ab" in prompt
    assert "pinned published version" not in prompt
    assert "doi:10.1038/72910" in agent_run.fill("claims", "local-smith-2024", "claude-opus-5-5")


def test_only_the_local_dataset_path_may_be_named_in_an_entry(monkeypatch):
    monkeypatch.delenv("ENCORE_LOCAL_DATA", raising=False)
    code = 'io = NWBHDF5IO("/Users/me/smith-2024/sub-1.nwb")'

    def errors(text):
        rep = entry.Report()
        entry._derivation_checks(rep, "nb", text)
        return [e for e in rep.errors if "local path" in str(e)]

    assert errors(code)
    monkeypatch.setenv("ENCORE_LOCAL_DATA", "/Users/me/smith-2024")
    assert not errors(code)
    assert errors('open("/Users/me/other/file.csv")')
    assert errors('open("/Users/me/smith-2024-copy/x.nwb")')


def test_the_report_counts_outcomes_and_lists_findings(tmp_path):
    reg = tmp_path / "registry"
    (reg / "attempts").mkdir(parents=True)
    (reg / "claims" / "local-x").mkdir(parents=True)
    (reg / "claims" / "local-x" / "c.yaml").write_text("claims:\n- id: rate\n  statement: Rates rose.\n")
    (reg / "attempts" / "local-x-smith-2024-01.yaml").write_text(
        "id: local-x-smith-2024-01\nentry: local-x-smith-2024\noutcomes:\n"
        "- claim: rate\n  outcome: blocked\n  blocked_by: data_missing\n  notes: No trials table.\n"
        "findings:\n- kind: data_missing\n  statement: The trials table is missing.\n")
    state = {"folder": "local-x", "title": "Smith 2024", "doi": "10.1/x", "mode": "quick", "model": "m",
             "protocol": "p", "finished": "2026-10-22T12:00", "dataset": {"location": "/d", "fingerprint": "files-1"},
             "roles": {"claims": {"status": "success"}}}
    text = report.write_report(tmp_path, reg, state).read_text()
    assert "## Claims: 1 blocked" in text and "blocked (data missing)" in text
    assert "The trials table is missing." in text and "quick run" in text


def test_macos_metadata_files_beside_the_claims_and_attempts_are_skipped(tmp_path):
    reg = tmp_path / "registry"
    (reg / "attempts").mkdir(parents=True)
    (reg / "claims" / "local-x").mkdir(parents=True)
    (reg / "claims" / "local-x" / "c.yaml").write_text("checks:\n- ready: true\nclaims:\n- id: rate\n")
    (reg / "attempts" / "local-x-smith-2024-01.yaml").write_text("id: local-x-smith-2024-01\n")
    # what macOS writes beside each file on an exFAT drive: binary, and not valid UTF-8
    for path in (reg / "claims" / "local-x" / "._c.yaml", reg / "attempts" / "._local-x-smith-2024-01.yaml"):
        path.write_bytes(b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        \x00\x02\x00\x00\x00\x09\xb0\xff")
    assert list(report.claims_of(reg, "local-x")) == ["rate"]
    assert report.latest_attempt(reg, "local-x")["id"] == "local-x-smith-2024-01"
    r = run.Run(tmp_path / "out", run.Dataset("local", "x", "/d", "files-1"), None, None, None, False, "m", "main")
    r.registry = reg
    assert r.claims_ready()


def test_a_run_keeps_only_the_example_attempt(tmp_path):
    reg = tmp_path / "out" / "registry"
    for path in ("claims/fouke-2025.yaml", "claims/knierim-2000.yaml", "entries/fouke-2025/x.ipynb",
                 "entries/knierim-2000/y.ipynb", "attempts/fouke-2025-01.yaml",
                 "attempts/knierim-2000-01.yaml", "transcripts/knierim-2000/author.md", "questions/knierim-2000.yaml"):
        (reg / path).parent.mkdir(parents=True, exist_ok=True)
        (reg / path).write_text("x")
    run.git("init", "-q", str(reg))
    run.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init", cwd=reg)
    run.git("config", "user.name", "t", cwd=reg)
    run.git("config", "user.email", "t@t", cwd=reg)
    r = run.Run(tmp_path / "out", run.Dataset("local", "x", "/d", "files-1"), None, None, None, False, "m", "main")
    r.prune()
    left = sorted(p.relative_to(reg).as_posix() for p in reg.rglob("*") if p.is_file() and ".git" not in p.parts)
    assert left == ["attempts/fouke-2025-01.yaml", "claims/fouke-2025.yaml", "entries/fouke-2025/x.ipynb"]


def _registry_repo(path: Path) -> str:
    """A small registry to fetch from, served as a remote that allows partial clones."""
    for name in ("claims/fouke-2025.yaml", "claims/knierim-2000.yaml", "entries/fouke-2025/x.ipynb",
                 "entries/knierim-2000/y.ipynb", "attempts/fouke-2025-01.yaml", "attempts/knierim-2000-01.yaml",
                 "transcripts/knierim-2000/author.md", "questions/knierim-2000.yaml", "docs/pilot-notes/k.md",
                 "docs/pilot-notes.md", "tools/agent_run.py", "targets/dandisets.json", "papers/datasets/k.yaml",
                 "README.md"):
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(name)
    run.git("init", "-q", str(path))
    run.git("config", "uploadpack.allowFilter", "true", cwd=path)
    run.git("add", "-A", cwd=path)
    run.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=path)
    return path.as_uri()


def _files(directory: Path) -> list[str]:
    return sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*")
                  if p.is_file() and ".git" not in p.parts)


def test_the_registry_is_fetched_without_other_datasets_work(tmp_path, monkeypatch):
    url = _registry_repo(tmp_path / "remote")
    monkeypatch.setenv("ENCORE_CACHE", str(tmp_path / "cache"))
    cache = run.cached_clone(url, "registry", "HEAD", run.sparse_patterns())
    assert _files(cache) == ["README.md", "attempts/fouke-2025-01.yaml", "claims/fouke-2025.yaml",
                             "docs/pilot-notes.md", "entries/fouke-2025/x.ipynb", "papers/datasets/k.yaml",
                             "targets/dandisets.json", "tools/agent_run.py"]
    # the contents of the files left out were never fetched
    missing = run.git("rev-list", "--objects", "--missing=print", "HEAD", cwd=cache)
    assert sum(line.startswith("?") for line in missing.splitlines()) == 6
    # a second run reuses the cache
    assert _files(run.cached_clone(url, "registry", "HEAD", run.sparse_patterns())) == _files(cache)


def test_a_full_cache_from_before_is_fetched_again(tmp_path, monkeypatch):
    url = _registry_repo(tmp_path / "remote")
    monkeypatch.setenv("ENCORE_CACHE", str(tmp_path / "cache"))
    old = run.cached_clone(url, "registry", "HEAD")   # as an earlier version cloned it
    assert "transcripts/knierim-2000/author.md" in _files(old)
    cache = run.cached_clone(url, "registry", "HEAD", run.sparse_patterns())
    assert "transcripts/knierim-2000/author.md" not in _files(cache) and "claims/fouke-2025.yaml" in _files(cache)
    assert run.git("count-objects", "-v", cwd=cache).count("size-pack: 0") == 0
    assert run.git("rev-list", "--objects", "--missing=print", "HEAD", cwd=cache).count("\n?") == 6


def test_the_protocol_is_laid_over_a_copy_of_the_registry(tmp_path):
    from encore_science.run import LAID, lay_protocol
    protocol, registry = tmp_path / "protocol", tmp_path / "registry"
    for folder in LAID:
        (protocol / folder / "sub").mkdir(parents=True)
        (protocol / folder / "sub" / "file.txt").write_text(f"protocol {folder}")
    (protocol / "tools" / "__pycache__").mkdir()
    (protocol / "tools" / "__pycache__" / "x.pyc").write_text("")
    (protocol / "README.md").write_text("the protocol's own")
    (registry / "docs").mkdir(parents=True)
    (registry / "docs" / "queue.md").write_text("the registry's own")
    lay_protocol(protocol, registry)
    assert all((registry / folder / "sub" / "file.txt").read_text() == f"protocol {folder}" for folder in LAID)
    assert (registry / "docs" / "queue.md").read_text() == "the registry's own"
    assert not (registry / "tools" / "__pycache__").exists() and not (registry / "README.md").exists()


def test_a_run_reads_the_paper_first_layout(tmp_path):
    reg = tmp_path / "out" / "registry"
    (reg / "attempts").mkdir(parents=True)
    (reg / "claims").mkdir()
    (reg / "questions").mkdir()
    (reg / "claims" / "local-x.yaml").write_text(
        "checks:\n- ready: true\nclaims:\n- id: rate\n  statement: Rates rose.\n")
    (reg / "questions" / "local-x.yaml").write_text("- question: Is rate per trial?\n")
    (reg / "attempts" / "local-x-01.yaml").write_text(
        "id: local-x-01\nentry: local-x\noutcomes:\n- claim: rate\n  outcome: reproduced\n")
    r = run.Run(tmp_path / "out", run.Dataset("local", "x", "/d", "files-1"), None, None, None, False, "m", "main")
    r.state = {"key": "local-x"}
    assert r.claims_ready() and r.open_questions() == 1
    state = {"folder": "local-x", "key": "local-x", "title": "Smith 2024", "doi": "10.1/x", "mode": "quick",
             "model": "m", "protocol": "p", "finished": "2026-11-24T12:00", "dataset": {"location": "/d"},
             "roles": {"author": {"status": "success"}}}
    text = report.write_report(tmp_path, reg, state).read_text()
    assert "## Claims: 1 reproduced" in text and "Rates rose." in text and "Open questions: 1" in text
    assert "`registry/claims/local-x.yaml`" in text and "`registry/transcripts/local-x/`" in text


def test_a_run_finds_its_paper_key_in_the_registry(tmp_path):
    reg = tmp_path / "out" / "registry"
    r = run.Run(tmp_path / "out", run.Dataset("local", "x", "/d", "files-1"), None, None, None, False, "m", "main")
    reg.mkdir(parents=True)
    assert r.paper_key() == "local-x"   # a registry from before papers had keys
    shutil.copytree(REPO / "tools", reg / "tools")
    (reg / "targets").mkdir()
    (reg / "papers").mkdir()
    (reg / "papers" / "triage.yaml").write_text("{}\n")
    (reg / "targets" / "local.json").write_text(json.dumps({"targets": [
        {"archive": "local", "id": "x", "name": "Smith 2024", "path": "/d", "fingerprint": "files-1",
         "papers": [{"doi": "10.1/x", "title": "Smith 2024", "preprint": False}]}]}))
    assert r.paper_key() == "local-x"   # a dataset no paper lists: its records go under its folder
