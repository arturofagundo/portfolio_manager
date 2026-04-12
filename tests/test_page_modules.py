import importlib
import sys
import types
from pathlib import Path

import numpy as np
import polars as pl
import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


class DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def title(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def header(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        return None

    def divider(self, *args, **kwargs):
        return None

    def dataframe(self, *args, **kwargs):
        return None

    def altair_chart(self, *args, **kwargs):
        return None

    def metric(self, *args, **kwargs):
        return None

    def text_input(self, label, value="", **kwargs):
        return value

    def selectbox(self, label, options, index=0, **kwargs):
        return options[index] if options else ""

    def number_input(self, *args, value=0.0, **kwargs):
        return value

    def slider(self, *args, value=0.0, min_value=0.0, max_value=1.0, **kwargs):
        return value

    def toggle(self, *args, value=False, **kwargs):
        return value

    def form_submit_button(self, *args, **kwargs):
        return False

    def form(self, *args, **kwargs):
        return DummyContainer()

    def expander(self, *args, **kwargs):
        return DummyContainer()

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [DummyContainer() for _ in range(count)]

    def tabs(self, labels, **kwargs):
        return [DummyContainer() for _ in labels]

    def button(self, *args, **kwargs):
        return False


class DummyStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}

    def __getattr__(self, name):
        if hasattr(DummyContainer, name):
            return getattr(DummyContainer(), name)
        raise AttributeError(name)


def _patch_streamlit(monkeypatch):
    dummy_st = DummyStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", dummy_st)
    return dummy_st


def _patch_required_modules(monkeypatch):
    if "cvxpy" not in sys.modules:
        monkeypatch.setitem(sys.modules, "cvxpy", types.ModuleType("cvxpy"))
    if "pypfopt" not in sys.modules:
        pypfopt = types.ModuleType("pypfopt")
        pypfopt.EfficientFrontier = lambda mu, cov: None
        pypfopt.risk_models = types.SimpleNamespace(
            corr_to_cov=lambda corr, sigmas: np.zeros((len(sigmas), len(sigmas)))
        )
        monkeypatch.setitem(sys.modules, "pypfopt", pypfopt)
    if "altair" not in sys.modules:
        altair = types.ModuleType("altair")
        altair.Chart = lambda *args, **kwargs: DummyContainer()
        altair.Theta = lambda *args, **kwargs: None
        altair.Color = lambda *args, **kwargs: None
        altair.Legend = lambda *args, **kwargs: None
        altair.X = lambda *args, **kwargs: None
        altair.Y = lambda *args, **kwargs: None
        altair.Column = lambda *args, **kwargs: None
        altair.Header = lambda *args, **kwargs: None
        altair.mark_bar = lambda *args, **kwargs: DummyContainer()
        monkeypatch.setitem(sys.modules, "altair", altair)


def _patch_data_utils(monkeypatch):
    import data_utils

    monkeypatch.setattr(data_utils, "load_fund_info", lambda: {})
    monkeypatch.setattr(data_utils, "get_all_holdings", lambda: (pl.DataFrame(), {}))
    monkeypatch.setattr(data_utils, "get_all_available_funds", lambda: {})
    monkeypatch.setattr(data_utils, "save_fund_info", lambda *_args, **_kwargs: None)


def _import_page_module(module_name: str, monkeypatch):
    monkeypatch.syspath_prepend(str(SRC_DIR))
    _patch_streamlit(monkeypatch)
    _patch_required_modules(monkeypatch)
    _patch_data_utils(monkeypatch)
    sys.modules.pop(f"pages.{module_name}", None)
    return importlib.import_module(f"pages.{module_name}")


def test_get_current_allocation_computes_weights(monkeypatch):
    module = _import_page_module("allocation_sandbox", monkeypatch)
    combined_df = pl.DataFrame(
        {
            "asset_class": ["Equity", "Bond", "Equity"],
            "value": [100.0, 200.0, 300.0],
        }
    )
    result = module.get_current_allocation(combined_df, ["Equity", "Bond", "Cash"])

    assert result["Equity"] == pytest.approx(0.6666666666666666)
    assert result["Bond"] == pytest.approx(0.3333333333333333)
    assert result["Cash"] == 0.0


def test_calculate_portfolio_metrics_returns_expected_values(monkeypatch):
    module = _import_page_module("portfolio_metrics", monkeypatch)

    combined_df = pl.DataFrame(
        {"asset_class": ["Stock", "Bond"], "value": [500.0, 500.0]}
    )
    returns_df = pl.DataFrame(
        {
            "Asset Class": ["Stock", "Bond"],
            "Expected Return": [0.10, 0.02],
            "Standard Deviation": [0.15, 0.05],
        }
    )
    correlation_df = pl.DataFrame(
        {
            "Asset Class": ["Stock", "Bond"],
            "Stock": [1.0, 0.2],
            "Bond": [0.2, 1.0],
        }
    )

    expected_return, std_dev = module.calculate_portfolio_metrics(
        combined_df, returns_df, correlation_df
    )

    assert expected_return == pytest.approx(0.06, rel=1e-6)
    assert std_dev == pytest.approx(0.083666, rel=1e-4)


def test_scrape_vanguard_composition_handles_http_errors(monkeypatch):
    module = _import_page_module("fund_details", monkeypatch)

    import requests

    class DummyResponse:
        status_code = 500

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: DummyResponse())

    result, error = module.scrape_vanguard_composition("https://example.com")
    assert result is None
    assert "Status 500" in error


def test_import_holdings_page_with_empty_data(monkeypatch):
    module = _import_page_module("holdings", monkeypatch)
    assert module is not None


def test_import_fund_details_page_with_empty_data(monkeypatch):
    module = _import_page_module("fund_details", monkeypatch)
    assert module is not None


def test_import_portfolio_metrics_page_with_empty_data(monkeypatch):
    module = _import_page_module("portfolio_metrics", monkeypatch)
    assert module is not None


def test_import_allocation_sandbox_page_with_empty_data(monkeypatch):
    module = _import_page_module("allocation_sandbox", monkeypatch)
    assert module is not None
