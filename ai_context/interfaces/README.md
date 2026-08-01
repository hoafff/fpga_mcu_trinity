# Interface contract index

Authoritative implementation contracts:

1. `SPI_CONTROL_PLANE_ICD_v0.1.md`
2. `PC_SN32_PROTOCOL_ICD_v0.1.md`
3. `MLKEM_BACKEND_SPEC_v0.1.md`
4. `PROTOCOL_REGISTRY_v0.1.json`

Detailed payload/API documents incorporated by reference:

- `SPI_CONTROL_PLANE_PAYLOAD_DETAIL_v0.1.md`
- `PC_SN32_PROTOCOL_PAYLOAD_DETAIL_v0.1.md`
- `MLKEM_BACKEND_API_DETAIL_v0.1.md`

The current main ICD/registry controls status, enums, numeric values and any
explicit override. The detail documents retain byte-exact request/response/API
layouts omitted from the compact main ICD. Their historical `ASSUMED` status and
old open-item wording are superseded: SPI and PC contracts are approved
implementation baselines; ML-KEM backend implementation is approved with V-001
verification pending.
