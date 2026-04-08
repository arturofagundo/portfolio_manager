import json
import os
from unittest.mock import mock_open, patch

import polars as pl

from src.data_utils import (
    FundInfo,
    clean_currency,
    get_all_available_funds,
    get_latest_file,
    load_fund_info,
    save_fund_info,
)


def test_clean_currency():
    # Test cleaning currency strings in a Polars Series
    df = pl.DataFrame({"price": ["$1,234.56", "- ", "($50.00)", "100.00"]})
    result = df.select(clean_currency(pl.col("price")).alias("cleaned"))

    assert result["cleaned"][0] == 1234.56
    assert result["cleaned"][1] == 0.0
    assert result["cleaned"][2] == 50.00
    assert result["cleaned"][3] == 100.00


def test_fund_info_serialization():
    # Test FundInfo to_dict and from_dict
    data = {"Symbol": "AAPL", "Asset Class": "Equity", "Composition": {"AAPL": 1.0}}
    info = FundInfo.from_dict(data)
    assert info.symbol == "AAPL"
    assert info.asset_class == "Equity"
    assert info.composition == {"AAPL": 1.0}

    assert info.to_dict() == data

    # Test default values
    info_empty = FundInfo.from_dict({})
    assert info_empty.symbol == ""
    assert info_empty.asset_class == "Other/Unclassified"
    assert info_empty.composition == {}


def test_get_latest_file(tmp_path):
    # Create dummy files
    d = tmp_path / "summaries"
    d.mkdir()
    (d / "2026-01-01_test.csv").write_text("data")
    (d / "2026-02-01_test.csv").write_text("data")

    latest = get_latest_file(str(d))
    assert os.path.basename(latest) == "2026-02-01_test.csv"


def test_load_fund_info_file_not_exists():
    with patch("os.path.exists", return_value=False):
        assert load_fund_info() == {}


def test_load_fund_info_success():
    mock_data = {"Fund A": {"Symbol": "A", "Asset Class": "Class A"}}
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            fund_map = load_fund_info()
            assert "Fund A" in fund_map
            assert fund_map["Fund A"].symbol == "A"


def test_save_fund_info():
    fund_map = {"Fund B": FundInfo(symbol="B", asset_class="Class B")}
    with patch("os.makedirs"):
        with patch("builtins.open", mock_open()) as mocked_file:
            save_fund_info(fund_map)
            # Verify json.dump was called
            handle = mocked_file()
            # Get all written content
            written = "".join(call.args[0] for call in handle.write.call_args_list)
            assert '"Symbol": "B"' in written


def test_get_all_available_funds_mocked(tmp_path):
    # Setup dummy directories and files
    summaries = tmp_path / "summaries"
    summaries.mkdir()
    (summaries / "data.csv").write_text("Fund name,Symbol\nMy Fund,MYF")

    # Patch glob and pl.read_csv to control behavior
    with patch("glob.glob", return_value=[str(summaries / "data.csv")]):
        # We need to ensure load_fund_info is also mocked to avoid file errors
        with patch("src.data_utils.load_fund_info", return_value={}):
            funds = get_all_available_funds()
            assert "My Fund" in funds
            assert funds["My Fund"] == "MYF"
