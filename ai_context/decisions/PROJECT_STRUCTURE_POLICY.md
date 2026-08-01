# Project Structure Policy

Allowed root entries:

```text
pc_host/ sn32/ primer1/ primer2/ tiny1p5/ ai_context/
.github/workflows/
README.md .gitignore LICENSE
```

Only directly buildable/programmed target source belongs in target directories.
Architecture, decisions, ICDs, reference models, tests, evidence and migration
records belong in `ai_context/`. Target builds must not depend on `ai_context/`.

`.github/workflows/` is the only additional root-directory exception. It may run
portable Python/GCC/Icarus/static checks only and must not claim Gowin, Keil,
timing or hardware PASS.

Generated vendor artifacts and acceptance binaries are not committed to `main`;
store acceptance artifacts in GitHub Release/archive with tool versions, commit
SHA and SHA-256.

Legacy/candidate documents remain isolated under `ai_context/migration/`.
