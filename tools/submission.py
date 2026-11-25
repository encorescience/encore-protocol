"""A run's results as one file, for a run made from encore-runner or a fork of it (docs/outside-runs.md).

    python tools/submission.py pack --paper P --out DIR [--meta KEY=VALUE ...]
    python tools/submission.py apply SUBMISSION --paper P [--into DIR]
    python tools/submission.py show SUBMISSION
    python tools/submission.py digest --paper P [--root DIR]
    python tools/submission.py lay FROM --paper P [--into DIR]
    python tools/submission.py record STATE --paper P --registry R --base-sha SHA --role ROLE --run-url URL ...

A run started from a fork of encore-runner reads the registry but cannot write to it. Its last job (`submit` in
attempt.yml and papers.yml) gathers what the run changed in the registry's files, as `pack` describes, into
`submission.tar.gz`, which GitHub then signs as made by that workflow. The registry's intake workflow checks the
signature, lays the files over main with `apply`, and opens a pull request for a person to merge.

`pack` reads the changes a run left staged in a checkout of the registry (`git add`), against the commit checked out:
every added or changed file goes in under `files/`, and `manifest.json` names each with its SHA-256, lists the files
removed, and carries what the workflow says about the run (`--meta`). Only one paper's files may change: its claims
file, attempt records, entry, questions and transcripts.

An attempt made from encore-runner keeps its state between runs on the runner's own branch, attempt/<paper>: the
paper's files, laid out as in the registry, and `.encore/attempt.json`, the ledger of its runs. `lay` puts the
paper's files of one directory in place of another's, which is how a run starts from that state over a checkout of
the registry, and how the state takes a run's results. `digest` names a state: one SHA-256 over the paper's files and
their contents. Each run's submission carries the digest of the state it started from (`state_before`), so that the
registry, laying the submissions one over the other from the commit of main the attempt began at, can tell that each
run started from what the run before it left. `record` adds a run to the ledger.

`apply` lays a submission over a checkout. It refuses a submission whose files are not the paper's, whose contents do
not match the manifest, or whose archive holds anything but regular files, so that a submission can only ever change
the paper it names.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

FORMAT = 1
KEY = r"[a-z0-9]+(?:-[a-z0-9]+)*"
NAME = "submission.tar.gz"


def paper_files(paper: str) -> list[str]:
    """The paths a submission for `paper` may change, as regular expressions."""
    p = re.escape(paper)
    return [
        rf"claims/{p}\.yaml",
        rf"attempts/{p}-[0-9]{{2}}\.yaml",
        rf"entries/{p}/[^\0]+",
        rf"questions/{p}\.yaml",
        rf"questions/{p}/[^/]+\.yaml",
        rf"transcripts/{p}/[^\0]+",
        # The recorder's notes on a finished attempt.
        rf"docs/pilot-notes/{p}-[0-9]{{2}}\.md",
        rf"summaries/{p}-[0-9]{{2}}\.md",
    ]


def belongs(path: str, paper: str) -> bool:
    parts = path.split("/")
    if path.startswith("/") or any(x in ("", ".", "..") for x in parts) or "\\" in path:
        return False
    return any(re.fullmatch(rx, path) for rx in paper_files(paper))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


LEDGER = ".encore/attempt.json"
# Where a paper's files are, to look no further than these in a checkout of the registry.
PLACES = ("claims", "attempts", "entries", "questions", "transcripts", "docs/pilot-notes", "summaries")


def state(root: Path, paper: str) -> dict[str, bytes]:
    """The paper's files under `root`, by path. Only regular files: a link is not part of a state."""
    found = {}
    for place in PLACES:
        top = root / place
        if not top.is_dir():
            continue
        for f in sorted(top.rglob("*")):
            rel = f.relative_to(root).as_posix()
            if f.is_file() and not f.is_symlink() and belongs(rel, paper):
                found[rel] = f.read_bytes()
    return found


def digest_of(files: dict[str, bytes]) -> str:
    listing = "".join(f"{sha256(data)}  {path}\n" for path, data in sorted(files.items()))
    return sha256(listing.encode())


def digest(root: Path, paper: str) -> str:
    """One name for the paper's files under `root` and their contents."""
    return digest_of(state(root, paper))


def lay(src: Path, dest: Path, paper: str) -> int:
    """Put the paper's files of `src` in place of the paper's files of `dest`; the rest of `dest` is left alone."""
    if not re.fullmatch(KEY, paper):
        raise SystemExit(f"Not a paper key: {paper!r}")
    files = state(src, paper)
    for x in state(dest, paper):
        (dest / x).unlink()
    for x, data in files.items():
        (dest / x).parent.mkdir(parents=True, exist_ok=True)
        (dest / x).write_bytes(data)
    return len(files)


def record(state_dir: Path, paper: str, registry: str, base_sha: str, run: dict) -> dict:
    """Add a run to the ledger of the attempt whose state is in `state_dir`, starting the ledger if there is none."""
    path = state_dir / LEDGER
    ledger = json.loads(path.read_text()) if path.is_file() else {
        "format": FORMAT, "paper": paper, "registry": registry, "base_sha": base_sha, "runs": []}
    for key, value in (("paper", paper), ("registry", registry), ("base_sha", base_sha)):
        if ledger.get(key) != value:
            raise SystemExit(f"The ledger's {key} is {ledger.get(key)!r}, and this run's is {value!r}")
    ledger["runs"].append(run)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=1) + "\n")
    return ledger


def staged(root: Path) -> tuple[list[str], list[str]]:
    """The files the index adds or changes, and the files it removes, against HEAD."""
    out = subprocess.run(["git", "diff", "--cached", "--name-status", "--no-renames", "-z", "HEAD"],
                         cwd=root, check=True, capture_output=True).stdout.decode()
    fields = out.split("\0")
    changed, removed = [], []
    for status, path in zip(fields[0::2], fields[1::2]):
        (removed if status == "D" else changed).append(path)
    return sorted(changed), sorted(removed)


def pack(root: Path, paper: str, meta: dict, out: Path) -> dict:
    if not re.fullmatch(KEY, paper):
        raise SystemExit(f"Not a paper key: {paper!r}")
    changed, removed = staged(root)
    stray = [x for x in changed + removed if not belongs(x, paper)]
    if stray:
        raise SystemExit("Changes outside paper " + paper + ": " + ", ".join(stray))
    contents = {x: (root / x).read_bytes() for x in changed}
    manifest = {"format": FORMAT, "paper": paper, **meta,
                "files": {x: sha256(b) for x, b in contents.items()}, "removed": removed}
    out.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        add(tar, "manifest.json", (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode())
        for x in sorted(contents):
            add(tar, f"files/{x}", contents[x])
    # mtime 0, so that the same changes always make the same file.
    (out / NAME).write_bytes(gzip.compress(buf.getvalue(), mtime=0))
    return manifest


def add(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = len(data), 0o644, 0
    tar.addfile(info, io.BytesIO(data))


def read(path: Path, paper: str | None = None) -> tuple[dict, dict[str, bytes]]:
    """The manifest and files of a submission, after checking each against the other and against the paper."""
    files: dict[str, bytes] = {}
    manifest = None
    with tarfile.open(path, mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isreg():
                raise SystemExit(f"{m.name}: not a regular file. A submission holds only files.")
            data = tar.extractfile(m).read()
            if m.name == "manifest.json":
                manifest = json.loads(data)
            elif m.name.startswith("files/"):
                if m.name[6:] in files:
                    raise SystemExit(f"{m.name}: twice in the submission")
                files[m.name[6:]] = data
            else:
                raise SystemExit(f"{m.name}: not part of a submission")
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise SystemExit("The submission has no manifest of format 1")
    p = manifest.get("paper")
    if paper is not None and p != paper:
        raise SystemExit(f"The submission is for {p!r}, not {paper!r}")
    if not isinstance(p, str) or not re.fullmatch(KEY, p):
        raise SystemExit(f"The manifest names no paper key: {p!r}")
    named, removed = manifest.get("files") or {}, manifest.get("removed") or []
    if set(named) != set(files):
        raise SystemExit("The files in the submission are not the ones its manifest names")
    for x, data in files.items():
        if named[x] != sha256(data):
            raise SystemExit(f"{x}: its contents do not match the manifest")
    stray = [x for x in list(files) + list(removed) if not belongs(x, p)]
    if stray:
        raise SystemExit("Files outside paper " + p + ": " + ", ".join(sorted(stray)))
    if set(files) & set(removed):
        raise SystemExit("A file is both in the submission and removed by it")
    return manifest, files


def apply(path: Path, root: Path, paper: str | None = None) -> dict:
    manifest, files = read(path, paper)
    for x in manifest.get("removed") or []:
        (root / x).unlink(missing_ok=True)
    for x, data in files.items():
        (root / x).parent.mkdir(parents=True, exist_ok=True)
        (root / x).write_bytes(data)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("pack")
    a.add_argument("--paper", required=True)
    a.add_argument("--out", required=True, type=Path)
    a.add_argument("--meta", action="append", default=[], metavar="KEY=VALUE")
    a.add_argument("--root", default=Path("."), type=Path)
    b = sub.add_parser("apply")
    b.add_argument("submission", type=Path)
    b.add_argument("--paper")
    b.add_argument("--into", default=Path("."), type=Path)
    c = sub.add_parser("show")
    c.add_argument("submission", type=Path)
    d = sub.add_parser("digest")
    d.add_argument("--paper", required=True)
    d.add_argument("--root", default=Path("."), type=Path)
    e = sub.add_parser("lay")
    e.add_argument("src", type=Path)
    e.add_argument("--paper", required=True)
    e.add_argument("--into", default=Path("."), type=Path)
    f = sub.add_parser("record")
    f.add_argument("state", type=Path)
    for name in ("paper", "registry", "base-sha", "role", "run-url", "result", "before", "after"):
        f.add_argument(f"--{name}", required=True)
    f.add_argument("--artifact", default="")
    args = ap.parse_args(argv)
    if args.cmd == "digest":
        print(digest(args.root, args.paper))
        return 0
    if args.cmd == "lay":
        print(f"Laid {lay(args.src, args.into, args.paper)} files of {args.paper} from {args.src} over {args.into}")
        return 0
    if args.cmd == "record":
        ledger = record(args.state, args.paper, args.registry, args.base_sha,
                        {"role": args.role, "run_url": args.run_url, "result": args.result, "artifact": args.artifact,
                         "state_before": args.before, "state_after": args.after})
        print(f"Run {len(ledger['runs'])} of the attempt on {args.paper}: {args.role}")
        return 0
    if args.cmd == "pack":
        meta = dict(kv.split("=", 1) for kv in args.meta)
        m = pack(args.root, args.paper, meta, args.out)
        print(f"{len(m['files'])} files, {len(m['removed'])} removed, for {args.paper}: {args.out / NAME}")
    elif args.cmd == "apply":
        m = apply(args.submission, args.into, args.paper)
        print(f"Laid {len(m['files'])} files of {m['paper']} over {args.into}, removed {len(m['removed'])}")
    else:
        print(json.dumps(read(args.submission)[0], indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
