"""Zenodo (zenodo.org), CERN's general-purpose repository: docs/archives.md, "Zenodo".

A dataset is a Zenodo record, named by its record id (https://zenodo.org/records/3924718 is ZENODO:3924718, folder
zenodo-3924718), which is also its DOI's suffix (10.5281/zenodo.3924718). Each version of a deposit is a record of
its own, with its own id and DOI, and the concept DOI, the deposit's, resolves to the latest; so a record id pins a
version, and published_version is the record id. The target list also gives the deposit's concept id and its other
versions' ids, so that a paper citing another version or the concept DOI still names the dataset. Open records'
metadata and files are readable without an account, so agents read them directly: no stage(), no secrets.
"""

from . import Archive

ARCHIVE = Archive(
    key="zenodo", label="ZENODO", name="Zenodo", url="https://zenodo.org/records/{id}",
    access=("Read the files of record {id} (DOI 10.5281/zenodo.{id}) anonymously, as docs/archives.md says under "
            "\"Zenodo\". The target list gives every file with its key, size and MD5; the same list comes from "
            "https://zenodo.org/api/records/{id} (under files). Read each file from "
            "https://zenodo.org/api/records/{id}/files/<key>/content with fsspec (block_size=2**20), opening a zip "
            "in place with zipfile, or with pandas, into memory, and check its MD5 against the list when you read "
            "it whole. Start from a README among the files and the record's description in the target list. Do not "
            "download whole files to disk."),
    list="zenodo.json", builder="tools/build_zenodo_targets.py",
    hosts=("zenodo.org", "*.zenodo.org"),
)
