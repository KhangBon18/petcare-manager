from petcare.database.connection import read_connection, transaction
from petcare.repositories import audit_repo, customer_repo
from petcare.repositories.base import fetch_one
from petcare.services.common import page_window, phone_value, positive_id, require_actor, text_value
from petcare.services.exceptions import NotFoundError, ValidationError


def list_customers(actor_id, search="", include_inactive=False, page=None):
    search = (search or "").strip()[:120]
    with read_connection() as connection:
        require_actor(connection, actor_id)
        if page is not None:
            total = customer_repo.count_customers(connection, search, include_inactive)
            _current_page, offset, pagination = page_window(page, total)
            return {
                "items": customer_repo.list_customers_page(
                    connection, search, include_inactive, pagination["page_size"], offset
                ),
                "pagination": pagination,
            }
        return customer_repo.list_customers(
            connection, search, include_inactive
        )


def get_customer(actor_id, customer_id):
    customer_id = positive_id(customer_id, "Khách hàng")
    with read_connection() as connection:
        require_actor(connection, actor_id)
        customer = customer_repo.get_customer(connection, customer_id)
    if not customer:
        raise NotFoundError("Không tìm thấy khách hàng.")
    return customer


def get_customer_profile(actor_id, customer_id, page="1"):
    customer_id = positive_id(customer_id, "Khách hàng")
    with read_connection() as connection:
        require_actor(connection, actor_id)
        customer = customer_repo.get_customer(connection, customer_id)
        if not customer:
            raise NotFoundError("Không tìm thấy khách hàng.")
        total = customer_repo.count_customer_invoices(connection, customer_id)
        _current_page, offset, pagination = page_window(page, total)
        currencies = customer_repo.summarize_customer_invoices(connection, customer_id)
        invoices = customer_repo.list_customer_invoices_page(
            connection, customer_id, pagination["page_size"], offset
        )

    summary = {
        "invoice_count": sum(int(row["invoice_count"] or 0) for row in currencies),
        "paid_invoice_count": sum(
            int(row["paid_invoice_count"] or 0) for row in currencies
        ),
        "unpaid_invoice_count": sum(
            int(row["unpaid_invoice_count"] or 0) for row in currencies
        ),
        "currencies": currencies,
    }
    return {
        "customer": customer,
        "summary": summary,
        "invoices": invoices,
        "pagination": pagination,
    }


def _customer_data(data):
    values, errors = {}, {}
    validators = {
        "full_name": lambda value: text_value(value, "Họ tên", 160),
        "phone": phone_value,
        "address": lambda value: text_value(value, "Địa chỉ", 255, required=False),
    }
    for field, validate in validators.items():
        try:
            values[field] = validate(data.get(field))
        except ValidationError as exc:
            errors[field] = str(exc)
    if errors:
        raise ValidationError(next(iter(errors.values())), field_errors=errors)
    return values["full_name"], values["phone"], values["address"]


def create_customer(actor_id, data):
    full_name, phone, address = _customer_data(data)
    with transaction() as connection:
        require_actor(connection, actor_id)
        customer_id = customer_repo.create_customer(connection, full_name, phone, address)
        audit_repo.add_event(
            connection, actor_id, "customer.created", "customer", customer_id,
            f"Tạo hồ sơ khách hàng #{customer_id}",
        )
        return customer_id


def update_customer(actor_id, customer_id, data):
    customer_id = positive_id(customer_id, "Khách hàng")
    full_name, phone, address = _customer_data(data)
    with transaction() as connection:
        require_actor(connection, actor_id)
        current = customer_repo.get_customer(connection, customer_id)
        if not current:
            raise NotFoundError("Không tìm thấy khách hàng.")
        changed_fields = [
            field for field, old, new in (
                ("full_name", current["full_name"], full_name),
                ("phone", current["phone"], phone),
                ("address", current["address"], address),
            ) if old != new
        ]
        if customer_repo.update_customer(connection, customer_id, full_name, phone, address):
            audit_repo.add_event(
                connection, actor_id, "customer.updated", "customer", customer_id,
                f"Cập nhật hồ sơ khách hàng #{customer_id}",
                {"changed_fields": changed_fields},
            )


def set_active(actor_id, customer_id, active):
    customer_id = positive_id(customer_id, "Khách hàng")
    with transaction() as connection:
        require_actor(connection, actor_id)
        customer = customer_repo.get_customer(connection, customer_id)
        if not customer:
            raise NotFoundError("Không tìm thấy khách hàng.")
        if bool(customer["active"]) == bool(active):
            return
        changed = customer_repo.set_active(connection, customer_id, int(bool(active)))
        if not changed:
            raise NotFoundError("Không tìm thấy khách hàng.")
        audit_repo.add_event(
            connection, actor_id, "customer.status_changed", "customer", customer_id,
            f"{'Kích hoạt' if active else 'Ngừng sử dụng'} khách hàng #{customer_id}",
            {"active": bool(active)},
        )
