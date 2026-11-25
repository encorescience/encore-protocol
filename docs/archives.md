# Archives

The registry tests papers against data in public archives. It began with one,
the DANDI Archive. The protocol is written for any archive. What is particular
to an archive (how its datasets are named, versioned and read) is here, and an
agent is pointed to its archive's section.

A dataset is keyed as `<archive>:<id>` and shown as `<LABEL>:<id>`, for example
`DANDI:000003`. Its files in this repository (`claims/`, `questions/`,
`transcripts/`, the `attempt/` branch, the paper store) are under its folder
name: the identifier alone for DANDI, which the registry began with, and
`<archive>-<id>` for any other archive. Each archive is an adapter, a module in `tools/archives/` ("Adding an archive",
below), and `tools/datasets.py` turns one form of a dataset's name into another.
The workflows take a dataset in any of these forms.

## DANDI

- **Datasets.** A dandiset, identified by six digits (`000003`). Targets are the
  public dandisets whose metadata names a paper (`targets/dandisets.json`, built
  by `tools/build_targets.py` and refreshed daily by the Track DANDI workflow).
- **Versions.** A published version (`0.220126.1855`) is fixed and has a DOI,
  `10.48324/dandi.<id>/<version>`. The draft can change. Pin the version the
  paper cites, or the latest published one. For a draft, record its
  modification time under `dataset: modified` in the attempt.
- **Reading.** List the assets and read metadata with the DANDI REST API
  (`https://api.dandiarchive.org/api/dandisets/<id>/versions/<version>/` and its
  `assets/` endpoint). Read NWB files by streaming them: open each asset's S3
  URL with `remfile` and `h5py`, and read it with `pynwb`. Do not download files
  to disk.
- **In an entry.** The entry names the dataset as `dandi:<id>/<version>` under
  `related`. The helper module keeps the version in one constant.

## CRCNS

- **Datasets.** A CRCNS data set, identified by its short name (`ret-1`,
  `hc-3`), with a DOI of its own (`10.6080/...`). The registry's list is
  `targets/crcns.json`, written by hand; for now it holds one data set, to test
  the pipeline beyond DANDI.
- **Versions.** CRCNS data sets are not versioned. Record the version as
  `unversioned`, with the data set's DOI under `dataset: doi`, and give in the
  notebook header the MD5 sums from the data set's `checksums.md5` for the
  files read, so a later change is detectable.
- **Reading.** The files are in the public S3 bucket `crcnsarchive` (region
  us-west-2), under `<id>/`, readable without an account at
  `https://crcnsarchive.s3-us-west-2.amazonaws.com/<id>/<file>`; list a data
  set with `?list-type=2&prefix=<id>/` on the bucket's address. The site
  crcns.org asks for a login to download; the bucket does not. Most data sets
  are zip files of MATLAB or other files: open the zip in place with
  `fsspec.open(url, block_size=2**20).open()` and Python's `zipfile`, which
  read only the parts needed over range requests (`remfile` lacks what
  `zipfile` needs to read a member), and load members in memory
  (`scipy.io.loadmat`, or `h5py` for MATLAB 7.3 files). Do not download whole
  files to disk. Some data sets keep their files under `<id>/live/` instead
  (with older ones under `<id>/old/`). The data set's `docs/` folder describes
  the files; its text is also under `paper/` as `<id>.data-description.txt`
  (with the PDF where there is one), put in the paper store with the paper.
- **In an entry.** The entry names the data set as `crcns:<id>/unversioned`
  under `related`.

## EBRAINS

- **Datasets.** A dataset version in the EBRAINS Knowledge Graph. The registry
  names it by its DOI's suffix: `10.25493/Q0FG-1X8` is `EBRAINS:Q0FG-1X8`, in
  folders `ebrains-q0fg-1x8` (EBRAINS DOIs ignore case). The version's
  Knowledge Graph id, a UUID, is `kg_id` in the registry's list,
  `targets/ebrains.json` (written by hand; for now it holds one dataset, to
  test the pipeline beyond DANDI); its record is at
  `https://search.kg.ebrains.eu/instances/<kg_id>`. Only datasets marked "free
  access" can be read without an account.
- **Versions.** Each version has its own DOI and Knowledge Graph id, so either pins it. Record the
  version's name (`v1`) under `dataset: version` and its DOI under
  `dataset: doi`.
- **Reading.** List the files with
  `https://data-proxy.ebrains.eu/api/v1/public/datasets/<kg_id>?limit=500` (JSON,
  under `objects`). Read a file at
  `https://data-proxy.ebrains.eu/api/v1/public/datasets/<kg_id>/<file>`, which
  redirects to the object at CSCS; open it with `fsspec` and read it into memory
  (`scipy.io.loadmat` for MATLAB files, `h5py` for MATLAB 7.3 or HDF5). The
  data proxy answers no HEAD requests, so open files for reading only. Do not
  download whole files to disk. The dataset's data descriptor (a PDF among its
  files) describes them.
- **In an entry.** The entry names the dataset as `ebrains:<doi suffix>/<version>`
  under `related`.

## Dryad

- **Datasets.** A Dryad dataset, named by its DOI's suffix without the
  `dryad.` prefix: `10.5061/dryad.bvq83bkk9` is `DRYAD:bvq83bkk9`, in folders
  `dryad-bvq83bkk9` (Dryad DOIs ignore case). The registry's list,
  `targets/dryad.json`, is built from chosen DOIs by
  `tools/build_dryad_targets.py`, which reads each dataset's metadata, latest
  version and file list from the public API v2; for now it holds three datasets
  outside neuroscience, to test the pipeline on a general-purpose repository.
  The papers are the dataset's related works marked `primary_article` (and
  `preprint`); related works marked `software` are the paper's code, usually on
  Zenodo.
- **Versions.** The DOI always resolves to the latest version, and versions
  have no DOIs of their own. Each version has an id in the API
  (`/api/v2/versions/<id>`), which is `published_version` in the target list
  and pins it; a version's number (`versionNumber`) counts metadata edits as
  well as file changes, so it is not a pin. Record the version id under
  `dataset: version` and the DOI under `dataset: doi`, and give in the notebook
  header the SHA-256 digest of each file read, which the file list gives.
  List the versions with `/api/v2/datasets/<url-encoded doi:...>/versions`.
- **Reading.** Metadata, versions and file lists are public:
  `https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.<id>` and
  `/api/v2/versions/<version id>/files`. Downloading a file is not:
  `/api/v2/files/<file id>/download` answers 401 without a bearer token, and
  the website's download links (`/downloads/file_stream/<file id>`) answer 403
  to scripts. A token comes from an API account, which a person makes from
  their Dryad account (an ORCID login), "My account", "API account"; its client
  id and secret are exchanged for a token, which lasts 10 hours, at
  `POST https://datadryad.org/oauth/token` (`grant_type=client_credentials`).
  The download answers 302 to a presigned URL in Dryad's S3 bucket, which
  answers 400 if the bearer header comes with it.
- **Staged, not streamed.** An agent's commands never see credentials (the
  workflows and `encore check` strip them), so an agent cannot download from
  Dryad. Before an agent starts, `tools/stage_files.py` (the adapter's
  `stage()`) downloads every file of the pinned version to
  `/tmp/dryad/<id>/<version id>/` and checks each against the SHA-256 the file
  list gives; the agent reads them there, in place, into memory
  (`pandas.read_excel` for the Excel workbooks most datasets hold, listing every
  sheet; `zipfile` for zips). The notebooks read the same paths. The
  credentials are the secrets `DRYAD_CLIENT_ID` and `DRYAD_CLIENT_SECRET` in
  the workflows that run agents and entries (`attempt.yml`, `check.yml`), and
  the same environment variables for `encore check`. The dataset's README
  (`README.md`, shown also on its page) describes the files and columns; there
  may be none, and a data dictionary may be a data file of its own
  (`Metadata.csv`).
- **In an entry.** The entry names the dataset as `dryad:<id>/<version id>`
  under `related`, and gives in the notebook header the SHA-256 of each file
  read.

## Figshare

- **Datasets.** A Figshare item of type dataset, named by its article id:
  `https://figshare.com/articles/dataset/<title>/24949470` is
  `FIGSHARE:24949470`, in folders `figshare-24949470`. Institutional and
  publisher portals (`springernature.figshare.com`, `<university>.figshare.com`)
  are views of the same repository, with the same ids and API. Most Figshare
  items are figures and journals' supplementary tables (PLOS's `S1 Data`, one
  table per item), so the registry's list, `targets/figshare.json`, is built
  from chosen ids by `tools/build_figshare_targets.py`, which reads each
  item's metadata, version and file list from the public API v2; for now it
  holds three Scientific Data deposits outside neuroscience and ecology, to
  test the pipeline on a general-purpose repository. An item names its paper
  only sometimes (a related material marked `IsSupplementTo`, or its
  `resource_doi`); otherwise the paper's DOI is given to the builder
  (`<id>=<paper DOI>`), from the paper's data statement.
- **Versions.** Each version has its own DOI,
  `10.6084/m9.figshare.<id>.v<n>`; the DOI without `.v<n>` resolves to the
  latest. The version number is `published_version` in the target list and
  pins it, with its DOI under `doi`. Record the number under
  `dataset: version` and the versioned DOI under `dataset: doi`, and give in
  the notebook header the MD5 of each file read, which the file list gives
  (`computed_md5`). A paper may cite an earlier version than the latest, or
  the item with no version at all; pin the one it cites, or the latest. A new
  version gives changed files new ids and keeps the old ones downloadable.
  List the versions with `/v2/articles/<id>/versions`.
- **Reading.** Everything is public, with no account: the version's metadata
  and files at `https://api.figshare.com/v2/articles/<id>/versions/<n>` (under
  `files`: `id`, `name`, `size`, `computed_md5`), and each file at
  `https://ndownloader.figshare.com/files/<file id>`, which answers 302 to a
  presigned URL in Figshare's S3 buckets (`s3-eu-west-1.amazonaws.com`) that
  expires in ten seconds. Open that address with
  `fsspec.open(url, block_size=2**20)`, which asks `ndownloader` again for each
  range it reads, so the expiry does not matter, and read into memory
  (`pandas`, `openpyxl` listing every sheet, `zipfile`). Do not download whole
  files to disk, and do not use `figshare.com/ndownloader/...`, which answers
  scripts with a bot check. A README, if any, is a file of its own
  (`README.txt`, or a PDF); otherwise the item's description, in its metadata,
  is the only documentation, with the data descriptor paper. CSV files may use
  `;` as the separator.
- **In an entry.** The entry names the dataset as `figshare:<id>/<version>`
  under `related`, and gives in the notebook header the MD5 of each file read.

## OpenNeuro

- **Datasets.** An OpenNeuro dataset, named by its accession number:
  `https://openneuro.org/datasets/ds002778` is `OPENNEURO:ds002778`, in folders
  `openneuro-ds002778`. Every dataset is in BIDS, mostly human MRI, EEG, MEG
  and iEEG. The registry's list, `targets/openneuro.json`, is built from
  chosen accession numbers by `tools/build_openneuro_targets.py`, which reads
  each snapshot's metadata and file tree from OpenNeuro's GraphQL API and
  records its layout (how many files of each BIDS kind, with their sizes),
  the BIDS validator's errors, whether it has events files and derivatives,
  and its top-level files with their checksums; for now it holds three
  datasets with a paper in PubMed Central, one each of scalp EEG, iEEG and
  fMRI, to test the pipeline on OpenNeuro. A dataset names its paper in
  several places, none required: the paper DOI fields of OpenNeuro's metadata
  (`associatedPaperDOI`, and `openneuroPaperDOI`, which is often a whole
  citation), and `ReferencesAndLinks` and `HowToAcknowledge` in
  `dataset_description.json`, as DOIs, PubMed links, journal links or bare
  citations. The builder reads DOIs, PubMed ids and Nature links from all of
  them; otherwise give the paper's DOI to the builder (`<id>=<paper DOI>`).
- **Versions.** A snapshot, tagged `1.0.5` (older datasets also have
  `00001`-style tags), is fixed, and has its own DOI,
  `10.18112/openneuro.<id>.v<tag>`, and a git commit (`git_commit` in the
  target list): each dataset is a DataLad dataset, mirrored on GitHub as
  `OpenNeuroDatasets/<id>` with a tag per snapshot. The tag is
  `published_version` in the target list and pins it. Record the tag under
  `dataset: version` and the snapshot DOI under `dataset: doi`. The draft
  can change, and so can the bucket's unversioned keys, which hold the latest
  snapshot. OpenNeuro's own size for a snapshot leaves out `derivatives/`,
  which can be most of the data (`size_gb` in the target list counts them;
  `snapshot_size_gb` does not).
- **Reading.** Everything is public, with no account. List a snapshot's files
  by POSTing a query to `https://openneuro.org/crn/graphql`:

  ```graphql
  { snapshot(datasetId: "ds002778", tag: "1.0.5") {
      description { Name ReferencesAndLinks HowToAcknowledge }
      files(recursive: true) { filename size annexed directory id urls } } }
  ```

  Each file's `urls[0]` is pinned to that snapshot: a large (git-annex) file is
  an S3 object version in the public bucket `openneuro.org` (us-east-1),
  `https://s3.amazonaws.com/openneuro.org/<id>/<path>?versionId=<version>`,
  sometimes under another dataset's prefix when the file is shared; a small
  file kept in git (TSV, JSON, README) may instead be
  `https://openneuro.org/crn/datasets/<id>/objects/<git blob>?filename=<path>`.
  Use the URL as given. Read TSV and JSON files whole
  (`pandas.read_csv(url, sep="\t")`, `json.load`); open large files with
  `fsspec.open(url, block_size=2**20)`, which reads ranges of the S3 object
  version, and read only what a claim needs (`mne` reads EDF and BDF headers,
  `nibabel` NIfTI headers). The git object addresses answer no range
  requests. Do not download whole files or datasets to disk; imaging files
  (NIfTI) and recordings run to hundreds of megabytes each. `s3fs` with
  `anon=True` and `version_aware=True` reads the same object versions, and
  `datalad` or git-annex clones the GitHub mirror at the snapshot's tag, but
  neither is needed.
- **Checksums.** A file's `id` is its checksum: for an annexed file, a
  git-annex key, `MD5E-s<size>--<md5>.<ext>` or `SHA256E-s<size>--<sha256>.<ext>`;
  for a file in git, the git blob's SHA-1 (`sha1(b"blob <size>\0" + content)`,
  `git hash-object`). Give in the notebook header the snapshot's tag and the
  `id` of each file read. (The S3 ETag is an MD5 only for objects uploaded in
  one part, so do not rely on it.)
- **BIDS.** Start from `dataset_description.json`, the `README`,
  `participants.tsv` and its `participants.json`, then the task's `*_events.tsv`
  files and their JSON sidecars (`*_events.json`, `*_bold.json`, `*_eeg.json`),
  which a BIDS inheritance rule lets sit at the top level for all subjects.
  Behaviour is in `*_events.tsv` (trial conditions, responses, response
  times), in `*_beh.tsv`, or in `participants.tsv` (scores, ages); some
  datasets have none (a movie-watching fMRI study, a resting-state EEG one
  with only trigger codes), and their README may then describe the design in
  prose. Processed data, when any, are under `derivatives/<pipeline>/`, not
  always in BIDS. The BIDS validator's warnings are common and usually
  harmless; its errors (a missing coordinate system, a wrongly typed TSV
  value) are worth checking against the files read.
- **In an entry.** The entry names the dataset as `openneuro:<id>/<tag>`
  under `related`, and gives in the notebook header the `id` of each file read.

## SPARC

- **Datasets.** A dataset on the SPARC Portal (`sparc.science`), the data
  portal of the NIH SPARC program on the peripheral nervous system and the
  organs it controls. SPARC publishes through Pennsieve Discover, and a
  dataset is named by its Pennsieve Discover id:
  `https://sparc.science/datasets/206` is `SPARC:206`, in folders
  `sparc-206`. Many SPARC datasets are computational models, scaffolds or
  tools, not experiments. So the registry's list, `targets/sparc.json`, is
  built from chosen ids by `tools/build_sparc_targets.py`. For now it holds
  three experimental datasets whose paper is in PubMed Central, to test the
  pipeline on SPARC. The builder reads each dataset's metadata, versions and
  file list from Pennsieve Discover's public API
  (`https://api.pennsieve.io/discover/datasets/<id>`). The papers are the
  dataset's related publications marked `IsDescribedBy` (and
  `IsReferencedBy`, `IsSupplementTo` or `IsDocumentedBy`). SPARC's own DOIs
  (`10.26275/`) and protocols (`10.17504/`, protocols.io) are left out.
  Otherwise give the paper's DOI to the builder (`<id>=<paper DOI>`).
- **Versions.** Each version has a number and its own DOI
  (`10.26275/xxxx-xxxx`). The DOI of a version does not change, and an older
  version stays readable. The number is `published_version` in the target
  list and pins it, with its DOI under `doi`. `version_dois` lists every
  version's DOI, since a paper may cite any of them. Record the number under
  `dataset: version` and the DOI under `dataset: doi`. List the versions
  with `https://api.pennsieve.io/discover/datasets/<id>/versions`.
- **Reading.** Everything is public, with no account. Every SPARC dataset is
  in the AWS Open Data bucket `sparc-prod-aod-discover-publish50-use1`
  (us-east-1, `bucket` in the target list), under `<id>/`. The bucket keeps
  every version of every file as an S3 object version. Each version of a
  dataset has a `manifest.json`, which lists every file with its `path`,
  `size`, `s3VersionId` and `sha256`. The target list gives the object
  version of the pinned version's manifest as `manifest_version`, so the
  manifest is at
  `https://<bucket>.s3.amazonaws.com/<id>/manifest.json?versionId=<manifest_version>`.
  Each file is at
  `https://<bucket>.s3.amazonaws.com/<id>/<path>?versionId=<s3VersionId>`.
  Open files with `fsspec.open(url, block_size=2**20)`, which reads ranges,
  and read only what a claim needs. A key without `versionId` holds the
  latest version, which may not be the pinned one. Pennsieve's API also lists
  one folder at a time, with the same object versions:
  `/discover/datasets/<id>/versions/<n>/files/browse?path=<folder>`. Its
  download endpoints need an account, and are not needed.
- **Checksums.** The manifest gives each file's SHA-256 in base64. The
  target list gives it in hex. Give in the notebook header the SHA-256 of
  each file read.
- **SPARC Data Structure.** Every dataset follows the SPARC Data Structure
  (SDS). Start from `readme.md` (the dataset's description), and
  `files/README.txt` when there is one. Then read the sheets at the top of
  `files/`: `dataset_description.xlsx` (the study, its contributors, its
  protocols and its originating article), `subjects.xlsx` (one row for each
  subject, with species, sex, age and experimental group) and
  `samples.xlsx`. The data are under `files/primary/` (as recorded),
  `files/derivative/` (processed), `files/source/`, `files/code/`,
  `files/docs/` and `files/protocol/`, each with a `manifest.xlsx` that
  describes its files. The sheets' layout differs between versions of SDS:
  read every column. `metadata/records/` holds the same subjects and
  samples as CSV, from Pennsieve's records. The formats vary: MATLAB, HDF5,
  CSV and Excel; acquisition formats (LabChart, Spike2, Intan); and
  microscopy, as TIFF, JPEG 2000 (`.jp2`, `.jpx`) and Zeiss files (`.czi`,
  read with `czifile` or `aicspylibczi`; `.lsm`, a TIFF that `tifffile`
  reads). Read an image's metadata (its scale, channels and planes) before
  its pixels, and only the planes a claim needs.
- **In an entry.** The entry names the dataset as `sparc:<id>/<version>`
  under `related`, and gives in the notebook header the SHA-256 of each file
  read.

## OSF

- **Datasets.** A public project, component or registration on OSF
  (`osf.io`), the Open Science Framework of the Center for Open Science, named
  by its GUID: `https://osf.io/qpc2d/` is `OSF:qpc2d`, in folders `osf-qpc2d`.
  GUIDs are five characters and ignore case. A project's DOI, when its owners
  have had one minted, is `10.17605/OSF.IO/<GUID>`; a registration always has
  one. Most public OSF projects hold study materials, preregistrations or
  course pages rather than data, so the registry's list, `targets/osf.json`,
  is built from chosen GUIDs by `tools/build_osf_targets.py`, which reads each
  project's metadata, files and papers from OSF's public API v2. A project
  rarely names its paper in its metadata. The builder takes the papers from a
  registration's article DOI and from the preprints (PsyArXiv and the other
  OSF preprint servers) that name the project as their supplemental
  materials, with the journal article each preprint was published as;
  otherwise give the paper's DOI to the builder (`<GUID>=<paper DOI>`). A
  preprint's GUID may also be given: the builder takes the project it links.
- **Components.** A project can hold components, each a node with its own
  GUID, files, contributors and sometimes its own DOI, nested to any depth. A
  dataset is often spread across them (one component per experiment, or one
  for data and one for code). The builder lists the files of every public
  component below the project with the component's GUID first in the path
  (`xyz23/licks.csv`), and the components themselves, with their titles,
  under `components`. A component can also be a target of its own.
- **Versions.** A project is not versioned as a whole. Each file in OSF
  Storage keeps its own numbered versions, with an MD5 and a SHA-256 for each,
  and an older version stays downloadable. So the target list pins a dataset
  file by file: each file's `version` and hashes, as the builder read them.
  `published_version` is the time the project was last modified when the list
  was built (`date_modified`), which changes with any edit, files or not, so
  it dates the list rather than pinning anything. A registration is a frozen
  copy of a project, its files and components, and its `published_version` is
  the time it was registered. Record `published_version` under
  `dataset: version` and the DOI, if any, under `dataset: doi`, and give in
  the notebook header the version and SHA-256 of each file read.
- **Reading.** Everything in a public project is readable with no account.
  The API is JSON:API: an item's related listings are at
  `relationships.<name>.links.related.href`, and a listing is paged, with the
  next page at `links.next` (`page[size]=100` is the largest page). List a
  project's storage providers at `https://api.osf.io/v2/nodes/<GUID>/files/`
  (`registrations/` for a registration); each provider's top folder, and each
  folder in it, lists its items at its `relationships.files` address. A
  file's attributes give its `materialized_path`, `size`, `current_version`
  and `extra.hashes` (`md5`, `sha256`), and its `links.download` is an
  address on `osf.io` (`https://osf.io/download/<id>/`). That address
  redirects to WaterButler on `files.osf.io` (or a regional host such as
  `files.de-1.osf.io`), which redirects in turn to OSF's object storage on
  Oracle Cloud (`*.compat.objectstorage.<region>.oraclecloud.com`), where
  range requests work. Add `?version=<n>` to the download address to read a
  given version; a version that does not exist gives 400 Bad Request. The
  sizes of every version are at `https://api.osf.io/v2/files/<id>/versions/`,
  and their hashes at the WaterButler address with `?revisions` added. Open
  the file with `fsspec.filesystem("http").open(url, block_size=2**20,
  size=<size>)` and read it into memory; do not download whole files to
  disk. Give the size: WaterButler answers a HEAD request with the size of
  the file's first version, whatever version is asked for, and fsspec, left
  to find the size that way, stops reading a later version that is larger at
  the first version's size, with no error. Check the SHA-256 of what you read
  against the target list. `pandas.read_csv(url)` reads the whole file with
  one request and is not affected. The project's wiki
  (`/nodes/<GUID>/wikis/`) and a README among its files, when there is one,
  describe the data; the description in the target list is the project's
  own.
- **Registrations.** A registration's files are copies with ids of their
  own, each at version 1, so their download addresses never change. In
  recent registrations the files of OSF Storage sit under a folder named
  `Archive of OSF Storage/`, which the target list keeps in their paths; in
  older ones they sit at the top. A registration's contributors are those of
  the project when it was registered.
- **Storage add-ons.** Besides OSF Storage (`osfstorage`), a project can link
  folders from GitHub, Google Drive, Dropbox, Box, Figshare, Amazon S3 and
  others. Their files are listed and read through the same API, named in the
  target list with the provider first (`github/analysis.py`), but OSF does not
  version them: what an add-on folder holds can change with no new version,
  and its files may have no size or hashes. The API still gives such a file a
  `current_version` of 1, but its download address answers `?version=1` with
  404 Not Found, so the target list gives it no version; read it at its
  download address as it is. The builder warns when a project has such
  files. A GitHub, GitLab or Bitbucket add-on is listed under `code`.
- **In an entry.** The entry names the dataset as
  `osf:<GUID>/<published_version>` under `related`, and gives in the notebook
  header the version and SHA-256 of each file read.

## Zenodo

- **Datasets.** A record on Zenodo (`zenodo.org`), CERN's general-purpose
  repository, named by its record id: `https://zenodo.org/records/3924718`,
  DOI `10.5281/zenodo.3924718`, is `ZENODO:3924718`, in folders
  `zenodo-3924718`. Zenodo holds every GitHub release archived through its
  integration, posters and slides as well as data, so the registry's list,
  `targets/zenodo.json`, is built from chosen record ids by
  `tools/build_zenodo_targets.py`, which reads each record's metadata, files
  and versions from Zenodo's public REST API and keeps records whose
  `resource_type` is a dataset. The papers are the record's related
  identifiers marked `isSupplementTo`, `isDescribedBy` or `isCitedBy` that
  are journal articles or preprints; otherwise give the paper's DOI to the
  builder (`<record id>=<paper DOI>`), from the paper's data statement.
  Related identifiers marked `isSupplementTo` a GitHub repository are listed
  under `code`.
- **Versions.** Each version of a deposit is a record of its own, with its
  own id and DOI, and a deposit's concept record (`conceptrecid`, with its
  concept DOI) resolves to the latest version. A record id therefore pins a
  version, and `published_version` is the record id. The target list also
  gives the deposit's `concept_id` and the ids of its other versions
  (`version_ids`), because a paper may cite the concept DOI or a version other
  than the one pinned; pin the record the paper cites, or the latest when it
  cites the concept DOI. A record's files cannot change once it is published:
  a change to the files is a new version. Record the record id under
  `dataset: version` and its DOI under `dataset: doi`, and give in the
  notebook header the MD5 of each file read, which the record gives
  (`checksum: md5:<hex>`).
- **Reading.** An open record needs no account. Its metadata, versions and
  files are at `https://zenodo.org/api/records/<id>` (under `files`, each with
  `key`, `size` and `checksum`), and each file at
  `https://zenodo.org/api/records/<id>/files/<key>/content`. Open it with
  `fsspec.open(url, block_size=2**20)`, opening a zip in place with
  `zipfile`, or with `pandas`, and read it into memory; do not download whole
  files to disk. A record whose files are restricted or embargoed
  (`access_right` other than `open`) is not a target. The record's
  description, in the target list, and a README among its files, when there
  is one, describe the data.
- **In an entry.** The entry names the dataset as `zenodo:<id>/<id>` under
  `related`, and gives in the notebook header the MD5 of each file read.

## Local and remote (`encore check`)

Two kinds of dataset exist only inside a run of `encore check`
([encore.md](encore.md)), and never in the registry's record: `local`, a
directory on the machine running it, and `remote`, files at a URL. The run
writes `targets/local.json` into its own copy of the registry, with the path or
URL and a fingerprint of the files, which stands in for a version. How agents
read them is in [protocol.md](protocol.md), "Local and remote datasets".

## Adding an archive

Each archive is an adapter: one module in `tools/archives/`, which defines
`ARCHIVE = Archive(...)` (see `tools/archives/__init__.py`, and
`tools/archives/crcns.py` for the simplest). Nothing else lists the archives:
the site, the Pipeline page, the paper store, the runner and `encore check`
take them from there.

1. Write the module. Give the archive's key (the first part of a dataset's key
   and folder name), its label and name, the address of a dataset's page, the
   target list's file name, the sentence agents get about reading a dataset
   (with a target's fields as `{field}`), the hosts an agent's commands must
   reach, and whether its identifiers ignore case.
2. If agents cannot read its files directly (the archive needs credentials, as
   Dryad does), give the module a `stage(target, root)` that downloads the
   pinned version's files to `root/<archive>/<id>/<version>/` and checks them,
   and list the environment variables it needs in `secrets`. Add those secrets
   to the staging steps of `attempt.yml` and `check.yml`, and to the
   repository's secrets. The access sentence then points agents to the staged
   directory.
3. Write its target list in `targets/`, by hand or with a builder named in the
   module (`builder`). Each target needs an `id`, a `name` and its `papers`
   (DOI, title, whether a preprint), as in `targets/dandisets.json`, and
   whatever field pins a version (`published_version`).
4. Add a section here, as for DANDI: what a dataset and a version are, how to
   pin one, and how to read files without downloading them.
5. Give attempts on it the archive's name in their `dataset` block (`archive`,
   `id`, `version`, and `doi` or `modified`), and give entries a relation
   `<archive>:<id>/<version>`.
