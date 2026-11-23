# Encore protocol

This repository holds the protocol that Encore runs to test a paper's claims against its open data. The records it produces live in the registry, [encorescience/encore-registry](https://github.com/encorescience/encore-registry), and are published at [encorescience.org](https://encorescience.org).

## Contents

| Path | Holds |
| --- | --- |
| `docs/protocol.md` | The protocol: the roles, their order and the criteria each one applies. |
| `docs/agents/` | The prompt each agent role is given. |
| `schemas/` | The schemas of the claims, attempts and entries the protocol writes. |
| `tools/` | The code a run uses: prompt assembly, entry execution, the claims check, transcript cleaning and the archive adapters. |
| `encore_science/` | The `encore` command-line tool, published on PyPI as `encore-science`. |
| `.github/workflows/` | The workflows that run a paper's attempt. |

## Relation to the registry

The files keep the paths they had in the registry. The tools find the records through the repository root, so they run in a registry checkout with this repository's files laid over it. The tests run the same way: CI checks out the registry and copies these files over it.

A tagged release of this repository is a protocol version. Each attempt in the registry records the version it ran.

## History

These files were split out of the registry on 2026-11-23 with their history. A reference such as `encorescience/encore-registry#855` in an older commit message points to a pull request in the registry.

## License

Apache-2.0. See `LICENSE`.
