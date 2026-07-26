"""Acceptance contract for persistent, uncertainty-aware opponent profiles."""

from __future__ import annotations

import pytest

profile_module = pytest.importorskip(
    "app.engine.opponents.profile",
    reason="OpponentProfile has not been implemented",
)
OpponentProfile = profile_module.OpponentProfile

pytestmark = pytest.mark.future_requirement


def test_profile_begins_with_finite_population_prior() -> None:
    profile = OpponentProfile(player_id="villain")

    vpip = profile.estimate("vpip")

    assert 0.0 < vpip.mean < 1.0
    assert vpip.opportunities == 0
    assert vpip.uncertainty > 0.0


def test_profile_updates_only_when_an_opportunity_exists() -> None:
    profile = OpponentProfile(player_id="villain")

    profile.observe(
        statistic="fold_to_flop_bet",
        occurred=True,
        opportunity=False,
        context={"street": "Flop", "facing_bet_fraction": 0.5},
    )

    assert profile.estimate("fold_to_flop_bet").opportunities == 0


def test_profile_posterior_moves_toward_repeated_observations() -> None:
    profile = OpponentProfile(player_id="villain")
    prior = profile.estimate("fold_to_flop_bet")

    for _ in range(20):
        profile.observe(
            statistic="fold_to_flop_bet",
            occurred=True,
            opportunity=True,
            context={"street": "Flop", "facing_bet_fraction": 0.75},
        )

    posterior = profile.estimate(
        "fold_to_flop_bet",
        context={"street": "Flop", "facing_bet_fraction": 0.75},
    )
    assert posterior.mean > prior.mean
    assert posterior.uncertainty < prior.uncertainty
    assert posterior.opportunities == 20


def test_profiles_do_not_mix_player_identities() -> None:
    folder = OpponentProfile(player_id="folder")
    caller = OpponentProfile(player_id="caller")

    for _ in range(15):
        folder.observe("fold_to_bet", True, True, {"street": "Turn"})
        caller.observe("fold_to_bet", False, True, {"street": "Turn"})

    assert (
        folder.estimate("fold_to_bet", {"street": "Turn"}).mean
        > caller.estimate("fold_to_bet", {"street": "Turn"}).mean
    )


def test_profile_serialization_round_trip_preserves_posterior() -> None:
    profile = OpponentProfile(player_id="villain")
    for occurred in [True, False, True, True]:
        profile.observe("river_bet", occurred, True, {"position": "late"})

    restored = OpponentProfile.from_dict(profile.to_dict())

    assert restored.player_id == profile.player_id
    assert restored.estimate("river_bet", {"position": "late"}) == profile.estimate(
        "river_bet", {"position": "late"}
    )


def test_contexts_remain_distinct() -> None:
    profile = OpponentProfile(player_id="villain")
    for _ in range(12):
        profile.observe("fold_to_bet", True, True, {"street": "Flop"})
        profile.observe("fold_to_bet", False, True, {"street": "River"})

    flop = profile.estimate("fold_to_bet", {"street": "Flop"})
    river = profile.estimate("fold_to_bet", {"street": "River"})
    assert flop.mean > river.mean
