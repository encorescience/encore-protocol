# Outside Runs

An organization other than CatalystNeuro can run Encore's attempts itself, with its own Anthropic API key, its own compute and its own copy of the papers, and send the results to the registry, [encorescience/encore-registry](https://github.com/encorescience/encore-registry). Its attempts then sit in the same registry as CatalystNeuro's, on the same pages of [encorescience.org](https://encorescience.org), with the organization named as the one that ran them. CatalystNeuro's verifiers check each one after it arrives, as they check any attempt, and until they do the site shows it as not yet verified.

This page says how to set that up, how a submission goes, and what the registry checks before a person merges it.

## How It Works

The organization forks the registry on GitHub and runs the same workflows CatalystNeuro runs, in its fork. The fork is only a place to run and to send pull requests from: the records live in the central registry, and nothing the fork publishes or tracks (the site, the queue, the target lists) runs there, because those jobs check that they are in `encorescience/encore-registry`.

A paper goes in two pull requests, because the protocol fixes a paper's claims before anyone tests them on the data (the checkpoint in `docs/pipeline.md`):

1. **The claims.** The reader writes the paper's claims file and a second reader checks it (`papers.yml`, roles `claims` and `claims-check`). The organization sends the claims file and those two runs' transcripts to the registry. A person at CatalystNeuro merges it, which puts the claims on main.
2. **The attempt.** The organization updates its fork from the registry's main, runs the author on those claims (`attempt.yml`, role `author`), and sends the attempt: its record, its entry, the author's questions and its transcripts.

A paper whose claims are already on the registry's main skips the first step: the author starts from those claims, as CatalystNeuro's own repeat attempts do. A paper the registry does not list yet (in `papers/keys.yaml` and `papers/datasets/`) has to be added by CatalystNeuro first; ask for it with `encore request` or an issue on the registry.

The verification rounds, the author's revisions after them, the reconcile run and the recorder all run in the registry, on CatalystNeuro's accounts, after the attempt is merged. An outside pull request does not include them.

## Setting Up a Fork

Fork `encorescience/encore-registry` into the organization's GitHub account and enable Actions on the fork. GitHub disables scheduled workflows on a fork, which is what you want: the only workflows the fork needs are the ones you start by hand.

The fork needs one secret and one environment:

- A repository secret `ANTHROPIC_API_KEY`, the organization's own key. Runs are billed to it. The workflows use the key when the fork has no `CLAUDE_CODE_OAUTH_TOKEN`, which an outside fork does not.
- An environment named `papers`, with a secret `PAPERS_DEPLOY_KEY`: the private half of a read-only deploy key on the organization's own paper store. The runs read the papers in that environment and never commit them.

And two repository variables:

- `ENCORE_PAPERS_REPO`, the paper store, as `owner/name`. It is a private repository laid out as CatalystNeuro's is: one folder per dataset, named as the registry's `papers/datasets/` files name the dataset's folder, holding the paper's full text and PDF named by its DOI in lower case with `/` as `-` (for example `10.1016-j.neuron.2020.01.001.txt`), and optionally the dataset's own description as `<id>.data-description.txt`. Large files can be in Git LFS. Papers are copyrighted, which is why each organization keeps its own store.
- `ENCORE_ACCOUNTABLE`, the name the attempt records as the one accountable for it (for example "Acme Lab, University of Somewhere"). Without it the record names the fork's owner. It cannot be CatalystNeuro.

## Running a Paper

With `P` as the paper's key in the registry (its claims file is `claims/P.yaml`):

1. Run the claims: from the fork's Actions tab, the "Paper run" workflow with role `claims`, then with role `claims-check`, until the last check in `claims/P.yaml` says the file is ready. The runs commit to the branch `attempt/P` in the fork.
2. Open a pull request from that branch to `encorescience/encore-registry` with only the claims file and the two runs' transcripts. Wait for it to be merged.
3. Update the fork's main from the registry's ("Sync fork" on GitHub) and delete the fork's `attempt/P` branch, so that the author's run starts from the claims as merged.
4. Run the author: the "Agent run" workflow with role `author`. It commits to `attempt/P` again.
5. Open a pull request from `attempt/P` to the registry. The registry's check runs on it, and a person reviews and merges it.

The author has to start after the claims are on the registry's main; the check compares the time the author's run started with the time main took the claims file, and refuses an attempt that started earlier.

## What the Registry Checks

The registry's workflow `outside.yml` runs `tools/outside_check.py` on every pull request from a fork. It runs the registry's own copy of the check against the pull request's files, which it reads as data and never runs, so that a pull request cannot change the check it is held to. It passes a pull request that is one of the two submissions above and nothing more:

- Every file it changes belongs to one paper: `claims/P.yaml`, `attempts/P-NN.yaml`, `entries/P/`, `questions/P.yaml`, `questions/P/` and `transcripts/P/`. It removes nothing outside the transcripts.
- A claims pull request brings the claims file and the reader's transcripts, for a paper whose claims main does not have yet, and the file's last check says it is ready.
- An attempt pull request leaves the claims file as main has it, adds exactly one new attempt record and changes no earlier one, and includes no verification rounds, revisions, reconcile run or recorder, in the record or as transcripts.
- The attempt's record names who is accountable, and not CatalystNeuro, and its `provenance.runner.url` is a run of the attempt workflow in the fork the pull request comes from, which started after main took the claims.

Both kinds also have to meet the protocol's schemas, and the registry's usual check (`check.yml`) runs on them as on any pull request: the entry's metadata and conventions, and its notebooks executed from a clean environment.

The check establishes where an attempt was run and that it was run from fixed claims. It cannot establish that the transcripts are a faithful record of the run, any more than a record from CatalystNeuro's own runner could be checked that way from the outside. That is what happens after the merge: the registry executes the entry's notebooks again from a clean environment, and CatalystNeuro's verifiers check the analysis and each outcome against the paper and the claims file. Only their agreement moves the attempt out of "not yet verified".

## Who Can Do What

The organization's runs and its API key stay in its own account; CatalystNeuro never holds its key. The organization cannot write to the registry: its records arrive by pull request, and a person at CatalystNeuro merges them. CatalystNeuro's runs after the merge use CatalystNeuro's accounts and paper store.
