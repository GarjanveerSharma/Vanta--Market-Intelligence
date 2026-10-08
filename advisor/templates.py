from __future__ import annotations

from advisor.prompts import EVENT_EXPLANATIONS

REGIME_EXPLANATIONS = {
    "TRENDING_UP": " The broader market is trending upward.",
    "TRENDING_DOWN": " The broader market is trending downward.",
    "SIDEWAYS": " The broader market is moving sideways.",
    "HIGH_VOLATILITY": " Volatility is elevated, so price moves and stop distances may be larger.",
}


def explain_event(event_type: str, regime: str = "SIDEWAYS") -> str:
    try:
        explanation = EVENT_EXPLANATIONS[event_type]
    except KeyError as error:
        raise ValueError(f"Unsupported event type: {event_type}") from error
    return explanation + REGIME_EXPLANATIONS.get(regime, "")
