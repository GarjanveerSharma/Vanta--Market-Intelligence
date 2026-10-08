import pytest

from advisor.templates import explain_event


def test_template_explanation_includes_regime_context():
    explanation = explain_event("breakout", "HIGH_VOLATILITY")

    assert "resistance" in explanation
    assert "Volatility is elevated" in explanation


def test_template_rejects_unknown_event_type():
    with pytest.raises(ValueError, match="Unsupported event type"):
        explain_event("unknown")
