"""OSF (osf.io), the Open Science Framework of the Center for Open Science: docs/archives.md, "OSF".

A dataset is an OSF project, component or registration, named by its GUID, five characters that ignore case
(OSF:qpc2d, folder osf-qpc2d); its DOI, when one has been minted, is 10.17605/OSF.IO/<GUID>. A project is not
versioned as a whole: each file in OSF Storage keeps its own numbered versions, so the target list pins a dataset
by the version and hashes of each file it lists, with published_version the time the project was last modified
when the list was built. A registration is a frozen copy of a project, and its files do not change. Metadata and
files of a public project are readable without an account, so agents read them directly: no stage(), no secrets.
"""

from . import Archive

ARCHIVE = Archive(
    key="osf", label="OSF", name="OSF", url="https://osf.io/{id}/", case="lower",
    access=("Read the files anonymously, as docs/archives.md says under \"OSF\". The target list gives every file "
            "with its provider, path, size, version, md5 and sha256, and a download address; read each file at the "
            "version listed, by adding ?version=<version> to its download address, with fsspec "
            "(block_size=2**20) or pandas, into memory. The same list comes, at the current versions, from "
            "https://api.osf.io/v2/{api_type}/{id}/files/, one storage provider at a time, following each folder's "
            "relationships.files and each page's links.next; check a file's current_version and hashes against "
            "the target list before relying on it, because a project's files can change. Start from a README or "
            "the project's wiki (https://api.osf.io/v2/{api_type}/{id}/wikis/), and the description in the "
            "target list. A file in a component has the component's GUID first in its path. Do not download files "
            "to disk."),
    list="osf.json", builder="tools/build_osf_targets.py",
    hosts=("api.osf.io", "osf.io", "files.osf.io", "*.osf.io", "storage.googleapis.com"),
)
