# Encore protocol

This repository holds the protocol that Encore runs to test a paper's claims against its open data. The records it produces live in the registry, [encorescience/encore-registry](https://github.com/encorescience/encore-registry), and are published at [encorescience.org](https://encorescience.org).

## Contents

| Path | Holds |
| --- | --- |
| `docs/protocol.md` | The protocol: the roles, their order and the criteria each one applies. |
| `docs/agents/` | The prompt each agent role is given. |
| `docs/outside-runs.md` | How a whole attempt is made from encore-runner, or another organization's fork of it with its own Claude account, and taken into the registry. |
| `schemas/` | The schemas of the claims, attempts and entries the protocol writes. |
| `tools/` | The code a run uses: prompt assembly, entry execution, the claims check, transcript cleaning and the archive adapters. |
| `encore_science/` | The `encore` command-line tool, published on PyPI as `encore-science`. |
| `.github/workflows/` | The workflows that run one role of an attempt, called from the registry, and the package's publishing. |

## Relation to the registry

The registry holds the records and names the protocol version it uses in its `protocol.lock` file. This repository's `docs/`, `schemas/` and `tools/` are laid over a checkout of the registry at that version, and the registry's `.gitignore` keeps them out of its commits. The tools find the records through the repository root, so they run in that combined checkout.

Three things lay the protocol over the registry:

- The workflows `attempt.yml` and `papers.yml`, which the registry's workflows of the same names call at the pinned version. An attempt's branch keeps the protocol text it began with, from the `protocol.lock` on that branch. The tools always come at the version main names.
- The registry's own workflows and its queue runner, through `tools/protocol.sh` in the registry.
- The `encore` command-line tool, for a run on your own machine.

The tests run the same way: CI checks out the registry and copies these files over it.

## Versions

A tag `v<major>.<minor>.<patch>` is a protocol version. To move the registry to a new one, tag it here, then change `protocol.lock` and the version in the registry's `attempt.yml` and `papers.yml` in one pull request. The registry's CI checks that the three agree.

A tag `encore-v<version>` publishes the `encore-science` package to PyPI (`publish-encore.yml`).

## History

These files were split out of the registry on 2026-11-23 with their history. A reference such as `encorescience/encore-registry#855` in an older commit message points to a pull request in the registry.

## License

Apache-2.0. See `LICENSE`.
