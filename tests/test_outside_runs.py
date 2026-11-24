"""Runs from another organization, with its own API key and paper store, whose results go to the registry by pull
request (docs/outside-runs.md)."""

from __future__ import annotations

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


def test_the_blind_audit_also_looks_for_the_outside_copy(tmp_path):
    # The audit is for a repeat attempt's reconcile run: an earlier record and this one.
    (tmp_path / "attempts").mkdir()
    for n in ("01", "02"):
        (tmp_path / "attempts" / f"demo-2020-{n}.yaml").write_text(f"id: demo-2020-{n}\n")
    (tmp_path / "transcripts" / "demo-2020").mkdir(parents=True)
    (tmp_path / "transcripts" / "demo-2020" / "author.md").write_text(
        "fetched https://github.com/acme-lab/encore-registry/blob/main/README.md\n"
        "fetched https://github.com/acme-labXencore-registry/x\n")
    audit = lambda repo: subprocess.run(
        ["bash", str(REPO / "tools" / "blind.sh"), "audit", "demo-2020"], cwd=tmp_path, capture_output=True,
        text=True, check=True, env={**os.environ, "GITHUB_REPOSITORY": repo}).stdout
    assert audit("acme-lab/encore-registry").splitlines() == [
        "1:fetched https://github.com/acme-lab/encore-registry/blob/main/README.md"]
    assert audit("encorescience/encore-registry") == ""
