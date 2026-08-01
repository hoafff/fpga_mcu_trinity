# Project Structure Policy

1. Root contains only `pc_host/`, `sn32/`, `primer1/`, `primer2/`, `tiny1p5/`,
   `ai_context/`, `README.md`, `.gitignore` and `LICENSE`.
2. Deployment source belongs inside its target. A target may be marked partial,
   but it must never be falsely marked buildable.
3. Testbench, reference models, evidence, migration records and detailed guides
   belong only in `ai_context/`.
4. No target may depend on `ai_context/` for a deployment build.
5. No generated `.fs`, `.hex`, `.axf`, build log, report or cache is committed.
6. The old repository may be mined file-by-file, but its root tree is forbidden.
7. Exact candidate files relocated during migration must remain hash-verifiable.
8. A status label must distinguish source-only, exact build and hardware proof.

Current exception: `sn32/` is intentionally a source-only partial integration
slice for P0.10/P0.11. Its manifest explicitly says it is not deployment
buildable; this is not a waiver of the final self-contained-target requirement.
