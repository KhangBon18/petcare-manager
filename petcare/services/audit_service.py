"""Read-only administration view for transactional audit events."""

from petcare.database.connection import read_connection
from petcare.repositories import audit_repo
from petcare.services.common import page_window, require_actor

EVENT_LABELS = {
    "auth.login_succeeded": "Đăng nhập thành công",
    "auth.logout": "Đăng xuất",
    "auth.store_switched": "Chuyển cửa hàng",
    "tenant.settings_updated": "Cập nhật cài đặt cửa hàng",
    "account.email_changed": "Cập nhật email tài khoản",
    "account.email_removed": "Gỡ email tài khoản",
    "account.email_verified": "Xác minh email tài khoản",
    "account.password_reset": "Đặt lại mật khẩu",
    "invoice.created": "Tạo hóa đơn",
    "invoice.paid": "Thu tiền hóa đơn",
    "invoice.cancelled": "Hủy hóa đơn",
    "stock.adjusted": "Điều chỉnh tồn kho",
    "user.created": "Tạo tài khoản",
    "user.updated": "Cập nhật tài khoản",
    "membership.invitation_created": "Tạo lời mời thành viên",
    "membership.invitation_accepted": "Thành viên chấp nhận lời mời",
    "membership.invitation_revoked": "Thu hồi lời mời thành viên",
    "membership.owner_transfer_requested": "Đề nghị bàn giao chủ cửa hàng",
    "membership.owner_transfer_cancelled": "Thu hồi yêu cầu bàn giao chủ cửa hàng",
    "membership.owner_transferred": "Đã bàn giao chủ cửa hàng",
    "tenant.exported": "Xuất dữ liệu cửa hàng",
    "customer.created": "Thêm khách hàng",
    "customer.updated": "Sửa hồ sơ khách hàng",
    "customer.status_changed": "Cập nhật trạng thái khách hàng",
    "product.created": "Thêm sản phẩm",
    "product.updated": "Sửa sản phẩm",
    "product.status_changed": "Cập nhật trạng thái sản phẩm",
    "pet.created": "Thêm thú cưng",
    "pet.updated": "Sửa hồ sơ thú cưng",
    "pet.status_changed": "Cập nhật trạng thái thú cưng",
}
ENTITY_LABELS = {
    "session": "Phiên làm việc",
    "invoice": "Hóa đơn",
    "product": "Sản phẩm",
    "pet": "Thú cưng",
    "customer": "Khách hàng",
    "user": "Tài khoản",
    "invitation": "Lời mời",
    "tenant": "Cửa hàng",
}


def list_events(actor_id, page="1"):
    with read_connection() as connection:
        require_actor(connection, actor_id, admin=True)
        total = audit_repo.count_events(connection)
        _current, offset, pagination = page_window(page, total)
        items = audit_repo.list_events(connection, pagination["page_size"], offset)
        for event in items:
            event["event_label"] = EVENT_LABELS.get(event["event_type"], "Thay đổi dữ liệu")
            event["entity_label"] = ENTITY_LABELS.get(event["entity_type"], event["entity_type"])
        return {
            "items": items,
            "pagination": pagination,
        }
