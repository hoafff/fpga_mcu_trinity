# Project Structure Policy

## 1. Root layout

Allowed root entries:

```text
pc_host/
sn32/
primer1/
primer2/
tiny1p5/
ai_context/
.github/          # optional; workflows only
README.md
.gitignore
LICENSE
```

`.github/` may contain only `workflows/` and repository metadata required for
portable CI. Do not create legacy roots such as `docs/`, `rtl/`, `targets/`,
`tb/`, `software/`, `constraints/`, `scripts/` or `tools/`.

## 2. Deployment vs context

- Code/project directly built or programmed for a target belongs in that target.
- Architecture, decisions, ICDs, golden model, testbench, tests, evidence, build
  guides, toolchain lock, status and migration records belong in `ai_context/`.
- Target builds must not depend on `ai_context/`.
- Partial targets must not be described as buildable.

## 3. Active project memory

- Entry point: `ai_context/README_AI.md`.
- Active architecture: `ai_context/architecture/`.
- Active decisions: `ai_context/decisions/`.
- Interfaces: `ai_context/interfaces/`.
- Status/open items: `ai_context/status/`.
- Toolchain lock: `ai_context/toolchains/`.
- One authoritative decision per subject; secondary docs reference its ID.

## 4. Legacy isolation

Legacy/candidate docs required for provenance remain under
`ai_context/migration/` and have no architectural authority. Git history is kept;
probe commits are historical connectivity probes, not active source.

## 5. Evidence/artifacts

- Do not commit `.fs`, `.hex`, `.axf`, build cache or generated vendor report to
  the `main` source tree.
- Acceptance binaries/reports go to GitHub Release/artifact archive with tool
  versions, commit SHA and SHA-256.
- Status must distinguish `TESTED`, `BUILD-PENDING`, `PHYSICAL-PENDING`.

## 6. Portable CI exception

`.github/workflows/` may run only portable checks:

- Python tests;
- repository layout and candidate hash checks;
- GCC reference tests;
- Icarus/Verilog simulation;
- format/static checks.

CI must not claim Gowin synthesis/P&R/timing, Keil exact-target build or hardware
PASS. When the first workflow is added, update `check_repository_layout.py` in the
same commit so policy and checker agree.

## 7. Candidate preservation

The 29 P0-J19-001 files remain hash-verifiable. Relocation requires simultaneous
FILE_MAP and hash-manifest updates without changing byte content.
