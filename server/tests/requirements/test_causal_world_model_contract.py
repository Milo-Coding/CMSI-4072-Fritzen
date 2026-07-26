"""Acceptance tests that distinguish causal action value from correlation."""

from __future__ import annotations

import pytest

causal_module = pytest.importorskip(
    "app.engine.causal.world_model",
    reason="Causal poker world model has not been implemented",
)
state_module = pytest.importorskip(
    "app.engine.causal.state",
    reason="Causal state schema has not been implemented",
)

PokerWorldModel = causal_module.PokerWorldModel
CausalPokerState = state_module.CausalPokerState

pytestmark = pytest.mark.future_requirement


@pytest.fixture
def river_nuts_state():
    """Hero cannot lose at showdown; folding remains causally worth zero."""
    return CausalPokerState.from_dict(
        {
            "street": "River",
            "hero_cards": [("Hearts", 14), ("Hearts", 13)],
            "board": [
                ("Hearts", 12),
                ("Hearts", 11),
                ("Hearts", 10),
                ("Clubs", 2),
                ("Diamonds", 3),
            ],
            "pot": 100,
            "hero_stack": 900,
            "opponents": [
                {
                    "player_id": "villain",
                    "stack": 900,
                    "range": "all_legal_combinations",
                }
            ],
            "amount_to_call": 0,
            "legal_actions": [
                {"action": "check"},
                {"action": "bet", "amount": 50},
                {"action": "fold"},
            ],
        }
    )


def test_intervention_does_not_mutate_pre_action_state(river_nuts_state) -> None:
    model = PokerWorldModel.deterministic_test_model(seed=7)
    before = river_nuts_state.to_dict()

    model.evaluate_intervention(
        river_nuts_state,
        action={"action": "bet", "amount": 50},
        rollouts=32,
    )

    assert river_nuts_state.to_dict() == before


def test_fold_has_zero_future_pot_share(river_nuts_state) -> None:
    model = PokerWorldModel.deterministic_test_model(seed=7)

    result = model.evaluate_intervention(
        river_nuts_state,
        action={"action": "fold"},
        rollouts=32,
    )

    assert result.expected_gross_pot_share == pytest.approx(0.0)
    assert result.probability_showdown == pytest.approx(0.0)


def test_known_nuts_showdown_equity_is_one(river_nuts_state) -> None:
    model = PokerWorldModel.deterministic_test_model(seed=7)

    result = model.evaluate_intervention(
        river_nuts_state,
        action={"action": "check"},
        rollouts=32,
    )

    assert result.showdown_equity == pytest.approx(1.0)
    assert result.expected_net_bb > 0.0


def test_same_exogenous_seed_produces_paired_counterfactuals(
    river_nuts_state,
) -> None:
    model = PokerWorldModel.deterministic_test_model(seed=31)

    first = model.evaluate_intervention(
        river_nuts_state,
        action={"action": "check"},
        rollouts=64,
        exogenous_seed=101,
    )
    second = model.evaluate_intervention(
        river_nuts_state,
        action={"action": "check"},
        rollouts=64,
        exogenous_seed=101,
    )

    assert first == second


def test_illegal_intervention_is_rejected(river_nuts_state) -> None:
    model = PokerWorldModel.deterministic_test_model(seed=7)

    with pytest.raises(ValueError, match="legal"):
        model.evaluate_intervention(
            river_nuts_state,
            action={"action": "raise", "amount": 10000},
            rollouts=8,
        )


def test_synthetic_confounding_prefers_interventional_value() -> None:
    """Raising may correlate with wins while causing lower EV in every stratum."""
    model = PokerWorldModel.synthetic_confounding_fixture(
        # Historical policy raises strong hands and checks weak hands. Within
        # either strength stratum, checking has the greater true causal value.
        observational_rows=[
            {"strength": "strong", "action": "raise", "net_bb": 8.0, "count": 900},
            {"strength": "strong", "action": "check", "net_bb": 10.0, "count": 100},
            {"strength": "weak", "action": "raise", "net_bb": -8.0, "count": 100},
            {"strength": "weak", "action": "check", "net_bb": -6.0, "count": 900},
        ]
    )

    effects = model.estimate_action_effects(context={"strength": "weak"})

    assert effects["check"].expected_net_bb > effects["raise"].expected_net_bb


def test_out_of_support_action_reports_uncertainty() -> None:
    model = PokerWorldModel.synthetic_confounding_fixture(
        observational_rows=[
            {"strength": "weak", "action": "check", "net_bb": -1.0, "count": 1000}
        ]
    )

    estimate = model.estimate_action_effects(context={"strength": "weak"})["raise"]

    assert estimate.out_of_support
    assert estimate.epistemic_uncertainty > 0.0
