"""A run's results as one file, for a run made from encore-runner or a fork of it (docs/outside-runs.md).

    python tools/submission.py pack --paper P --out DIR [--meta KEY=VALUE ...]
    python tools/submission.py apply SUBMISSION --paper P [--into DIR]
    python tools/submission.py show SUBMISSION

A run started from a fork of encore-runner reads the registry but cannot write to it. Its last job (`submit` in
attempt.yml and papers.yml) gathers what the run changed in the registry's files, as `pack` describes, into
`submission.tar.gz`, which GitHub then signs as made by that workflow. The registry's intake workflow checks the
signature, lays the files over main with `apply`, and opens a pull request for a person to merge.

`pack` reads the changes a run left staged in a checkout of the registry (`git add`), against the commit checked out:
every added or changed file goes in under `files/`, and `manifest.json` names each with its SHA-256, lists the files
removed, and carries what the workflow says about the run (`--meta`). Only one paper's files may change: its claims
file, attempt records, entry, questions and transcripts.

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
    ]


def belongs(path: str, paper: str) -> bool:
    parts = path.split("/")
    if path.startswith("/") or any(x in ("", ".", "..") for x in parts) or "\\" in path:
        return False
    return any(re.fullmatch(rx, path) for rx in paper_files(paper))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    args = ap.parse_args(argv)
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
