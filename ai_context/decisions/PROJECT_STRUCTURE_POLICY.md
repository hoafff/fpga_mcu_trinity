# Project Structure Policy

## 1. Root layout

Root chỉ được chứa:

```text
pc_host/
sn32/
primer1/
primer2/
tiny1p5/
ai_context/
README.md
.gitignore
LICENSE
```

Không tạo các root legacy như `docs/`, `rtl/`, `targets/`, `tb/`, `software/`,
`constraints/`, `scripts/` hoặc `tools/`.

## 2. Phân tách deployment và context

- Code/project trực tiếp build hoặc nạp cho target phải nằm trong target tương ứng.
- Mọi nội dung không trực tiếp tham gia deployment build phải nằm trong
  `ai_context/`: kiến trúc, quyết định, tài liệu, golden model, testbench, test,
  evidence, build guide và migration records.
- Target không được phụ thuộc `ai_context/` để build hoặc nạp.
- Target có thể được đánh dấu partial, nhưng không được ghi sai là buildable.

## 3. Active project memory

- `ai_context/README_AI.md` là entrypoint bắt buộc cho AI/nhân sự mới.
- `ai_context/architecture/` chỉ chứa architecture baseline hiện hành đã duyệt.
- `ai_context/decisions/` chỉ chứa Decision Register hiện hành và policy quản trị.
- `ai_context/status/` phản ánh source/test/build/hardware truth hiện tại.
- Một quyết định chỉ có một bản có thẩm quyền; tài liệu phụ phải dẫn chiếu ID.

## 4. Legacy and migration isolation

- File legacy/candidate cần bảo toàn hash phải nằm dưới `ai_context/migration/`.
- Nội dung dưới `migration/` và `evidence/` không có thẩm quyền định nghĩa kiến trúc.
- Không để tài liệu legacy có tên/đường dẫn giống active architecture hoặc active
  decision register.
- Git history giữ provenance; không cần giữ một baseline cũ trong vùng active.

## 5. Evidence and generated artifacts

- Không commit `.fs`, `.hex`, `.axf`, build cache hoặc generated report vào source
  tree của `main`.
- Acceptance binary/report được lưu ở GitHub Release hoặc artifact archive cùng
  tool version, commit SHA và SHA-256.
- Status phải phân biệt `TESTED`, `BUILD-PENDING` và `PHYSICAL-PENDING`.

## 6. Candidate preservation

- 29 file P0-J19-001 phải tiếp tục hash-verifiable.
- Di chuyển file candidate được phép nếu cập nhật đồng thời FILE_MAP và hash
  manifest mà không thay đổi byte content.

## 7. Current exception

`sn32/` hiện là source-only partial integration slice cho P0.10/P0.11 và không
phải firmware deployment hoàn chỉnh. Exception này không miễn yêu cầu target phải
tự chứa trước khi được coi là buildable.
