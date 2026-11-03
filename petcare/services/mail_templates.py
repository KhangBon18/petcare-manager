"""Plain-text transactional email copy for supported interface locales."""


def account_token_email(purpose, link, locale="vi"):
    if locale == "en":
        if purpose == "email_verification":
            return (
                "Verify your PetCare Manager email",
                "Verify your email address to protect your account.\n\n"
                "Open this single-use link within 24 hours:\n"
                f"{link}\n\n"
                "If you did not request this, you can ignore this email.",
            )
        return (
            "Reset your PetCare Manager password",
            "A password reset was requested for your PetCare Manager account.\n\n"
            "Open this single-use link within 30 minutes:\n"
            f"{link}\n\n"
            "If you did not request this, you can ignore this email.",
        )

    if purpose == "email_verification":
        return (
            "Xác minh email PetCare Manager",
            "Xác minh địa chỉ email để bảo vệ tài khoản của bạn.\n\n"
            "Mở liên kết dùng một lần này trong vòng 24 giờ:\n"
            f"{link}\n\n"
            "Nếu bạn không yêu cầu thao tác này, hãy bỏ qua email.",
        )
    return (
        "Đặt lại mật khẩu PetCare Manager",
        "Có yêu cầu đặt lại mật khẩu cho tài khoản PetCare Manager của bạn.\n\n"
        "Mở liên kết dùng một lần này trong vòng 30 phút:\n"
        f"{link}\n\n"
        "Nếu bạn không yêu cầu thao tác này, hãy bỏ qua email.",
    )


def invitation_email(store_name, role, link, locale="vi"):
    role_label = (
        ("an administrator" if role == "admin" else "a staff member")
        if locale == "en"
        else ("quản trị viên" if role == "admin" else "nhân viên")
    )
    if locale == "en":
        return (
            "Invitation to join a store on PetCare Manager",
            f'You have been invited to join "{store_name}" as {role_label}.\n\n'
            f"Accept this single-use invitation within 7 days:\n{link}\n\n"
            "If you were not expecting this invitation, you can ignore this email.",
        )
    return (
        "Lời mời tham gia cửa hàng trên PetCare Manager",
        f'Bạn được mời tham gia cửa hàng "{store_name}" với vai trò {role_label}.\n\n'
        f"Chấp nhận lời mời dùng một lần này trong vòng 7 ngày:\n{link}\n\n"
        "Nếu bạn không mong đợi lời mời này, hãy bỏ qua email.",
    )


def ownership_transfer_email(store_name, username, link, locale="vi"):
    if locale == "en":
        return (
            "Store ownership transfer request",
            f'The owner of "{store_name}" requested to transfer ownership to your account '
            f'"{username}". Sign in, open the ownership page, and confirm with your current '
            f"password within 72 hours:\n{link}\n\n"
            "This email is a notice only. It cannot be used to approve the transfer.",
        )
    return (
        "Yêu cầu bàn giao chủ cửa hàng",
        f'Chủ cửa hàng "{store_name}" đề nghị chuyển quyền sở hữu cho tài khoản '
        f'"{username}". Hãy đăng nhập, mở trang bàn giao và xác nhận bằng mật khẩu hiện tại '
        f"trong vòng 72 giờ:\n{link}\n\n"
        "Email này chỉ thông báo, không thể dùng để chấp thuận bàn giao.",
    )
