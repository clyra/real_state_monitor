import pytest

from real_estate_monitor.services.money_parser import parse_money
from real_estate_monitor.services.property_extractor import (
    extract_area,
    extract_bathrooms,
    extract_bedrooms,
    extract_parking,
)
from real_estate_monitor.services.text_utils import normalize_text, normalize_whitespace


class TestNormalizeText:
    def test_none_returns_empty(self):
        assert normalize_text(None) == ""

    def test_strips_extra_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_removes_non_ascii(self):
        assert normalize_text("caf\u00e9") == "cafe"

    def test_normalizes_newlines(self):
        assert normalize_text("hello\nworld\tfoo") == "hello world foo"


class TestNormalizeWhitespace:
    def test_collapses_spaces(self):
        assert normalize_whitespace("a   b  c") == "a b c"

    def test_strips_ends(self):
        assert normalize_whitespace("  hello  ") == "hello"


class TestParseMoney:
    def test_none_returns_none(self):
        assert parse_money(None) is None

    def test_brl_format(self):
        assert parse_money("R$ 1.500,00") == 1500.0

    def test_brl_no_cents(self):
        assert parse_money("R$ 2.000") == 2000.0

    def test_plain_number(self):
        assert parse_money("1500") == 1500.0

    def test_with_text(self):
        assert parse_money("Rent: R$ 3.200,50") == 3200.5

    def test_empty_string(self):
        assert parse_money("") is None


class TestPropertyExtractor:
    def test_extract_bedrooms(self):
        assert extract_bedrooms("3 bedrooms") == 3

    def test_extract_bedrooms_none(self):
        assert extract_bedrooms(None) is None

    def test_extract_bathrooms(self):
        assert extract_bathrooms("2 bath") == 2

    def test_extract_parking(self):
        assert extract_parking("1 garage") == 1

    def test_extract_area_float(self):
        assert extract_area("120,5 m2") == 120.5

    def test_extract_area_int(self):
        assert extract_area("85 m2") == 85.0

    def test_extract_area_none(self):
        assert extract_area(None) is None
