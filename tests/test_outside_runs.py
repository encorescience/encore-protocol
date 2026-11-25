"""Runs from encore-runner and its forks, with their own API key and paper store, whose results the registry takes
through its intake (docs/outside-runs.md)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = Path(os.environ.get("PROTOCOL_ROOT") or REPO) / ".github" / "workflows"
sys.path.insert(0, str(REPO / "tools"))

import agent_run  # noqa: E402

ROLE_WORKFLOWS = ("attempt.yml", "papers.yml")


def load(name: str) -> dict:
    # PyYAML reads the key `on` as True.
    workflow = yaml.safe_load((WORKFLOWS / name).read_text())
    return workflow.get("on") or workflow[True]


def agent_job(name: str) -> list[dict]:
    workflow = yaml.safe_load((WORKFLOWS / name).read_text())
    return workflow["jobs"]["run"]["steps"]


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_a_caller_with_only_an_api_key_is_accepted(name):
    secrets = load(name)["workflow_call"]["secrets"]
    assert secrets["CLAUDE_CODE_OAUTH_TOKEN"]["required"] is False
    assert secrets["ANTHROPIC_API_KEY"]["required"] is False
    inputs = load(name)["workflow_call"]["inputs"]
    assert inputs["papers_repo"]["default"] == "" and inputs["accountable"]["default"] == ""


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_the_account_is_chosen_before_any_credential_is_used(name):
    steps = agent_job(name)
    names = [s.get("name") for s in steps]
    choose = names.index("Choose the account")
    assert choose < names.index("Check that the unverified account has a token") < names.index("Run the agent")
    for step in steps:
        for key, value in (step.get("env") or {}).items():
            if key in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
                assert "inputs.account" not in value and "steps.acct.outputs.account" in value, (step["name"], key)
            if key == "ANTHROPIC_API_KEY":
                assert "secrets.ANTHROPIC_API_KEY_CREDITS || secrets.ANTHROPIC_API_KEY" in value


@pytest.mark.parametrize("has_token,has_key,asked,used", [
    ("true", "true", "verified", "verified"),      # CatalystNeuro: unchanged
    ("true", "true", "unverified", "unverified"),
    ("false", "true", "verified", "api"),          # an outside organization with its key
    ("false", "false", "verified", "verified"),    # nothing: the check after it says so
    ("true", "false", "api", "api"),
])
@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_choosing_the_account(name, has_token, has_key, asked, used, tmp_path):
    step = next(s for s in agent_job(name) if s.get("name") == "Choose the account")
    out, env = tmp_path / "out", tmp_path / "env"
    for f in (out, env, tmp_path / "summary"):
        f.write_text("")
    subprocess.run(["bash", "-euo", "pipefail", "-c", step["run"]], check=True, env={
        **os.environ, "HAS_TOKEN": has_token, "HAS_KEY": has_key, "ACCOUNT": asked,
        "GITHUB_OUTPUT": str(out), "GITHUB_ENV": str(env), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")})
    assert out.read_text() == f"account={used}\n" and env.read_text() == f"ACCOUNT={used}\n"


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_the_commit_records_the_account_the_run_used(name):
    workflow = yaml.safe_load((WORKFLOWS / name).read_text())
    assert workflow["jobs"]["run"]["outputs"]["account"] == "${{ steps.acct.outputs.account }}"
    assert workflow["jobs"]["commit"]["env"]["ACCOUNT"].startswith("${{ needs.run.outputs.account")


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_the_paper_store_and_the_accountable_name_come_from_the_caller(name):
    steps = agent_job(name)
    papers = next(s for s in steps if s.get("name") == "Put the papers under paper/")
    assert papers["env"]["ENCORE_PAPERS_REPO"] == "${{ inputs.papers_repo }}"
    prompt = next(s for s in steps if s.get("name") == "Write the prompt")
    assert prompt["env"]["ENCORE_ACCOUNTABLE"] == "${{ inputs.accountable }}"


def fake_git(tmp_path: Path) -> dict:
    """A PATH whose git records its arguments and fails, so that get_papers.sh stops at the clone."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "git").write_text(f'#!/bin/bash\necho "$*" >> {tmp_path}/git.log\nexit 1\n')
    (bin_ / "git").chmod(0o755)
    return {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "PAPERS_DEPLOY_KEY": "not a key"}


@pytest.mark.parametrize("repo,url", [(None, "git@github.com:catalystneuro/registry-papers.git"),
                                      ("acme-lab/encore-papers", "git@github.com:acme-lab/encore-papers.git")])
def test_get_papers_clones_the_store_the_caller_names(tmp_path, repo, url):
    env = fake_git(tmp_path)
    env.pop("ENCORE_PAPERS_REPO", None)
    if repo:
        env["ENCORE_PAPERS_REPO"] = repo
    run = subprocess.run(["bash", str(REPO / "tools" / "get_papers.sh"), "000147", str(tmp_path / "paper")],
                         env=env, capture_output=True, text=True)
    assert run.returncode != 0
    assert url in (tmp_path / "git.log").read_text()


@pytest.mark.parametrize("repo", ["acme lab/papers", "acme/papers;rm -rf /", "../papers", "acme"])
def test_get_papers_refuses_a_store_that_is_not_a_repository(tmp_path, repo):
    env = {**fake_git(tmp_path), "ENCORE_PAPERS_REPO": repo}
    run = subprocess.run(["bash", str(REPO / "tools" / "get_papers.sh"), "000147", str(tmp_path / "paper")],
                         env=env, capture_output=True, text=True)
    assert run.returncode != 0 and "Not a repository" in run.stdout
    assert not (tmp_path / "git.log").exists()


@pytest.mark.parametrize("env,expected", [
    ({}, "CatalystNeuro"),
    ({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "encorescience/encore-registry"}, "CatalystNeuro"),
    ({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "acme-lab/encore-registry"}, "acme-lab"),
    ({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "acme-lab/encore-registry",
      "ENCORE_ACCOUNTABLE": "  Acme  Lab, University of Somewhere "}, "Acme Lab, University of Somewhere"),
    ({"ENCORE_ACCOUNTABLE": "Acme Lab"}, "Acme Lab"),
])
def test_the_accountable_name(monkeypatch, env, expected):
    for k in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY", "ENCORE_ACCOUNTABLE"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert agent_run.accountable() == expected


def test_an_accountable_name_that_would_break_the_prompt_is_refused(monkeypatch):
    monkeypatch.setenv("ENCORE_ACCOUNTABLE", 'Acme "Lab"')
    with pytest.raises(SystemExit, match="ENCORE_ACCOUNTABLE"):
        agent_run.accountable()


def test_the_author_is_told_who_is_accountable(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme-lab/encore-registry")
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    monkeypatch.delenv("ENCORE_ACCOUNTABLE", raising=False)
    text = agent_run.fill("author", "000147", "m")
    assert 'accountable name "acme-lab"' in text and "CatalystNeuro" not in text.split("Provenance:", 1)[1].split("\n")[0]
    assert "https://github.com/acme-lab/encore-registry/actions/runs/1" in text


# Runs from encore-runner and its forks: they read the registry, push nothing, and sign what they made.

def jobs(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())["jobs"]


def step(job: dict, name: str) -> dict:
    return next(s for s in job["steps"] if s.get("name", "").startswith(name))


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_a_run_from_encore_runner_reads_the_registry_it_names(name):
    assert load(name)["workflow_call"]["inputs"]["registry"]["default"] == ""
    checkout = jobs(name)["run"]["steps"][0]
    assert checkout["with"]["repository"] == "${{ inputs.registry || github.repository }}"
    assert checkout["with"]["persist-credentials"] is False
    lay = step(jobs(name)["run"], "Lay the protocol over the registry")["run"]
    assert 'main=$(git rev-parse HEAD)' in lay and '"$main:protocol.lock"' in lay and "GITHUB_SHA" not in lay


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_a_run_from_encore_runner_signs_a_submission_and_pushes_to_its_own_branch_only(name):
    j = jobs(name)
    assert "inputs.registry == ''" in j["commit"]["if"]
    submit = j["submit"]
    assert "inputs.registry != ''" in submit["if"]
    assert submit["permissions"] == {"contents": "write", "id-token": "write", "attestations": "write"}
    sign = next(s for s in submit["steps"] if s.get("uses", "").startswith("actions/attest-build-provenance"))
    assert sign["with"]["subject-path"] == "submission/submission.tar.gz"
    upload = [s for s in submit["steps"] if s.get("uses", "").startswith("actions/upload-artifact")]
    assert upload[-1]["with"]["name"] == "submission-${{ needs.run.outputs.folder }}-${{ inputs.role }}"
    # The registry is checked out at the commit the attempt began at, without credentials, and submission.py comes
    # from this workflow.
    assert submit["steps"][0]["with"]["repository"] == "${{ inputs.registry }}"
    assert submit["steps"][0]["with"]["ref"] == "${{ needs.run.outputs.base_sha }}"
    assert submit["steps"][0]["with"]["persist-credentials"] is False
    assert step(submit, "Lay the protocol's tools")["env"]["WORKFLOW_SHA"] == "${{ job.workflow_sha }}"
    gather = step(submit, "Gather the run's changes")["run"]
    assert "--meta base_sha=" in gather and "--meta run_url=" in gather and "--meta state_before=" in gather
    # The run job tells the submit job which state it started from, and a branch that moved meanwhile stops it.
    assert submit["env"]["STARTED_FROM"] == "${{ needs.run.outputs.state }}" and '"$before" = "$STARTED_FROM"' in gather
    # One push, in the last step, to the caller's own repository: never to the registry.
    pushes = [s for s in submit["steps"] if "git push" in s.get("run", "")]
    assert [s["name"] for s in pushes] == ["Add the results to the attempt's state, on this repository's branch"]
    assert "github.com/${GITHUB_REPOSITORY}.git" in pushes[0]["run"] and "REGISTRY" not in pushes[0]["run"].split("git push")[1]
    assert "git push" not in yaml.safe_dump(j["run"])


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    """A registry with a main, and the branch a start notice made for acme/encore-runner's attempt on demo-2020."""
    src = tmp_path / "src"
    src.mkdir()
    git(src, "init", "-q", "-b", "main")
    (src / "README.md").write_text("registry\n")
    (src / "tools").mkdir()
    (src / "tools" / "outside_check.py").write_text("# the registry's own tools\n")
    (src / "claims").mkdir()
    (src / "claims" / "main-2019.yaml").write_text("paper: main-2019\n")   # claims already on main
    git(src, "add", "-A")
    git(src, "commit", "-qm", "main")
    git(src, "checkout", "-qb", "attempt/demo-2020")
    git(src, "commit", "-q", "--allow-empty", "-m", "Attempt on demo-2020 begun by acme/encore-runner",
        "-m", "Encore-Source: acme/encore-runner\nEncore-Start: https://github.com/acme/encore-runner/actions/runs/1")
    git(src, "checkout", "-q", "main")
    bare = tmp_path / "registry.git"
    git(tmp_path, "clone", "-q", "--bare", str(src), str(bare))
    return bare


@pytest.fixture
def runner(tmp_path: Path, registry: Path) -> Path:
    """acme/encore-runner: its branch attempt/demo-2020 holds the state its claims run left, and the ledger."""
    src = tmp_path / "runner-src"
    src.mkdir()
    git(src, "init", "-q", "-b", "attempt/demo-2020")
    for path, text in {"claims/demo-2020.yaml": "paper: demo-2020\n", "transcripts/demo-2020/claims.md": "read\n",
                       ".encore/attempt.json": json.dumps({
                           "format": 1, "paper": "demo-2020", "registry": "encorescience/encore-registry",
                           "base_sha": git(registry, "rev-parse", "main").strip(), "runs": []})}.items():
        (src / path).parent.mkdir(parents=True, exist_ok=True)
        (src / path).write_text(text)
    git(src, "add", "-A")
    git(src, "commit", "-qm", "Agent run on demo-2020: claims (success)")
    bare = tmp_path / "runner.git"
    git(tmp_path, "clone", "-q", "--bare", str(src), str(bare))
    return bare


def run_start(name: str, tmp_path: Path, registry: Path, runner: Path | None = None, **env) -> subprocess.CompletedProcess:
    """The run job's start step, as a shell script, in a checkout of the registry's main."""
    script = step(jobs(name)["run"], "Start from the attempt's branch")["run"]
    work, temp = tmp_path / "work", tmp_path / "temp"
    git(tmp_path, "clone", "-q", str(registry), str(work))
    temp.mkdir()
    # The step takes submission.py from the workflow's own commit of this repository, checked out under .protocol.
    (work / ".protocol" / "tools").mkdir(parents=True)
    git(work / ".protocol", "init", "-q")
    (work / ".protocol" / "tools" / "submission.py").write_text((WORKFLOWS.parents[1] / "tools" / "submission.py").read_text())
    git(work / ".protocol", "add", "-A")
    git(work / ".protocol", "commit", "-qm", "the protocol, as it is here")
    full = {**os.environ, "GITHUB_OUTPUT": str(tmp_path / "out"), "GITHUB_ENV": str(tmp_path / "env"),
            "PAPER": "demo-2020", "REPLICATE": "", "DATASET": "", "GITHUB_REPOSITORY": "acme/encore-runner",
            "MAIN_SHA": git(work, "rev-parse", "HEAD").strip(), "RUNNER_TEMP": str(temp), "GH_TOKEN": "",
            "WORKFLOW_SHA": git(work / ".protocol", "rev-parse", "HEAD").strip(),
            "RUNNER_REMOTE": str(runner or tmp_path / "no-such-runner.git"), **env}
    if runner is None:
        git(tmp_path, "init", "-q", "--bare", str(tmp_path / "no-such-runner.git"))
    return subprocess.run(["bash", "-e", "-c", script], cwd=work, env=full, capture_output=True, text=True)


@pytest.mark.parametrize("name,role,repo,paper,ok", [
    ("papers.yml", "claims", "acme/encore-runner", "new-2021", True),         # a new attempt starts from main
    ("papers.yml", "claims-check", "acme/encore-runner", "demo-2020", True),  # goes on from its own state
    ("papers.yml", "answer", "acme/encore-runner", "demo-2020", True),
    ("papers.yml", "claims-check", "other/encore-runner", "demo-2020", False),  # the registry names another runner
    ("papers.yml", "claims", "other/encore-runner", "demo-2020", False),
    ("papers.yml", "claims-check", "acme/encore-runner", "new-2021", False),  # no claims run yet
    ("papers.yml", "paper-match", "acme/encore-runner", "demo-2020", False),  # writes to the registry's main
    ("attempt.yml", "author", "acme/encore-runner", "demo-2020", True),
    ("attempt.yml", "verifier-1", "acme/encore-runner", "demo-2020", True),   # every role of an attempt
    ("attempt.yml", "recorder", "acme/encore-runner", "demo-2020", True),
    ("attempt.yml", "author", "acme/encore-runner", "main-2019", True),       # from the claims main has
    ("attempt.yml", "author", "other/encore-runner", "demo-2020", False),
    ("attempt.yml", "author", "acme/encore-runner", "new-2021", False),       # no claims anywhere
    ("attempt.yml", "verifier-1", "acme/encore-runner", "main-2019", False),  # no author's run yet
])
def test_a_run_from_encore_runner_starts_from_its_own_branch_and_only_on_its_own_attempt(
        tmp_path, registry, runner, name, role, repo, paper, ok):
    r = run_start(name, tmp_path, registry, runner, ROLE=role, PAPER=paper, GITHUB_REPOSITORY=repo,
                  REGISTRY="encorescience/encore-registry")
    assert (r.returncode == 0) == ok, r.stdout + r.stderr
    if ok:
        out = dict(line.split("=", 1) for line in (tmp_path / "out").read_text().splitlines())
        # Every run of an attempt reads the registry at one commit, and says which state it started from.
        assert out["base_sha"] == git(registry, "rev-parse", "main").strip() and len(out["state"]) == 64


def test_a_run_starts_from_the_state_its_runner_keeps_and_tells_its_own_changes_from_it(tmp_path, registry, runner):
    r = run_start("attempt.yml", tmp_path, registry, runner, ROLE="author", REGISTRY="encorescience/encore-registry")
    assert r.returncode == 0, r.stdout + r.stderr
    work = tmp_path / "work"
    assert (work / "claims" / "demo-2020.yaml").read_text() == "paper: demo-2020\n"
    assert (work / "transcripts" / "demo-2020" / "claims.md").is_file() and not (work / ".encore").exists()
    # The state is committed in the job's checkout, so that only the run's own changes are collected after it.
    (work / "attempts").mkdir()
    (work / "attempts" / "demo-2020-01.yaml").write_text("id: demo-2020-01\n")
    git(work, "add", "-A", "--", "attempts", "claims", "transcripts")
    assert git(work, "diff", "--cached", "--name-only").split() == ["attempts/demo-2020-01.yaml"]
    # Nothing of the runner's clone is left where the agent could read the address it was fetched from.
    assert not (tmp_path / "temp" / "state").exists()


def test_a_runner_whose_branches_cannot_be_read_does_not_start_as_if_the_attempt_were_new(tmp_path, registry):
    r = run_start("papers.yml", tmp_path, registry, ROLE="claims", PAPER="new-2021",
                  REGISTRY="encorescience/encore-registry", RUNNER_REMOTE=str(tmp_path / "nowhere"))
    assert r.returncode != 0 and "Could not read the branches" in r.stdout


def test_the_registrys_own_runs_start_as_before(tmp_path, registry):
    # No registry named: the caller is the registry, and an attempt branch is continued whoever began it.
    r = run_start("attempt.yml", tmp_path, registry, ROLE="verifier-1", REGISTRY="")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_run_from_encore_runner_refuses_a_registry_that_is_not_a_repository(tmp_path, registry):
    r = run_start("attempt.yml", tmp_path, registry, ROLE="author", REGISTRY="x; rm -rf /")
    assert r.returncode != 0 and "Not a repository" in r.stdout
