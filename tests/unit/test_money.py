import unittest
from decimal import Decimal

from petcare.money import (
    CurrencyError,
    currency_options,
    currency_precision,
    currency_step,
    format_money,
    money_input_value,
    normalize_currency_code,
    parse_money,
)
from petcare.services.exceptions import ValidationError
from petcare.services.common import money_value


class CurrencyTests(unittest.TestCase):
    def test_supported_current_tender_currencies_are_available_for_signup(self):
        options = currency_options("en")
        codes = {item["code"] for item in options}
        self.assertIn("USD", codes)
        self.assertIn("VND", codes)
        self.assertEqual(currency_precision("VND"), 0)
        self.assertEqual(currency_precision("JPY"), 0)
        self.assertEqual(currency_precision("USD"), 2)
        self.assertEqual(currency_precision("KWD"), 3)

    def test_normalizes_code_and_rejects_unknown_and_historical_codes(self):
        self.assertEqual(normalize_currency_code(" usd "), "USD")
        for code in ("US", "XYZ", "VEF", "USDT"):
            with self.subTest(code=code), self.assertRaises(CurrencyError):
                normalize_currency_code(code)

    def test_parses_exact_currency_precision_without_float_rounding(self):
        self.assertEqual(parse_money("12.34", "USD"), Decimal("12.34"))
        self.assertEqual(parse_money("1.234", "KWD"), Decimal("1.234"))
        self.assertEqual(parse_money("123", "JPY"), Decimal("123"))
        with self.assertRaises(ValueError):
            parse_money("1.001", "USD")
        with self.assertRaises(ValueError):
            parse_money("-1", "USD")

    def test_html_money_inputs_use_currency_precision_and_native_steps(self):
        self.assertEqual(money_input_value(Decimal("2400000.0000"), "VND"), "2400000")
        self.assertEqual(money_input_value(Decimal("12.3400"), "USD"), "12.34")
        self.assertEqual(money_input_value(Decimal("12.3450"), "KWD"), "12.345")
        self.assertEqual(currency_step("JPY"), "1")
        self.assertEqual(currency_step("USD"), "0.01")
        self.assertEqual(currency_step("KWD"), "0.001")
        with self.assertRaisesRegex(ValueError, "USD"):
            money_input_value(Decimal("12.345"), "USD")

    def test_service_validation_and_locale_format_include_unambiguous_currency_code(self):
        self.assertEqual(money_value("5.10", "Price", "USD"), Decimal("5.10"))
        with self.assertRaises(ValidationError):
            money_value("5.101", "Price", "USD")
        self.assertIn("USD", format_money(Decimal("1234.50"), "USD"))
        self.assertIn("VND", format_money(1234, "VND"))


if __name__ == "__main__":
    unittest.main()
