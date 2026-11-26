"""Dryad (datadryad.org), a general-purpose repository: docs/archives.md, "Dryad".

A dataset is named by its DOI's suffix without "dryad." (10.5061/dryad.bvq83bkk9 is bvq83bkk9); Dryad DOIs
ignore case. published_version is the id of the dataset's version in Dryad's API, which pins it. Dryad lets no
one download a file without a bearer token, and the commands an agent runs never see credentials, so stage()
downloads the pinned version's files before the agent starts, with a token from the API account's client id
and secret, and checks each against the digest the file list gives: SHA-256, or for older files, which Dryad lists
with an MD5 only (DRYAD:m31b1h7, 2019), the MD5.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from . import Archive

API = "https://datadryad.org/api/v2"


def _token() -> str:
    body = urllib.parse.urlencode({"grant_type": "client_credentials",
                                   "client_id": os.environ["DRYAD_CLIENT_ID"],
                                   "client_secret": os.environ["DRYAD_CLIENT_SECRET"]}).encode()
    req = urllib.request.Request("https://datadryad.org/oauth/token", data=body)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["access_token"]


class _NoAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    # A download answers 302 to a presigned S3 URL, which refuses a request that also carries the bearer header.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            new.remove_header("Authorization")
        return new


def _listed_digests(version: str) -> dict:
    """Each file's digest as the version's public file list gives it, by file id: (algorithm, hex digest)."""
    url = f"{API}/versions/{version}/files"
    out = {}
    while url:
        with urllib.request.urlopen(url, timeout=60) as r:
            page = json.load(r)
        for f in page["_embedded"]["stash:files"]:
            algo = {"sha-256": "sha256", "md5": "md5"}.get((f.get("digestType") or "").lower())
            if algo and f.get("digest"):
                out[int(f["_links"]["self"]["href"].rstrip("/").split("/")[-1])] = (algo, f["digest"].lower())
        nxt = (page.get("_links") or {}).get("next", {}).get("href")
        url = urllib.parse.urljoin(API, nxt) if nxt else None
    return out


def _expected(target: dict, f: dict, listed: dict | None) -> tuple[str, str]:
    """The digest a file is checked against: the SHA-256 of the registry's list, or, for a file listed without one
    (Dryad gives older files an MD5 only), the digest of the version's file list."""
    if f.get("sha256"):
        return "sha256", f["sha256"]
    if listed and int(f["file_id"]) in listed:
        return listed[int(f["file_id"])]
    raise RuntimeError(f"DRYAD:{target['id']} {f['path']}: no SHA-256 or MD5 for it, in the registry's list or Dryad's")


def stage(target: dict, root: Path) -> Path:
    dest = root / "dryad" / target["id"] / str(target["published_version"])
    listed = _listed_digests(str(target["published_version"])) if any(not f.get("sha256") for f in target["files"]) else None
    want = {f["path"]: _expected(target, f, listed) for f in target["files"]}
    def ok(f, data: bytes) -> bool:
        algo, digest = want[f["path"]]
        return hashlib.new(algo, data).hexdigest() == digest
    todo = [f for f in target["files"] if not ((dest / f["path"]).is_file() and ok(f, (dest / f["path"]).read_bytes()))]
    if not todo:
        return dest
    bearer = _token()
    opener = urllib.request.build_opener(_NoAuthOnRedirect)
    for f in todo:
        req = urllib.request.Request(f"{API}/files/{f['file_id']}/download",
                                     headers={"Authorization": f"Bearer {bearer}"})
        with opener.open(req, timeout=300) as r:
            data = r.read()
        if not ok(f, data):
            algo, digest = want[f["path"]]
            raise RuntimeError(f"DRYAD:{target['id']} {f['path']}: {algo.upper()} {hashlib.new(algo, data).hexdigest()}, "
                               f"not the listed {digest}")
        path = dest / f["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return dest


ARCHIVE = Archive(
    key="dryad", label="DRYAD", name="Dryad", url="https://doi.org/10.5061/dryad.{id}", case="lower",
    access=("The files of the pinned version ({published_version}) are already in /tmp/dryad/{id}/"
            "{published_version}/, downloaded from Dryad and checked against their listed digests before you started, "
            "because Dryad needs a token that your commands cannot hold (docs/archives.md, \"Dryad\"). Read them "
            "there, in place, into memory (pandas, openpyxl, zipfile; list every sheet of a workbook); do not copy "
            "or change them, and do not try to download them from Dryad. Dryad's metadata and file list are "
            "public: https://datadryad.org/api/v2/versions/{published_version}/files."),
    list="dryad.json", builder="tools/build_dryad_targets.py",
    hosts=("datadryad.org", "zenodo.org", "*.zenodo.org"),
    secrets=("DRYAD_CLIENT_ID", "DRYAD_CLIENT_SECRET"), stage=stage,
)
