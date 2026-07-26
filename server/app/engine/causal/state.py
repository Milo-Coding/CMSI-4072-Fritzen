"""Immutable-enough causal state schema for action interventions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple


CardIdentity = Tuple[str, int]


def _card_identity(card: Any) -> CardIdentity:
    if isinstance(card, Mapping):
        return str(card["suit"]), int(card["value"])
    if isinstance(card, (list, tuple)) and len(card) == 2:
        return str(card[0]), int(card[1])
    if hasattr(card, "suit") and hasattr(card, "value"):
        return str(card.suit), int(card.value)
    raise ValueError(f"Unsupported card representation: {card!r}")


@dataclass(frozen=True)
class CausalPokerState:
    """All information held fixed while comparing legal hero interventions."""

    street: str
    hero_cards: Tuple[CardIdentity, ...]
    board: Tuple[CardIdentity, ...]
    pot: int
    hero_stack: int
    opponents: Tuple[Dict[str, Any], ...]
    amount_to_call: int
    legal_actions: Tuple[Dict[str, Any], ...]
    big_blind: int = 20
    current_table_bet: int = 0
    hero_current_bet: int = 0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CausalPokerState":
        hero_cards = tuple(_card_identity(card) for card in payload.get("hero_cards", []))
        board = tuple(_card_identity(card) for card in payload.get("board", []))
        all_visible = hero_cards + board
        if len(all_visible) != len(set(all_visible)):
            raise ValueError("Causal state contains duplicate visible cards")

        legal_actions = tuple(deepcopy(list(payload.get("legal_actions", []))))
        if not legal_actions:
            raise ValueError("At least one legal action is required")
        return cls(
            street=str(payload.get("street", "Pre-Flop")),
            hero_cards=hero_cards,
            board=board,
            pot=max(0, int(payload.get("pot", 0))),
            hero_stack=max(0, int(payload.get("hero_stack", 0))),
            opponents=tuple(deepcopy(list(payload.get("opponents", [])))),
            amount_to_call=max(0, int(payload.get("amount_to_call", 0))),
            legal_actions=legal_actions,
            big_blind=max(1, int(payload.get("big_blind", 20))),
            current_table_bet=max(0, int(payload.get("current_table_bet", 0))),
            hero_current_bet=max(0, int(payload.get("hero_current_bet", 0))),
        )

    @classmethod
    def from_game_state(
        cls,
        game_state: Mapping[str, Any],
        hero_cards: Sequence[Any],
        *,
        big_blind: int = 20,
    ) -> "CausalPokerState":
        agent_index = int(game_state.get("agent_index", 0))
        players = list(game_state.get("players", []))
        opponents = [
            {
                "player_id": player.get("player_id"),
                "stack": int(player.get("chips", 0)),
                "total_bet_in_hand": int(player.get("total_bet_in_hand", 0)),
                "is_playing_round": bool(player.get("is_playing_round", False)),
                "range": "all_legal_combinations",
            }
            for index, player in enumerate(players)
            if index != agent_index and player.get("is_playing_round", False)
        ]
        legal_actions: List[Dict[str, Any]] = []
        pot = int(game_state.get("pot", 0))
        current_bet = int(game_state.get("current_table_bet", 0))
        hero_current_bet = (
            int(players[agent_index].get("current_bet_in_round", 0))
            if 0 <= agent_index < len(players)
            else 0
        )
        for action in game_state.get("available_actions", []):
            if action in {"bet", "raise"}:
                minimum = max(big_blind, current_bet + big_blind)
                legal_actions.append({"action": action, "amount": minimum})
                if pot > minimum:
                    legal_actions.append(
                        {
                            "action": action,
                            "amount": min(
                                hero_current_bet
                                + int(game_state.get("hero_stack", 0) or 0),
                                max(minimum, pot),
                            ),
                        }
                    )
            else:
                legal_actions.append({"action": action})
        return cls.from_dict(
            {
                "street": game_state.get("state_name", "Pre-Flop"),
                "hero_cards": list(hero_cards),
                "board": game_state.get("community_cards", []),
                "pot": pot,
                "hero_stack": game_state.get("hero_stack", 0),
                "opponents": opponents,
                "amount_to_call": game_state.get("call_amount", 0),
                "legal_actions": legal_actions,
                "big_blind": big_blind,
                "current_table_bet": current_bet,
                "hero_current_bet": hero_current_bet,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "street": self.street,
            "hero_cards": [list(card) for card in self.hero_cards],
            "board": [list(card) for card in self.board],
            "pot": self.pot,
            "hero_stack": self.hero_stack,
            "opponents": deepcopy(list(self.opponents)),
            "amount_to_call": self.amount_to_call,
            "legal_actions": deepcopy(list(self.legal_actions)),
            "big_blind": self.big_blind,
            "current_table_bet": self.current_table_bet,
            "hero_current_bet": self.hero_current_bet,
        }
