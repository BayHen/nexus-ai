# Giao diện AI Assistant và Analytics

## Phạm vi Task 24

Task 24 bổ sung workspace `/assistant` và mở rộng `/analytics`. Browser chỉ gọi BFF cùng origin `/api/backend/*`; API key OpenAI, provider configuration và tenant identifier tin cậy không xuất hiện trong JavaScript phía client.

## Hành trình người dùng

1. Người dùng đăng nhập, chọn organization và mở **Trợ lý AI**.
2. UI tải danh sách tài liệu mà backend cho phép qua `GET /knowledge/documents`.
3. Người có quyền có thể upload PDF, TXT hoặc Markdown. Backend kiểm tra loại, kích thước, document permission, chunking và embedding; UI chỉ hiển thị kết quả thật hoặc lỗi rõ ràng.
4. Người dùng chọn câu hỏi gợi ý hoặc nhập câu hỏi. Với câu hỏi so sánh, UI yêu cầu hai khoảng ngày.
5. `POST /agent/ask` được gửi không kèm tenant ID do client kiểm soát. Backend suy ra active tenant từ authentication context, thực thi RBAC và chọn tool read-only.
6. UI hiển thị status, tool đã chọn, số state transitions và citations. Nội dung được render dưới dạng React text, không dùng `dangerouslySetInnerHTML`.
7. Lịch sử tối đa 30 message được lưu trong `sessionStorage` với key theo active organization. Dữ liệu không được đồng bộ sang server và bị giới hạn trong tab hiện tại.
8. Người dùng kiểm tra analytics theo date range. UI tải kỳ hiện tại, kỳ liền trước cùng số ngày, revenue series và low-stock records từ API thật.

## Trạng thái và giới hạn

- `completed`: tool hoàn tất; citation xuất hiện khi nguồn là Knowledge Base.
- `unsupported`: câu hỏi ngoài tool scope hoặc không đủ evidence; UI giữ nguyên thông báo từ backend.
- `denied`: backend từ chối quyền; UI không hiển thị dữ liệu thay thế.
- `failed`: timeout hoặc lỗi tool; UI hiển thị lỗi chung, không phơi bày prompt, stack trace hay secret.
- Tool status phản ánh response cuối cùng, chưa phải streaming event theo thời gian thực.
- Upload API hiện xử lý đồng bộ nên trạng thái indexing là `ready` hoặc `failed`; chưa có polling trạng thái trung gian.
- Lịch sử trong `sessionStorage` phù hợp cho UX tạm thời, không phải conversation persistence đa thiết bị.
- AI có thể sai; người dùng phải kiểm chứng citations và số liệu trước quyết định kinh doanh.

## Security boundary

- Backend authorization và active tenant là nguồn quyết định duy nhất; việc ẩn navigation không phải security control.
- AI output và excerpt được React escape mặc định. UI không thực thi HTML, script hay URL do model sinh ra.
- Không có API key trong environment public hoặc request browser.
- Không fallback mock khi backend lỗi.
- Document list và citations chỉ được hiển thị sau khi backend áp dụng tenant/document permission.

## Kiểm thử

```powershell
Set-Location frontend
npm.cmd test
npm.cmd run test:e2e
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Vitest dùng deterministic API fakes để kiểm tra citations, lỗi authorization, chart, comparison và inventory alerts. Playwright intercept BFF tại browser boundary để kiểm tra toàn bộ hành trình UI trên desktop Chromium và mobile Chromium; đây không phải kiểm thử model live và không đo chất lượng retrieval thực tế.
