"""The workflows that run one role of an attempt, attempt.yml and papers.yml. The tests run in a checkout of the
registry with the protocol laid over it (test.yml), where .github/ is the registry's own: the workflows are read
from this repository's checkout, PROTOCOL_ROOT."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = Path(os.environ.get("PROTOCOL_ROOT") or REPO) / ".github" / "workflows"


def test_a_repeat_authors_commit_may_remove_the_questions_filed_by_dataset():
    # Issues 658 and 664: blind.sh leaves out a repeat author's earlier questions, which before the cutover were
    # questions/<paper>/<dataset>.yaml; the commit job refused their removal as a change outside the paper.
    import re
    workflow = (WORKFLOWS / "attempt.yml").read_text()
    allowed = re.search(r'allowed="(\^\(attempts.*?)"', workflow).group(1).replace("$FOLDER", "pakhomov-2023")
    ok = lambda path: re.search(allowed, path) is not None
    assert ok("questions/pakhomov-2023/000686.yaml") and ok("questions/pakhomov-2023.yaml")
    assert not ok("questions/silkuniene-2025/001276.yaml") and not ok("questions/pakhomov-2023/a/b.yaml")
    assert not ok("claims/silkuniene-2025.yaml")




def test_the_agents_job_guards_the_runners_memory_before_the_agent_starts():
    # rozsa-2023, 2026-11-19: three author runs ended with the runner starved by the agent's own scripts and nothing
    # saved. The guard ends the largest Python process first, never the agent or the runner, and a runner without
    # it goes on.
    import re
    import yaml
    workflow = yaml.safe_load((WORKFLOWS / "attempt.yml").read_text())
    steps = next(j["steps"] for j in workflow["jobs"].values() if any(s.get("name") == "Run the agent" for s in j["steps"]))
    names = [s.get("name") for s in steps]
    assert names.index("Guard the runner's memory") < names.index("Run the agent")
    run = steps[names.index("Guard the runner's memory")]["run"]
    assert "exit 0" in run and run.rstrip().endswith('|| echo "earlyoom did not start; no guard"')
    prefer, avoid = (re.search(rf"--{k} '([^']+)'", run).group(1) for k in ("prefer", "avoid"))
    for name, spared in (("python3.12", False), ("python", False), ("jupyter-nbconvert", False), ("node", True),
                         ("claude", True), ("Runner.Worker", True), ("Runner.Listener", True)):
        assert bool(re.search(avoid, name)) == spared and bool(re.search(prefer, name)) != spared, name




def test_an_authors_large_scratch_files_are_left_out_of_its_changes():
    # petersen-2020, 2026-11-15: two pickles of 1.4 and 2.6 GB in the entry made a patch git refused to apply. New
    # files over 20 MB are removed before the changes are collected, with a warning.
    workflow = (WORKFLOWS / "attempt.yml").read_text()
    drop = workflow.index('git ls-files --others --exclude-standard -z -- "${paths[@]}"')
    assert '-gt 20000000' in workflow[drop:drop + 400] and "::warning::Left out of the changes" in workflow[drop:drop + 400]
    assert drop < workflow.index('git add -A -- "${paths[@]}" && git diff --cached --binary')




def test_a_repeat_authors_commit_moves_a_finished_earlier_attempts_transcripts_aside(tmp_path):
    # A repeat attempt that does not read the claims again found the earlier attempt's transcripts still in the
    # folder, and its blind author's revision runs could read the earlier verifiers' reports (three replicates did).
    # The author's commit now archives them whenever a finished attempt's are there (its recorder's transcript).
    workflow = (WORKFLOWS / "attempt.yml").read_text()
    line = next(x.strip() for x in workflow.splitlines() if 'if [ "$ROLE" = author ] && {' in x)
    def archives(role, files):
        d = tmp_path / f"{role}-{len(files)}-{'-'.join(sorted(files))[:40]}"; (d / "transcripts" / "x").mkdir(parents=True)
        for f in files: (d / "transcripts" / "x" / f).write_text("t")
        script = f'ROLE={role}; FOLDER=x\n{line} echo yes; else echo no; fi'
        return subprocess.run(["bash", "-c", script], cwd=d, capture_output=True, text=True).stdout.strip()
    assert archives("author", ["claims.md", "author.md", "verifier-2-report.md", "recorder.md"]) == "yes"   # the hole
    assert archives("author", ["author.md", "recorder.md"]) == "yes"
    assert archives("author", ["claims.md", "claims-check.md"]) == "no"       # this attempt's own claims runs stay
    assert archives("author", ["claims.md", "author.md"]) == "no"             # its own failed first author run stays
    assert archives("author-revise-1", ["claims.md", "recorder.md"]) == "no"
    # The reconcile run follows the instructions as they are now, not as the branch had them when its attempt began.
    assert 'git -C .protocol archive "$PROTOCOL_REF" -- docs/agents/reconcile.md docs/protocol.md schemas' in workflow




def test_the_reconcile_run_is_given_the_earlier_attempts_entry():
    # It reads both attempts' code to say why an outcome differs; the earlier entry is copied from main, outside the
    # folders whose changes are collected.
    workflow = (WORKFLOWS / "attempt.yml").read_text()
    step = workflow[workflow.index("name: Put the earlier attempt's entry under earlier-entry/"):]
    assert "if: inputs.role == 'reconcile'" in step[:200] and 'git archive FETCH_HEAD "entries/$FOLDER"' in step[:500]
    assert "earlier-entry" not in workflow[workflow.index("paths=(attempts claims entries README.md)"):][:300]
    assert "`earlier-entry/`" in (REPO / "docs" / "agents" / "reconcile.md").read_text()





def test_a_replicate_has_its_own_branch_and_concurrency_group():
    # docs/replicates.md: a replicate's runs commit to replicate/<paper>/<rN>, and one waits for no other.
    for name in ("attempt.yml", "papers.yml"):
        workflow = (WORKFLOWS / name).read_text()
        assert 'BRANCH="replicate/$FOLDER/$REPLICATE"' in workflow and "format('-{0}', inputs.replicate)" in workflow
    assert "format('replicate/{0}/{1}'" in (WORKFLOWS / "attempt.yml").read_text()


def _lay_step(workflow: str, name: str) -> str:
    import yaml
    jobs = yaml.safe_load(workflow)["jobs"]
    return next(s["run"] for j in jobs.values() for s in j["steps"] if s.get("name") == name)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"})


def test_an_attempts_branch_keeps_the_protocol_text_it_began_with_and_takes_mains_tools(tmp_path):
    protocol = tmp_path / ".protocol"
    (protocol / "docs" / "agents").mkdir(parents=True); (protocol / "schemas").mkdir(); (protocol / "tools").mkdir()
    _git(protocol, "init", "-q", "-b", "main")
    def version(tag, text):
        for path in ("docs/protocol.md", "docs/agents/reconcile.md", "schemas/attempt.json", "tools/agent_run.py"):
            (protocol / path).write_text(f"{text} {path}")
        _git(protocol, "add", "-A"); _git(protocol, "commit", "-q", "-m", tag); _git(protocol, "tag", tag)
    version("v1", "old"); version("v2", "new")
    (protocol / "docs" / "dropped.md").write_text("v2 only"); _git(protocol, "add", "-A")
    _git(protocol, "commit", "-q", "--amend", "-m", "v2"); _git(protocol, "tag", "-f", "v2")
    run = _lay_step((WORKFLOWS / "attempt.yml").read_text(), "Lay the protocol over the attempt's branch")
    def lay(role, branch_lock):
        # As the job has it: main's version laid, then the branch checked out, then this step.
        work = tmp_path / f"{role}-{branch_lock or 'none'}"
        work.mkdir()
        subprocess.run(["cp", "-R", str(protocol), str(work / ".protocol")], check=True)
        subprocess.run(["bash", "-c", "git -C .protocol archive v2 -- docs schemas tools | tar -x"], cwd=work, check=True)
        if branch_lock:
            (work / "protocol.lock").write_text(branch_lock + "\n")
        else:   # a branch from before protocol.lock tracks the protocol's text itself
            (work / "docs" / "protocol.md").write_text("tracked docs/protocol.md")
        subprocess.run(["bash", "-euo", "pipefail", "-c", run], cwd=work, check=True,
                       env={**os.environ, "PROTOCOL_REF": "v2", "ROLE": role, "GITHUB_STEP_SUMMARY": "/dev/null"})
        assert not (work / ".protocol").exists()
        return {path: (work / path).read_text().split()[0] if (work / path).exists() else None
                for path in ("docs/protocol.md", "docs/agents/reconcile.md", "schemas/attempt.json",
                             "tools/agent_run.py", "docs/dropped.md")}
    began_v1 = lay("verifier-1", "v1")
    assert began_v1 == {"docs/protocol.md": "old", "docs/agents/reconcile.md": "old", "schemas/attempt.json": "old",
                        "tools/agent_run.py": "new", "docs/dropped.md": None}
    assert lay("reconcile", "v1") == {**began_v1, "docs/protocol.md": "new", "docs/agents/reconcile.md": "new",
                                      "schemas/attempt.json": "new"}
    assert set(lay("author", "v2").values()) == {"new", "v2"}
    old_branch = lay("author", "")
    assert old_branch["docs/protocol.md"] == "tracked" and old_branch["tools/agent_run.py"] == "new"


def test_every_input_the_registry_passes_is_declared():
    # The registry's papers.yml passed papers_only, which this one declared only for workflow_dispatch: every run of
    # it failed at startup (2026-11-23). The registry's workflows pass these inputs, named in its own workflow_dispatch.
    import yaml
    passed = {"attempt.yml": {"paper", "dataset", "dandiset", "role", "model", "version", "account", "replicate"},
              "papers.yml": {"dataset", "paper", "dandiset", "role", "papers_only", "model", "account", "replicate"}}
    for name, inputs in passed.items():
        declared = set(yaml.safe_load((WORKFLOWS / name).read_text())[True]["workflow_call"]["inputs"])
        assert inputs <= declared, (name, inputs - declared)
