"""tools/submission.py: a run's results from a fork of encore-runner, as one file (docs/outside-runs.md)."""

from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import submission  # noqa: E402


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    root = tmp_path / "registry"
    for path, text in {"claims/other-2019.yaml": "x\n", "transcripts/demo-2020/old.md": "old\n",
                       "attempts/demo-2020-01.yaml": "id: demo-2020-01\n", "README.md": "readme\n"}.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    git(root.parent, "init", "-q", str(root))
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return root


def change(root: Path, files: dict[str, str], removed: tuple[str, ...] = ()) -> None:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    for path in removed:
        (root / path).unlink()
    git(root, "add", "-A")


def test_a_submission_carries_what_the_run_changed_and_lays_it_over_the_registry(registry, tmp_path):
    change(registry, {"claims/demo-2020.yaml": "claims\n", "entries/demo-2020/a b.py": "print(1)\n",
                      "attempts/demo-2020-02.yaml": "id: demo-2020-02\n", "transcripts/demo-2020/author.md": "t\n"},
           removed=("transcripts/demo-2020/old.md",))
    m = submission.pack(registry, "demo-2020", {"role": "author", "run_id": "7"}, tmp_path / "out")
    assert sorted(m["files"]) == ["attempts/demo-2020-02.yaml", "claims/demo-2020.yaml", "entries/demo-2020/a b.py",
                                  "transcripts/demo-2020/author.md"]
    assert m["removed"] == ["transcripts/demo-2020/old.md"] and m["role"] == "author" and m["paper"] == "demo-2020"

    # Laid over a fresh copy of the registry, it gives the same files.
    fresh = tmp_path / "fresh"
    git(tmp_path, "clone", "-q", str(registry), str(fresh))
    git(fresh, "checkout", "-q", "HEAD~0")
    subprocess.run(["git", "reset", "-q", "--hard", "HEAD"], cwd=fresh, check=True)
    submission.apply(tmp_path / "out" / submission.NAME, fresh, "demo-2020")
    assert (fresh / "entries/demo-2020/a b.py").read_text() == "print(1)\n"
    assert not (fresh / "transcripts/demo-2020/old.md").exists()
    assert (fresh / "attempts/demo-2020-01.yaml").exists()


def test_the_same_changes_make_the_same_file(registry, tmp_path):
    change(registry, {"claims/demo-2020.yaml": "claims\n"})
    a = submission.pack(registry, "demo-2020", {}, tmp_path / "a")
    b = submission.pack(registry, "demo-2020", {}, tmp_path / "b")
    assert a == b
    assert (tmp_path / "a" / submission.NAME).read_bytes() == (tmp_path / "b" / submission.NAME).read_bytes()


@pytest.mark.parametrize("files,removed", [
    ({"claims/other-2019.yaml": "changed\n"}, ()),   # another paper's
    ({"README.md": "changed\n"}, ()),                # the registry's own
    ({"docs/protocol.md": "x\n"}, ()),
    ({}, ("claims/other-2019.yaml",)),
])
def test_a_run_that_changed_anything_but_its_papers_files_cannot_be_packed(registry, tmp_path, files, removed):
    change(registry, files, removed)
    with pytest.raises(SystemExit, match="outside paper demo-2020"):
        submission.pack(registry, "demo-2020", {}, tmp_path / "out")


def forge(path: Path, members: list[tuple[tarfile.TarInfo, bytes | None]]) -> Path:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for info, data in members:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    path.write_bytes(gzip.compress(buf.getvalue()))
    return path


def member(name: str, data: bytes) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, data


def link(name: str, target: str) -> tuple[tarfile.TarInfo, None]:
    info = tarfile.TarInfo(name)
    info.type, info.linkname = tarfile.SYMTYPE, target
    return info, None


def manifest(files: dict[str, bytes], removed=(), paper="demo-2020") -> bytes:
    return json.dumps({"format": 1, "paper": paper, "files": {k: submission.sha256(v) for k, v in files.items()},
                       "removed": list(removed)}).encode()


def test_a_well_formed_submission_is_read(tmp_path):
    files = {"claims/demo-2020.yaml": b"c\n"}
    path = forge(tmp_path / "s.tar.gz", [member("manifest.json", manifest(files)),
                                         member("files/claims/demo-2020.yaml", b"c\n")])
    m, got = submission.read(path, "demo-2020")
    assert got == files and m["paper"] == "demo-2020"


@pytest.mark.parametrize("members,error", [
    # contents that are not what the manifest says
    ([member("manifest.json", manifest({"claims/demo-2020.yaml": b"c\n"})),
      member("files/claims/demo-2020.yaml", b"edited\n")], "do not match the manifest"),
    # a file the manifest does not name
    ([member("manifest.json", manifest({})), member("files/claims/demo-2020.yaml", b"c\n")], "not the ones"),
    # a path out of the registry
    ([member("manifest.json", manifest({"entries/demo-2020/../../x": b"x"})),
      member("files/entries/demo-2020/../../x", b"x")], "outside paper"),
    # another paper's file
    ([member("manifest.json", manifest({"claims/other-2019.yaml": b"x"})),
      member("files/claims/other-2019.yaml", b"x")], "outside paper"),
    # removing what is not the paper's
    ([member("manifest.json", manifest({}, removed=["README.md"]))], "outside paper"),
    # anything but a file
    ([member("manifest.json", manifest({})), link("files/entries/demo-2020/link", "/etc/passwd")],
     "not a regular file"),
    # no manifest
    ([member("files/claims/demo-2020.yaml", b"c\n")], "no manifest"),
])
def test_a_submission_that_is_not_one_papers_files_as_its_manifest_says_is_refused(tmp_path, members, error):
    path = forge(tmp_path / "s.tar.gz", members)
    with pytest.raises(SystemExit, match=error):
        submission.read(path)


def test_a_submission_for_another_paper_is_refused(tmp_path):
    path = forge(tmp_path / "s.tar.gz", [member("manifest.json", manifest({}, paper="other-2019"))])
    with pytest.raises(SystemExit, match="not 'demo-2020'"):
        submission.read(path, "demo-2020")


# An attempt's state between runs, on the runner's own branch.

def test_a_state_is_the_papers_files_and_its_digest_changes_with_any_of_them(registry):
    assert sorted(submission.state(registry, "demo-2020")) == ["attempts/demo-2020-01.yaml",
                                                               "transcripts/demo-2020/old.md"]
    before = submission.digest(registry, "demo-2020")
    change(registry, {"claims/other-2019.yaml": "another paper's\n", "README.md": "changed\n"})
    assert submission.digest(registry, "demo-2020") == before        # not the paper's files
    change(registry, {"transcripts/demo-2020/old.md": "old, edited\n"})
    edited = submission.digest(registry, "demo-2020")
    assert edited != before
    change(registry, {"summaries/demo-2020-01.md": "the recorder's notes\n"})
    assert submission.digest(registry, "demo-2020") not in (before, edited)


def test_laying_a_state_replaces_the_papers_files_and_leaves_the_rest(registry, tmp_path):
    state = tmp_path / "state"
    for path, text in {"claims/demo-2020.yaml": "claims\n", "transcripts/demo-2020/claims.md": "t\n",
                       ".encore/attempt.json": "{}\n", "claims/other-2019.yaml": "not laid\n"}.items():
        (state / path).parent.mkdir(parents=True, exist_ok=True)
        (state / path).write_text(text)
    assert submission.lay(state, registry, "demo-2020") == 2
    # The registry's own copies of the paper's files went, the state's came, and no other file moved.
    assert sorted(submission.state(registry, "demo-2020")) == ["claims/demo-2020.yaml",
                                                               "transcripts/demo-2020/claims.md"]
    assert (registry / "claims/other-2019.yaml").read_text() == "x\n" and not (registry / ".encore").exists()
    assert submission.digest(registry, "demo-2020") == submission.digest(state, "demo-2020")


def test_the_ledger_lists_the_runs_in_order_and_keeps_to_one_attempt(tmp_path):
    run = {"role": "claims", "run_url": "https://github.com/lab/encore-runner/actions/runs/1", "result": "success",
           "artifact": "7", "state_before": "a" * 64, "state_after": "b" * 64}
    submission.record(tmp_path, "demo-2020", "encorescience/encore-registry", "c" * 40, run)
    ledger = submission.record(tmp_path, "demo-2020", "encorescience/encore-registry", "c" * 40,
                               {**run, "role": "claims-check"})
    assert [r["role"] for r in ledger["runs"]] == ["claims", "claims-check"] and ledger["base_sha"] == "c" * 40
    assert json.loads((tmp_path / submission.LEDGER).read_text()) == ledger
    with pytest.raises(SystemExit, match="base_sha"):
        submission.record(tmp_path, "demo-2020", "encorescience/encore-registry", "d" * 40, run)


def test_the_recorders_notes_are_the_papers_and_another_papers_are_not():
    assert submission.belongs("docs/pilot-notes/demo-2020-02.md", "demo-2020")
    assert submission.belongs("summaries/demo-2020-02.md", "demo-2020")
    assert not submission.belongs("summaries/other-2019-01.md", "demo-2020")
    assert not submission.belongs("docs/protocol.md", "demo-2020")
