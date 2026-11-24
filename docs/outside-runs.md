# Runs from encore-runner

The runs that begin an attempt, the reader's claims and the author's first run, can be made from [encorescience/encore-runner](https://github.com/encorescience/encore-runner) or from a fork of it. CatalystNeuro makes its own from encore-runner. Another organization forks it and runs Encore with its own Anthropic API key, its own compute and its own copy of the papers. Either way the results go to one place, the registry, [encorescience/encore-registry](https://github.com/encorescience/encore-registry), on the attempt's branch, and from there the attempt goes on as any other: the registry's verifiers check it, and a person merges it. On [encorescience.org](https://encorescience.org) the attempt names the organization that ran it.

This page says how a run from encore-runner reaches the registry, what the registry checks before it takes one, and how an organization sets up its fork.

## How It Works

encore-runner holds no protocol of its own. Its workflows call this repository's `papers.yml` and `attempt.yml` with the input `registry: encorescience/encore-registry`. In that mode a run reads the registry, starting from the attempt's branch there when there is one, and writes nothing to it. Its last job, `submit`, gathers what the run changed into one file, `submission.tar.gz` (`tools/submission.py`), and signs it with GitHub's artifact attestations. The signature names the workflow that made the file (this repository's `papers.yml` or `attempt.yml`, at the commit the caller named), the repository and run it was made in, and the file's digest. A workflow in encore-runner or a fork cannot sign as this repository's, so a submission whose signature checks was made by the protocol's own workflow and has not been changed since.

The registry takes a submission with its intake workflow, given the run's address. The intake checks the signature, checks that the submission changes only what its role may change, and checks that the run started from the attempt branch's current commit. It then commits the submission to the attempt's branch, `attempt/<paper>`, and names the repository and run in the commit (`Encore-Source`, `Encore-Run`). The next run starts from that commit.

A paper's attempt begins with three runs, each taken by the intake before the next starts:

1. **claims**: the reader writes the paper's claims file (`papers.yml`).
2. **claims-check**: a second reader checks it, until its last check says the file is ready.
3. **author**: the author's first run on those claims (`attempt.yml`).

Each run starts from the commit the intake made for the one before, and the intake refuses a run that started anywhere else. The author's run is therefore signed as having started from the checked claims, which is the protocol's checkpoint (`docs/pipeline.md`): the claims are fixed before anyone tests them on the data. A paper whose claims are already on the registry's main can start with the author.

After the author's run, the registry takes over. The verification rounds, the author's revisions after them, the reconcile run and the recorder run in the registry on the same branch, on CatalystNeuro's accounts, as for any attempt. The site shows the attempt as not yet verified until they agree with it.

## What the Intake Checks

The intake (`tools/intake.py` in the registry) never runs anything from a submission; it reads the files and checks them:

- The signature is GitHub's, for this repository's `papers.yml` or `attempt.yml`, made in the run the intake was given and in that run's repository.
- The submission names the registry and the run it came from, and its files are one paper's: its claims file, attempt records, entry, questions and transcripts. It removes nothing but transcripts, which a new attempt moves aside.
- A claims or claims-check run changes only the claims file, the questions file and the reader's transcripts. An author run leaves the claims file as it was, adds one new attempt record and changes no earlier one, and brings no verification rounds or later runs. Its record names who is accountable for it and the run it was made in.
- The run started from the attempt branch's current commit, or, for a new attempt, from a commit on main. A repository continues only an attempt its own runs began, so two organizations never write to the same attempt.

The registry's usual check (`check.yml`) runs on the attempt when it comes to be merged, as on any pull request.

The signature establishes which workflow made a submission, where, and from which commit. It cannot establish that the transcripts are a faithful record of the run, any more than a record from CatalystNeuro's own runs could be checked that way from the outside. That is what the verification rounds are for: the registry executes the entry's notebooks again from a clean environment, and its verifiers check the analysis and each outcome against the paper and the claims file.

## Who Can Do What

Submissions from encore-runner itself go on the attempt's branch as soon as they pass. Submissions from a fork pass the same checks and then wait until a person at CatalystNeuro approves them, so that the registry's verifiers spend nothing on a run nobody has looked at. The registry's variable `ENCORE_INTAKE_AUTO` lists the repositories whose submissions go straight on; adding a fork to it, or setting it to `*`, lets that fork's runs, or every fork's, go straight on too.

An organization's runs and its API key stay in its own account; CatalystNeuro never holds its key. The organization cannot write to the registry: its runs read it, and the intake writes what they made. CatalystNeuro's runs after the author use CatalystNeuro's accounts and paper store.

## Setting Up a Fork

Fork encorescience/encore-runner into the organization's GitHub account and enable Actions on the fork. The fork is public, as a fork of a public repository is, which GitHub's signatures need on its Free and Team plans; it holds no papers and no keys.

The fork needs one secret, one environment and two variables:

- A repository secret `ANTHROPIC_API_KEY`, the organization's own key. Runs are billed to it.
- An environment named `papers`, with a secret `PAPERS_DEPLOY_KEY`: the private half of a read-only deploy key on the organization's own paper store. The runs read the papers in that environment and never commit them.
- A variable `ENCORE_PAPERS_REPO`, the paper store, as `owner/name`. It is a private repository laid out as CatalystNeuro's is: one folder per dataset, named as the registry's `papers/datasets/` files name the dataset's folder, holding the paper's full text and PDF named by its DOI in lower case with `/` as `-` (for example `10.1016-j.neuron.2020.01.001.txt`), and optionally the dataset's own description as `<id>.data-description.txt`. Large files can be in Git LFS. Papers are copyrighted, which is why each organization keeps its own store.
- A variable `ENCORE_ACCOUNTABLE`, the name the attempt records as accountable for it (for example "Acme Lab, University of Somewhere"). Without it the record names the fork's owner.

encore-runner's README says how to run a paper and send each run to the registry. A paper the registry does not list yet (in `papers/keys.yaml` and `papers/datasets/`) has to be added there first; ask for it with `encore request` or an issue on the registry.
