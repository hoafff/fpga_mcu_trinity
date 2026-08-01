# A-018 — Canonical project-memory placement

**Status:** `CONFIRMED`  
**Effective on:** `main`  
**Scope:** Chỉ chuẩn hóa vị trí lưu context/tài liệu; không thay đổi kiến trúc chức năng hoặc wire format.

## Decision

- Chỉ code/project trực tiếp build hoặc nạp cho từng target nằm trong `pc_host/`, `sn32/`, `primer1/`, `primer2/`, `tiny1p5/`.
- Mọi kiến trúc, quyết định, tài liệu, golden model, testbench, test, evidence, build guide và migration record nằm dưới `ai_context/`.
- `ai_context/README_AI.md` là entrypoint bắt buộc cho AI/người mới.
- Active architecture nằm trong `ai_context/architecture/`; active decisions nằm trong `ai_context/decisions/`; implementation truth nằm trong `ai_context/status/`.
- Legacy candidate documents phải cách ly dưới `ai_context/migration/` và không có thẩm quyền kiến trúc.
- Không tạo root `docs/`, `verification/` hoặc `tests/`.
- Target không được phụ thuộc `ai_context/` để build hoặc nạp.

## Supersession

Quyết định này ghi đè **chỉ phần đường dẫn lưu trữ** tại:

- System Specification v0.3 §25;
- Q50 của Decision Register v0.3;
- amendment A-006 của Decision Register v0.3.

Đường dẫn golden model có hiệu lực là:

```text
ai_context/verification/reference/
```

Mọi nội dung chức năng khác của System Specification và Decision Register v0.3 vẫn giữ nguyên hiệu lực.
