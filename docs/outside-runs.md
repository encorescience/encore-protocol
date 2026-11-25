# Attempts from encore-runner

An attempt can be made from [encorescience/encore-runner](https://github.com/encorescience/encore-runner) or from a fork of it. CatalystNeuro makes its own from encore-runner. Another organization forks it and runs Encore with its own Claude account, its own compute and its own copy of the papers. Either way the attempt ends up in one place, the registry, [encorescience/encore-registry](https://github.com/encorescience/encore-registry), on the attempt's branch, where the registry's check runs on it and a person merges it. On [encorescience.org](https://encorescience.org) the attempt names the organization that ran it.

A runner makes the whole attempt in its own repository, from the reader's claims to the recorder's notes. It touches the registry twice: it says when the attempt starts, and it sends the attempt when it is finished.

This page says how an attempt made in a runner reaches the registry, what the registry checks before it takes one, and how an organization sets up its fork.

## How It Works

encore-runner holds no protocol of its own. Its workflows call this repository's `sequence.yml`, which runs a whole attempt, or `papers.yml` and `attempt.yml`, which run one role, with the input `registry: encorescience/encore-registry`. In that mode a run reads the registry and writes nothing to it.

**The state.** Between runs, the attempt's state is on the runner's own branch, `attempt/<paper>`. The branch holds the paper's files, laid out as the registry lays them out (its claims file, attempt records, entry, questions, transcripts and the recorder's notes), and a ledger, `.encore/attempt.json`. The ledger names the registry, the commit of the registry's main the attempt began at, and the attempt's runs in order. A run starts from the registry at that commit with the branch's files laid over it, so every run of an attempt reads the same registry.

**The signature.** Each run's last job, `submit`, gathers what the run changed into one file, `submission.tar.gz` (`tools/submission.py`), and signs it with GitHub's artifact attestations. The signature names the workflow that made the file (this repository's `papers.yml` or `attempt.yml`, at the commit the caller named), the repository and run it was made in, and the file's digest. A workflow in encore-runner or a fork cannot sign as this repository's, so a submission whose signature checks was made by the protocol's own workflow and has not been changed since. The submission also carries the digest of the state the run started from. The job then adds the results to the runner's branch and the run to the ledger.

**The start.** When an attempt starts, the runner tells the registry. The registry's intake makes its own branch `attempt/<paper>`: one empty commit on main that names the runner (`Encore-Source`) and its run (`Encore-Start`). The registry then shows who is attempting the paper, CatalystNeuro's queue leaves the paper alone, and a run from any other runner refuses to start on it.

**The end.** When the last run has finished, the runner sends the attempt. The intake reads the ledger, checks every run as the next section says, and pushes the runs, one commit each, as the registry's `attempt/<paper>`, over the commit the start made. Each commit names the repository and run (`Encore-Source`, `Encore-Run`).

An attempt's runs, in order:

1. **claims**: the reader writes the paper's claims file (`papers.yml`).
2. **claims-check**: a second reader checks it, until its last check says the file is ready.
3. **author**: the author's attempt on those claims (`attempt.yml`).
4. **verifier-1, author-revise-1, verifier-2, author-revise-2**: two verification rounds, each followed by the author's revision.
5. **verifier-3, author-revise-3**: a third round, when the second revision proposed changes of outcome.
6. **reconcile**: for a paper with an earlier attempt, the comparison with it.
7. **recorder**: the notes on the finished attempt.

A paper whose claims are already on the registry's main can start with the author. `sequence.yml` does not yet run the reader's answers to questions the author raises (`answer`, `author-answers`); they can be run one at a time.

## What the Intake Checks

The intake (`tools/intake.py` in the registry) never runs anything from a submission; it reads the files and checks them. For each run in the ledger, in order:

- **The signature** is GitHub's, for this repository's `papers.yml` or `attempt.yml`, whichever makes that role, made in the run the ledger names and in the runner's repository.
- **The submission** names the registry, the run it came from and the commit of main the attempt began at, and its files are one paper's.
- **The chain.** The run started from the state the runs before it left: the digest it carries is the digest of the paper's files after the intake has laid the earlier submissions over the registry at the attempt's first commit. A run left out of the ledger, or a branch edited by hand between runs, breaks the chain, and the attempt is refused.
- **The role's changes.** A claims or claims-check run changes only the claims file, the questions file and the reader's transcripts. The author's first run starts from claims whose last check says they are ready, leaves the claims file as it was, adds one new attempt record and changes no earlier one; the record names who is accountable for it and the run it was made in. A verification round brings its transcripts and nothing else. A revision or the reconcile run changes the attempt's own record, entry and questions. The recorder writes the attempt's notes and summary.

Then, for the attempt as a whole: its last run succeeded, its record meets the schema and names who is accountable, and it has an entry. The registry's usual check (`check.yml`), which runs the entry's notebooks again from a clean environment, runs on the attempt's pull request, as on any.

The signatures establish which workflow made each submission, where, and from which state. They cannot establish that the transcripts are a faithful record of the runs, any more than a record from CatalystNeuro's own runs could be checked that way from the outside. They also cannot show a run that was made and left out before the next one started from the same state, such as a verification round repeated until it agreed. The intake lists, for whoever reviews the attempt, the runner's runs on the paper that the ledger does not name; a fork is public, so its runs can be read.

## Who Verifies

A runner makes its own verification rounds, with the same prompts and the same isolation as CatalystNeuro's: a verifier sees only its materials, and its job has no checkout of the repository. So an organization's attempt is verified by that organization's own runs. The attempt's record says who made it, and the site names that organization. The registry can run a verification round of its own on any attempt it has taken, when an independent check is wanted.

## Who Can Do What

An attempt from encore-runner itself is recorded and taken as soon as it passes: encore-runner starts the intake from its own runs, with a token only it holds. A fork's owner tells the registry with its "Outside attempt" issue form, giving the run's address and the paper; the run's summary has a link to the form with both filled in. A fork's notices pass the same checks and then wait until someone in the registry's `queue/priority.yaml` approves them with the `approved` label. The intake comments on the issue with what it found, and closes it once it is done. The registry's variable `ENCORE_INTAKE_AUTO` lists the repositories whose notices go straight on; adding a fork to it, or setting it to `*`, lets that fork's, or every fork's, go straight on too.

A fork's start notice does not hold its runs up: the attempt goes on while the notice waits, and an attempt that was never announced can still be sent at the end.

An organization's runs and its Claude account stay in its own GitHub account; CatalystNeuro never holds its key. The organization cannot write to the registry: its runs read it, and the intake writes what they made.

## Setting Up a Fork

Fork encorescience/encore-runner into the organization's GitHub account and enable Actions on the fork. The fork is public, as a fork of a public repository is, which GitHub's signatures need on its Free and Team plans; it holds no papers and no keys.

The fork needs two secrets, one environment and two variables:

- A repository secret with the organization's own account for Claude: either `ANTHROPIC_API_KEY`, an API key, whose runs are billed to it, or `CLAUDE_CODE_OAUTH_TOKEN`, a token for a Claude subscription made with `claude setup-token`, whose runs count against that subscription's limits. With both, the runs use the token.
- A repository secret `PAPERS_DEPLOY_KEY`: the private half of a read-only deploy key on the organization's own paper store. It has to be a repository secret, not an environment's: the protocol's workflows are in another organization, and GitHub passes neither `secrets: inherit` nor a caller's environment secrets to a reusable workflow outside the caller's own organization, so encore-runner passes each secret by name.
- An environment named `papers`, which the runs that read the papers run in. They never commit the papers.
- A variable `ENCORE_PAPERS_REPO`, the paper store, as `owner/name`. It is a private repository laid out as Encore's own store, `encorescience/registry-papers`, is: one folder per dataset, named as the registry's `papers/datasets/` files name the dataset's folder, holding the paper's full text and PDF named by its DOI in lower case with `/` as `-` (for example `10.1016-j.neuron.2020.01.001.txt`), and optionally the dataset's own description as `<id>.data-description.txt`. Large files can be in Git LFS. Papers are copyrighted, which is why each organization keeps its own store.
- A variable `ENCORE_ACCOUNTABLE`, the name the attempt records as accountable for it (for example "Acme Lab, University of Somewhere"). Without it the record names the fork's owner.

encore-runner's README says how to run a paper. A paper the registry does not list yet (in `papers/keys.yaml` and `papers/datasets/`) has to be added there first; ask for it with `encore request` or an issue on the registry.
