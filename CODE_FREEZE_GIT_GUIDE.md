# Đóng gói Git an toàn trước bảo vệ

Các lệnh dưới đây để **nhóm tự chạy** sau khi đọc diff. Trợ lý không stage, commit, tag hay push trong lượt chuẩn bị tài liệu này. Nhánh quan sát lúc rà soát: `solo/khang-petcare`; tag `v1.0-demo-ready` chưa tồn tại tại thời điểm kiểm tra 25/10/2026.

## 1. Xem thay đổi trước khi stage

```sh
cd "/Users/heisenbon/Documents/Workspace Code/NNLTPython/petcare-manager"
git branch --show-current
git status --short --untracked-files=all
git diff --check
git diff --stat
git diff -- petcare/i18n.py
git ls-files -u
git tag --list 'v1.0-demo-ready'
git ls-files -- .env 'backups/*' 'instance/pet-images/*' 'instance/product-images/*'
```

Điều kiện tiếp tục: đúng repo/nhánh mong muốn; không conflict (`git ls-files -u` không có dòng); diff check đạt; tag chưa có; không có `.env`, key/backup, ảnh upload thực tế trong danh sách tracked. Không dùng `git reset --hard`, `git clean -fd` hay ghi đè tag đã có.

`petcare/i18n.py` có sẵn đúng một comment `# pyrefly: ignore[missing-import]`. Các lệnh stage dưới bao gồm comment này để tag phản ánh đầy đủ working tree đang nghiệm thu; xem diff và xác nhận trước khi commit. Không revert để làm sạch status.

## 2. Stage đúng các đường dẫn đã rà soát

```sh
git add -- \
  .env.example .github/workflows/ci.yml \
  CHANGELOG.md README.md REPO_GUIDE.md docker-compose.yml \
  requirements.txt run.py petcare tests docs \
  DEMO_SCRIPT.md DEFENSE_QA_GUIDE.md CODE_FREEZE_GIT_GUIDE.md

git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git diff --cached
git status --short --untracked-files=all
```

Đọc toàn bộ staged diff và danh sách file mới. `docs/qa_reports/` là bộ bằng chứng lịch sử hư cấu được chủ động đưa vào commit, gồm báo cáo/ảnh/Excel/PDF/log và manifest; không có file `work/`, `.env`, SQL backup hoặc key. `.env.example` là mẫu được phép commit; không thay nó bằng bí mật thật. Nếu xuất hiện file ngoài phạm vi dự kiến hoặc thay đổi mới từ thành viên khác, dừng để rà soát rồi mới đi tiếp. Lệnh này không force-add file bị ignore.

Muốn gỡ một file stage nhầm mà vẫn giữ nội dung trên đĩa:

```sh
git restore --staged -- duong/dan/file-stage-nham
```

Thay đường dẫn minh họa bằng file cụ thể; không dùng `git restore` cho working tree hoặc `git clean` để xử lý phần việc chưa commit.

## 3. Commit sau khi đã duyệt staged diff

```sh
git commit -m "feat: complete four-phase PetCare demo MVP and defense documentation"
git status --short --untracked-files=all
git log -1 --oneline
```

Chỉ tạo tag sau khi commit thành công và `git status --short --untracked-files=all` **không còn dòng nào**. Nếu còn thay đổi, kiểm tra/stage/commit phần thực sự muốn đưa vào mốc đóng băng trước; không bỏ qua chỉ để đặt tag.

## 4. Tạo annotated tag và xác nhận mốc

```sh
git tag -a v1.0-demo-ready -m "PetCare v1.0 demo-ready: Phases 1–4 verified"
git show --no-patch --decorate v1.0-demo-ready
git rev-parse HEAD 'v1.0-demo-ready^{commit}'
git status --short --untracked-files=all
```

Hai hash ở lệnh `rev-parse` phải giống nhau; tag trỏ đúng commit vừa đóng băng. `git tag -a` tự từ chối nếu tên tag đã tồn tại: kiểm tra tag cũ, không dùng `-f` để ghi đè. Các lệnh này chỉ tạo mốc local, chưa upload lên remote; không có lệnh push trong checklist.

**Giới hạn bản sao:** tag chỉ lưu source/tài liệu/bằng chứng đã commit. Nó không sao lưu dữ liệu MySQL, `.env`, ảnh upload, volume Docker hoặc key mã hóa bị ignore. Giữ bộ backup dữ liệu hiện có và key ở nơi riêng, không đưa vào `docs/qa_reports/` hoặc Git. Các file Excel/PDF trong QA là mẫu lịch sử, không phải backup database.
