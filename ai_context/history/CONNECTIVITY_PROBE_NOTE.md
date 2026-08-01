# Git History Note — Connectivity Probe Commits

**Status:** `CONFIRMED`  
**Decision:** D60 / A-027

Several historical commits named `probe*` were created while testing GitHub write
connectivity. Their files were removed from the active tree before implementation
baseline work. The commits remain in history intentionally:

- no force-push or history rewrite;
- provenance and existing commit references remain stable;
- probe files have no authority and are not deployment source;
- implementation work starts from the current clean `main` tree.
