"""Signed screen snapshots keep Excel identical even if sales change after rendering."""

from datetime import datetime
from decimal import Decimal
from io import BytesIO
import json

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
import xlsxwriter

from petcare.money import currency_precision
from petcare.services.ui_text import ui_text
from petcare.services.exceptions import ValidationError


def _signer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="petcare-report-v1"
    )


def snapshot(report, actor_id, tenant_id):
    data = {key: value for key, value in report.items() if key != "chart_bars"}
    return _signer().dumps(
        {
            "actor": actor_id,
            "tenant": tenant_id,
            "report": json.loads(json.dumps(data, default=str)),
        }
    )


def read_snapshot(token, actor_id, tenant_id):
    try:
        payload = _signer().loads(token, max_age=900)
    except (BadSignature, SignatureExpired, TypeError) as exc:
        raise ValidationError(
            ui_text(
                "Bản báo cáo đã hết hạn hoặc không hợp lệ. Tải lại báo cáo rồi xuất lại.",
                "The report snapshot has expired or is invalid. Reload the report and export again.",
            )
        ) from exc
    if payload.get("actor") != actor_id or payload.get("tenant") != tenant_id:
        raise ValidationError(
            ui_text(
                "Bản báo cáo không thuộc phiên người dùng và cửa hàng này.",
                "The report snapshot belongs to a different user or store.",
            )
        )
    return payload["report"]


def workbook_bytes(report):
    output = BytesIO()
    book = xlsxwriter.Workbook(
        output,
        {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False},
    )
    book.set_properties(
        {
            "title": "PetCare — Báo cáo kinh doanh",
            "company": report["tenant_name"],
            "author": "PetCare Manager",
        }
    )
    base = {"font_name": "Arial", "font_size": 11, "valign": "vcenter"}
    heading = book.add_format(
        {**base, "bold": True, "font_size": 16, "font_color": "#287A62"}
    )
    header = book.add_format(
        {
            **base,
            "align": "center",
            "bold": True,
            "bg_color": "#287A62",
            "font_color": "white",
            "text_wrap": True,
            "valign": "vcenter",
        }
    )
    text = book.add_format({**base, "text_wrap": True})
    precision = currency_precision(report["currency_code"])
    number_format = (
        "#,##0"
        + ("." + "0" * precision if precision else "")
        + (
            '" ₫"'
            if report["currency_code"] == "VND"
            else '" ' + report["currency_code"] + '"'
        )
    )
    money = book.add_format(
        {**base, "num_format": number_format, "font_color": "#1F624F"}
    )
    total_format = book.add_format(
        {**base, "num_format": number_format, "bold": True, "bg_color": "#E8F3ED"}
    )
    day_format = book.add_format({**base, "num_format": "dd/mm/yyyy"})
    time_format = book.add_format({**base, "num_format": "dd/mm/yyyy hh:mm"})
    growth_format = book.add_format({**base, "num_format": '0.0"%"'})

    def amount(sheet, row, col, value, fmt=money):
        value = Decimal(str(value))
        # Excel numbers have 15 significant digits. Preserve larger values as
        # exact text rather than silently rounding a monetary amount.
        if len(value.normalize().as_tuple().digits) > 15 or abs(value) >= Decimal(
            "1e15"
        ):
            sheet.write_string(
                row, col, format(value, "f") + " " + report["currency_code"], text
            )
        else:
            sheet.write_number(row, col, float(value), fmt)

    def setup(name, columns, title):
        sheet = book.add_worksheet(name)
        sheet.hide_gridlines(2)
        sheet.set_default_row(22)
        sheet.set_column(0, columns - 1, 20, text)
        sheet.merge_range(0, 0, 0, columns - 1, title, heading)
        sheet.set_row(0, 38)
        sheet.merge_range(
            1,
            0,
            1,
            columns - 1,
            report["tenant_name"]
            + " · "
            + str(report["start_date"])
            + " — "
            + str(report["end_date"]),
            text,
        )
        sheet.merge_range(
            2,
            0,
            2,
            columns - 1,
            "Chốt số liệu: " + report["captured_at"] + " · " + report["timezone"],
            text,
        )
        sheet.set_row(1, 32)
        sheet.set_row(4, 32)
        sheet.freeze_panes(5, 0)
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 0)
        sheet.repeat_rows(0, 4)
        sheet.set_footer("&L" + report["tenant_name"] + "&RTrang &P / &N")
        return sheet

    overview = setup("Tong quan", 2, "BÁO CÁO KINH DOANH")
    overview.set_column(0, 0, 30, text)
    overview.set_column(1, 1, 32)
    overview.write_row(4, 0, ["Chỉ tiêu", "Giá trị"], header)
    overview.write(5, 0, "Doanh thu đã thu")
    amount(overview, 5, 1, report["summary"]["revenue"], total_format)
    overview.write(6, 0, "Hóa đơn hoàn tất")
    overview.write_number(6, 1, report["summary"]["invoice_count"])
    overview.write(7, 0, "Doanh thu kỳ trước")
    amount(overview, 7, 1, report["previous"]["revenue"])
    overview.write(8, 0, "Thay đổi (%)")
    overview.write(
        8,
        1,
        (
            float(report["growth"])
            if report["growth"] is not None
            else "Không có nền so sánh"
        ),
        growth_format,
    )
    overview.write(9, 0, "Thú cưng đã bán")
    overview.write_number(9, 1, report["pets_sold"]["pets_sold"])
    overview.write(10, 0, "Tồn hàng hiện tại")
    overview.write_number(10, 1, int(report["inventory"]["units_in_stock"]))
    overview.write(11, 0, "Mặt hàng dưới ngưỡng")
    overview.write_number(11, 1, int(report["inventory"].get("low_stock_count", 0)))
    overview.merge_range(12, 0, 12, 1, "BẢN TIN TỰ ĐỘNG · PYTHON", header)
    for i, line in enumerate(report["brief"], 13):
        overview.merge_range(i, 0, i, 1, line, text)
        overview.set_row(i, 44)
    overview.set_row(17, 40)
    overview.set_row(18, 40)
    overview.merge_range(
        17,
        0,
        18,
        1,
        "Nguồn: hóa đơn đã thanh toán của cửa hàng. File dùng đúng snapshot trên màn hình, không tải lại dữ liệu. Tồn kho là số hiện tại lúc chốt, không phải tồn cuối kỳ. Giá trị vượt 15 chữ số được lưu dạng văn bản chính xác.",
        text,
    )
    daily = setup("Doanh thu ngay", 3, "DOANH THU THEO NGÀY")
    daily.write_row(4, 0, ["Ngày địa phương", "Doanh thu", "Hóa đơn"], header)
    for r, item in enumerate(report["daily"], 5):
        daily.write_datetime(r, 0, datetime.fromisoformat(item["date"]), day_format)
        amount(daily, r, 1, item["revenue"])
        daily.write_number(r, 2, item["invoice_count"])
    daily.autofilter(4, 0, 4 + len(report["daily"]), 2)
    details = setup("Chi tiet", 8, "CHI TIẾT DÒNG HÀNG ĐÃ THU")
    for column, width in enumerate((10, 24, 12, 14, 32, 10, 19, 19)):
        details.set_column(column, column, width, text)
    details.write_row(
        4,
        0,
        [
            "Hóa đơn",
            "Ngày thu địa phương",
            "Loại",
            "Mã",
            "Mặt hàng",
            "Số lượng",
            "Đơn giá",
            "Thành tiền",
        ],
        header,
    )
    for r, item in enumerate(report["details"], 5):
        details.write_number(r, 0, item["invoice_id"])
        details.write_datetime(
            r,
            1,
            datetime.fromisoformat(item["paid_at"]).replace(tzinfo=None),
            time_format,
        )
        details.write_string(
            r, 2, "Thú cưng" if item["item_type"] == "pet" else "Sản phẩm"
        )
        details.write_string(r, 3, item["code"])
        details.write_string(r, 4, item["name"])
        details.write_number(r, 5, item["quantity"])
        amount(details, r, 6, item["unit_price"])
        amount(details, r, 7, item["line_total"])
        details.set_row(r, max(34, ((len(item["name"]) + 29) // 30) * 16))
    if report["details"]:
        details.autofilter(4, 0, 4 + len(report["details"]), 7)
    total_row = 5 + len(report["details"])
    details.merge_range(total_row, 0, total_row, 6, "TỔNG DOANH THU", header)
    amount(details, total_row, 7, report["summary"]["revenue"], total_format)
    products = setup("San pham ban chay", 4, "TOP 10 SẢN PHẨM TRONG KỲ")
    products.set_column(1, 1, 40, text)
    products.write_row(4, 0, ["Mã", "Sản phẩm", "Số lượng bán", "Doanh thu"], header)
    for r, item in enumerate(report.get("top_products", []), 5):
        products.write_string(r, 0, item["code"])
        products.write_string(r, 1, item["name"])
        products.write_number(r, 2, int(item["quantity_sold"]))
        amount(products, r, 3, item["revenue"])
        products.set_row(r, max(32, ((len(item["name"]) + 33) // 34) * 16))
    book.close()
    return output.getvalue()
