import pytest

from src.fmt import AmountError, inr, inr_short, parse_amount, pct, validate_amount


@pytest.mark.parametrize("x,expected", [
    (0, "₹0"), (999, "₹999"), (1000, "₹1,000"), (15_00_000, "₹15,00,000"),
    (1_00_00_000, "₹1,00,00,000"), (123_45_67_890, "₹1,23,45,67,890"), (-25_000, "−₹25,000"),
    (1499999.6, "₹15,00,000"),
])
def test_inr(x, expected):
    assert inr(x) == expected


def test_inr_decimals():
    assert inr(1234.5, 2) == "₹1,234.50"
    assert inr(999.999, 2) == "₹1,000.00"


@pytest.mark.parametrize("x,expected", [
    (15_00_000, "₹15 lakh"), (1_25_000, "₹1.25 lakh"), (1_20_00_000, "₹1.2 crore"),
    (75_000, "₹75,000"), (1_00_00_000, "₹1 crore"), (-2_50_000, "−₹2.5 lakh"),
])
def test_inr_short(x, expected):
    assert inr_short(x) == expected


@pytest.mark.parametrize("text,value", [
    ("15,00,000", 15_00_000), ("1500000", 15_00_000), ("15 lakh", 15_00_000), ("15L", 15_00_000),
    ("15 lakhs", 15_00_000), ("1.5 crore", 1_50_00_000), ("1.5cr", 1_50_00_000), ("1.5 Cr", 1_50_00_000),
    ("₹ 15,00,000", 15_00_000), ("Rs 2,50,000", 2_50_000), ("Rs. 2.5 lakh", 2_50_000), ("50k", 50_000),
    ("1,500,000", 15_00_000), (1500000, 15_00_000), ("10 lac", 10_00_000),
])
def test_parse_amount(text, value):
    assert parse_amount(text) == pytest.approx(value)


@pytest.mark.parametrize("bad", ["", "abc", "15 bananas", "-5", "0", "1.2.3", None])
def test_parse_amount_rejects_with_plain_message(bad):
    with pytest.raises(AmountError) as e:
        parse_amount(bad)
    assert len(str(e.value)) > 10


def test_validate_amount():
    assert validate_amount(15_00_000, 10_000, 100_00_00_000) is None
    assert "smallest" in validate_amount(5_000, 10_000, 100_00_00_000)
    assert "largest" in validate_amount(200_00_00_000, 10_000, 100_00_00_000)


def test_pct():
    assert pct(0.0532) == "5.3%"
    assert pct(-0.25, 0, sign=True) == "−25%"
