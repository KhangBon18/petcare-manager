"""Local, deterministic responses for the shop assistant."""

from __future__ import annotations

from petcare.i18n import translate
from petcare.money import format_money
from petcare.services.assistant_query import query_period
from petcare.services.catalog_intent import (
    _STOCK_INTENT_PHRASES,
    _catalog_preview_truncated,
    _normalize,
    _pet_search,
    _product_intent,
    _product_search,
    _question_intent,
)
from petcare.timezones import format_tenant_date


def _money(amount, currency_code, locale="vi") -> str:
    return format_money(amount, currency_code, "en_US" if locale == "en" else "vi_VN")


def _preview_note(total: int, shown: int, locale="vi") -> str:
    if total <= shown:
        return ""
    if locale == "en":
        return f" (showing the first {shown})"
    return f" (đang hiển thị {shown} mục đầu tiên)"


def _counted(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def top_products_answer(insight: dict, locale="vi") -> str:
    """Format a report-backed, read-only top-products answer."""
    english = locale == "en"
    period_labels = {
        "today": ("hôm nay", "today"),
        "7d": ("7 ngày gần nhất", "the last 7 days"),
        "week": ("tuần này", "this week"),
        "last_week": ("tuần trước", "last week"),
        "month": ("tháng này", "this month"),
        "last_month": ("tháng trước", "last month"),
    }
    vi_period, en_period = period_labels.get(insight["period"], period_labels["7d"])
    date_range = (
        f"{format_tenant_date(insight['start_date'], locale)} – "
        f"{format_tenant_date(insight['end_date'], locale)}"
    )
    items = insight["items"]
    if not items:
        return (
            f"Không có sản phẩm bán ròng trong {vi_period} ({date_range})."
            if not english else
            f"No products had net paid sales during {en_period} ({date_range})."
        )
    rows = []
    for index, item in enumerate(items, start=1):
        amount = _money(item["revenue"], insight["currency_code"], locale)
        if english:
            rows.append(
                f"{index}. {item['name']} ({item['code']}) — "
                f"{item['quantity_sold']} net units; {amount} net sales"
            )
        else:
            rows.append(
                f"{index}. {item['name']} ({item['code']}) — "
                f"bán ròng {item['quantity_sold']} sản phẩm; doanh thu ròng {amount}"
            )
    if english:
        return (
            f"Top products for {en_period} ({date_range}), ranked by net units sold "
            f"after returns recorded in the period:\n" + "\n".join(rows)
        )
    return (
        f"Sản phẩm bán chạy {vi_period} ({date_range}), xếp theo số lượng bán ròng "
        f"sau khi trừ hàng trả trong kỳ:\n" + "\n".join(rows)
    )


def local_answer(question: str, context: dict, locale="vi") -> str:
    query = _normalize(question)
    intent = _question_intent(question)
    period = query_period(query)
    locale = locale if locale in {"vi", "en"} else "vi"
    english = locale == "en"
    summary = context["summary"]
    currency_code = context["currency_code"]
    low_stock_count = summary.get("low_stock_count", len(context["low_stock"]))
    if intent == "revenue":
        if period == "month" and "revenue_month" in summary:
            amount, period_vi, period_en = summary["revenue_month"], "tháng này", "this month"
        elif period == "week" and "revenue_week" in summary:
            amount, period_vi, period_en = summary["revenue_week"], "tuần này", "this week"
        else:
            amount, period_vi, period_en = summary["revenue_today"], "hôm nay", "today"
        if english:
            revenue_label = "Today's paid revenue" if period_en == "today" else f"Paid revenue for {period_en}"
            return (
                f"{revenue_label} is {_money(amount, currency_code, locale)}. "
                "This includes paid invoices only. Open Reports to choose another date range."
            )
        return (
            f"Doanh thu đã thanh toán {period_vi} là {_money(amount, currency_code)}. "
            "Con số này chỉ tính hóa đơn đã thanh toán. Mở mục Báo cáo để lọc khoảng ngày khác."
        )
    if intent == "image":
        if english:
            return (
                "Open Pets → Find by image, then choose a file or capture one with the laptop camera. "
                "Local mode ranks saved profile photos by color and composition; it is not a trained "
                "animal detector. Generative image analysis only runs when a vision endpoint is configured."
            )
        return (
            "Mở Thú cưng → Tìm bằng ảnh, rồi chọn ảnh hoặc bật camera laptop để chụp. "
            "Chế độ cục bộ xếp hạng ảnh hồ sơ theo màu và bố cục, chưa phải mô hình nhận diện động vật. "
            "Phân tích ngữ nghĩa chỉ hoạt động khi cửa hàng cấu hình endpoint AI Vision."
        )
    pet_intent = intent == "pet"
    if pet_intent:
        pets, narrowed = _pet_search(question, context)
        incomplete = _catalog_preview_truncated(context, "available_pets")
        if not pets:
            if narrowed and incomplete:
                scanned = len(context.get("available_pets", []))
                if english:
                    return (
                        f"No matching pet appeared in the first {scanned} of "
                        f"{summary['available_pets']} available profiles. The catalog preview is limited, "
                        "so I can't rule out matches outside it. Check the full Pets list or narrow the filters."
                    )
                return (
                    f"Chưa thấy cá thể khớp trong {scanned} hồ sơ đầu tiên trên tổng số "
                    f"{summary['available_pets']} thú cưng đang bán. Danh mục trợ lý kiểm tra chưa đầy đủ, "
                    "nên chưa thể kết luận cửa hàng không có kết quả. Hãy xem toàn bộ danh sách Thú cưng "
                    "hoặc thu hẹp điều kiện tìm kiếm."
                )
            return (
                "No available pets match those filters. Try a different species, breed, or coat color."
                if english else
                "Chưa có thú cưng đang bán khớp các điều kiện này. Thử đổi loài, giống hoặc màu lông nhé."
            )
        shown_pets = pets[:8] if narrowed else pets[:12]
        total = len(pets) if narrowed else summary["available_pets"]
        if english:
            rows = "\n".join(
                f"• {pet['name']} — {pet.get('breed') or 'breed not provided'}; "
                f"coat {translate(pet.get('coat_color') or 'chưa cập nhật', locale)}; "
                f"eyes {translate(pet.get('eye_color') or 'chưa cập nhật', locale)}"
                + (f"; {_money(pet['sale_price'], currency_code, locale)}" if pet.get("sale_price") is not None else "")
                for pet in shown_pets
            )
        else:
            rows = "\n".join(
                f"• {pet['name']} — {pet.get('breed') or 'chưa rõ giống'}; "
                f"lông {pet.get('coat_color') or 'chưa cập nhật'}; mắt {pet.get('eye_color') or 'chưa cập nhật'}"
                + (f"; {_money(pet['sale_price'], currency_code)}" if pet.get("sale_price") is not None else "")
                for pet in shown_pets
            )
        if english:
            phrase = _counted(total, "pet") + (" is" if total == 1 else " are")
            if narrowed and incomplete:
                return (
                    f"At least {total} matching pet(s) appeared in the first "
                    f"{len(context.get('available_pets', []))} profiles; the full matching count may be higher. "
                    f"Showing {len(shown_pets)}:\n{rows}"
                )
            return f"{phrase} available for sale{_preview_note(total, len(shown_pets), locale)}:\n{rows}"
        if narrowed and incomplete:
            return (
                f"Trong phần xem trước có ít nhất {total} thú cưng khớp; trợ lý đã kiểm tra "
                f"{len(context.get('available_pets', []))} hồ sơ đầu tiên trên tổng số "
                f"{summary['available_pets']} cá thể. Tổng số khớp có thể cao hơn. "
                f"Đang hiển thị {len(shown_pets)} mục:\n{rows}"
            )
        return (
            f"Có {total} thú cưng đang sẵn sàng"
            f"{_preview_note(total, len(shown_pets))}:\n{rows}"
        )
    stock_intent = any(phrase in query for phrase in _STOCK_INTENT_PHRASES)
    if stock_intent and _product_intent(query, question):
        products, narrowed = _product_search(question, context)
        incomplete = _catalog_preview_truncated(context, "products")
        if narrowed:
            if not products:
                if incomplete:
                    scanned = len(context.get("products", []))
                    if english:
                        return (
                            f"No matching product appeared in the first {scanned} of "
                            f"{summary['active_products']} active products. The catalog preview is limited, "
                            "so I can't rule out matches outside it. Check the full Products list."
                        )
                    return (
                        f"Chưa thấy sản phẩm khớp trong {scanned} sản phẩm đầu tiên trên tổng số "
                        f"{summary['active_products']} sản phẩm đang hoạt động. Danh mục trợ lý kiểm tra "
                        "chưa đầy đủ nên chưa thể kết luận không có kết quả; hãy xem toàn bộ danh sách Sản phẩm."
                    )
                return (
                    "No active catalog item matches that stock query."
                    if english else "Không có sản phẩm đang hoạt động khớp từ khóa tồn kho này."
                )
            shown_products = products[:10]
            rows = "; ".join(
                f"{item['name']}: {item['stock_qty']} left (reorder at {item['reorder_level']})"
                if english else
                f"{item['name']} còn {item['stock_qty']} (ngưỡng bổ sung {item['reorder_level']})"
                for item in shown_products
            )
            count_note = _preview_note(len(products), len(shown_products), locale)
            if incomplete:
                count_note = (
                    f" (at least {len(products)} matches in the first "
                    f"{len(context.get('products', []))} products; more may match)"
                    if english else
                    f" (ít nhất {len(products)} kết quả trong {len(context.get('products', []))} sản phẩm đầu tiên; có thể còn kết quả khác)"
                )
            return (
                f"Stock for {len(products)} matching product(s){count_note}: {rows}."
                if english else f"Tồn kho của {len(products)} sản phẩm khớp từ khóa{count_note}: {rows}."
            )
    if stock_intent:
        if not low_stock_count:
            if english:
                return (
                    f"There are {summary['active_products']} active products; none has reached "
                    "its configured reorder level."
                )
            return (
                f"Cửa hàng có {summary['active_products']} sản phẩm đang hoạt động; "
                "chưa có sản phẩm nào chạm ngưỡng bổ sung riêng đã cài đặt."
            )
        shown_stock = context["low_stock"][:12]
        if english:
            rows = "; ".join(
                f"{item['name']}: {item['stock_qty']} left (code {item['code']})"
                for item in shown_stock
            )
        else:
            rows = "; ".join(
                f"{item['name']} còn {item['stock_qty']} (mã {item['code']})"
                for item in shown_stock
            )
        if english:
            phrase = _counted(low_stock_count, "product")
            verb = " is" if low_stock_count == 1 else " are"
            return (
                f"{phrase}{verb} at or below the reorder level"
                f"{_preview_note(low_stock_count, len(shown_stock), locale)}: {rows}."
            )
        return (
            f"Có {low_stock_count} sản phẩm ở ngưỡng tồn thấp"
            f"{_preview_note(low_stock_count, len(shown_stock))}: {rows}."
        )
    if _product_intent(query, question):
        products, narrowed = _product_search(question, context)
        incomplete = _catalog_preview_truncated(context, "products")
        if not products:
            if narrowed and incomplete:
                scanned = len(context.get("products", []))
                if english:
                    return (
                        f"No matching product appeared in the first {scanned} of "
                        f"{summary['active_products']} active products. The catalog preview is limited, "
                        "so I can't rule out matches outside it. Check the full Products list or refine the search."
                    )
                return (
                    f"Chưa thấy sản phẩm khớp trong {scanned} sản phẩm đầu tiên trên tổng số "
                    f"{summary['active_products']} sản phẩm đang hoạt động. Danh mục trợ lý kiểm tra "
                    "chưa đầy đủ nên chưa thể kết luận không có kết quả; hãy xem toàn bộ danh sách "
                    "Sản phẩm hoặc thu hẹp từ khóa."
                )
            return "There are no active products in the catalog." if english else "Hiện chưa có sản phẩm nào đang hoạt động trong danh mục."
        shown_products = products[:10] if narrowed else products[:20]
        if english:
            rows = "; ".join(
                f"{item['name']} ({item['category']}, stock {item['stock_qty']}, "
                f"price {_money(item['unit_price'], currency_code, locale)})"
                for item in shown_products
            )
        else:
            rows = "; ".join(
                f"{item['name']} ({item['category']}, tồn {item['stock_qty']}, "
                f"giá {_money(item['unit_price'], currency_code)})"
                for item in shown_products
            )
        total = len(products) if narrowed else summary["active_products"]
        if english:
            if narrowed and incomplete:
                return (
                    f"At least {total} matching product(s) appeared in the first "
                    f"{len(context.get('products', []))} products; the full matching count may be higher. "
                    f"Showing {len(shown_products)}: {rows}."
                )
            phrase = _counted(total, "product") + (" is" if total == 1 else " are")
            return f"{phrase} active{_preview_note(total, len(shown_products), locale)}: {rows}."
        if narrowed and incomplete:
            return (
                f"Trong phần xem trước có ít nhất {total} sản phẩm khớp; trợ lý đã kiểm tra "
                f"{len(context.get('products', []))} sản phẩm đầu tiên trên tổng số "
                f"{summary['active_products']} sản phẩm đang hoạt động. Tổng số khớp có thể cao hơn. "
                f"Đang hiển thị {len(shown_products)} mục: {rows}."
            )
        return (
            f"Có {total} sản phẩm đang hoạt động"
            f"{_preview_note(total, len(shown_products))}: {rows}."
        )
    if any(word in query for word in ("khach hang", "khach mua", "customer", "buyer", "client")):
        if english:
            return f"There are {_counted(summary['active_customers'], 'active customer')}."
        return f"Cửa hàng hiện có {summary['active_customers']} khách hàng đang hoạt động."
    if any(word in query for word in ("thanh toan", "hoa don", "ban hang", "lap hoa don", "invoice", "payment", "checkout", "sell")):
        if english:
            return (
                "Create an invoice from Invoices. A new invoice does not change stock; "
                "inventory and pet sale status update only after payment is confirmed."
            )
        return (
            "Bạn có thể lập hóa đơn từ mục Hóa đơn. Hóa đơn mới chưa trừ tồn; "
            "chỉ khi xác nhận thanh toán, hệ thống mới cập nhật kho và đánh dấu thú cưng đã bán."
        )
    if any(phrase in query for phrase in ("tong quan", "tat ca", "so luoc", "cua hang co gi", "overview", "summary", "everything", "store")):
        if english:
            customers = _counted(summary['active_customers'], "active customer")
            products = _counted(summary['active_products'], "active product")
            pets = _counted(summary['available_pets'], "available pet")
            low_stock = _counted(low_stock_count, "product")
            return (
                f"Store overview: {customers}, {products}, {pets}, "
                f"and {low_stock} at low stock. Today's paid revenue is "
                f"{_money(summary['revenue_today'], currency_code, locale)}. "
                "These figures are for the selected store. Ask about any item for more detail."
            )
        return (
            f"Tổng quan cửa hàng: {summary['active_customers']} khách hàng đang hoạt động, "
            f"{summary['active_products']} sản phẩm đang bán, "
            f"{summary['available_pets']} thú cưng sẵn sàng bán và "
            f"{low_stock_count} sản phẩm ở ngưỡng tồn thấp. "
            f"Doanh thu đã thanh toán hôm nay là {_money(summary['revenue_today'], currency_code)}. "
            "Số liệu thuộc cửa hàng đang chọn; bạn có thể hỏi riêng từng mục để xem chi tiết."
        )
    if english:
        return (
            "I can check your store overview, today's paid revenue, low-stock products, "
            "the product catalog, pets for sale, and invoice steps. What would you like to check?"
        )
    return (
        "Mình có thể tra cứu tổng quan cửa hàng, doanh thu hôm nay (hóa đơn đã thanh toán), "
        "sản phẩm tồn thấp, danh mục sản phẩm, thú cưng đang bán và hướng dẫn lập hóa đơn. "
        "Bạn muốn kiểm tra mục nào?"
    )
