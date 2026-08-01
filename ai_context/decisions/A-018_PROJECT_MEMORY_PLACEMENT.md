# A-018 — Canonical project-memory placement

**Status:** `CONFIRMED`  
**Effective on:** `main`

- Only direct target build/program source belongs in `pc_host/`, `sn32/`,
  `primer1/`, `primer2/`, `tiny1p5/`.
- Architecture, decisions, interfaces, reference models, tests, evidence,
  toolchain locks and migration records belong under `ai_context/`.
- `ai_context/README_AI.md` is the mandatory entrypoint.
- Legacy candidate documents remain isolated under `ai_context/migration/`.
- `.github/workflows/` is the sole additional root-directory exception and may
  contain portable CI only.
- Target builds must not depend on `ai_context/`.

System Specification v0.4 incorporates this placement directly; no path
supersession note is required for the active baseline.
