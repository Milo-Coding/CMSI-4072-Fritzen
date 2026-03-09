"""
Hand Evaluator Module - Poker hand evaluation logic
Provides functions to evaluate poker hands, compare them,
and convert hand rankings to human-readable formats.

Follows World Series of Poker (WSOP) tiebreaking rules:
- High Card: Compare all cards in descending order
- Pair: Compare pair value, then remaining cards in descending order  
- Two Pair: Compare higher pair, then lower pair, then kicker
- Three of a Kind: Compare triplet, then remaining cards in descending order
- Straight: Compare high card (A-2-3-4-5 straight has 5 as high card)
- Flush: Compare all cards in descending order
- Full House: Compare triplet value, then pair value
- Four of a Kind: Compare quad value, then kicker
- Straight Flush: Compare high card of the straight
"""

from enum import IntEnum
from itertools import combinations
from typing import List, Tuple
from .card import Card


class HandRank(IntEnum):
    """
    Hand rankings for poker.
    
    ORIGINAL: HAND_RANKS dict from old code/game.py
    Converted to IntEnum for better type safety.
    """
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_KIND = 8
    STRAIGHT_FLUSH = 9


def evaluate_best_five(cards: List[Card]) -> Tuple[int, List[int]]:
    """
    Evaluate all possible 5-card combinations and return the best hand.
    
    Args:
        cards: List of 5-7 cards to evaluate
        
    Returns:
        tuple: (hand_rank, kicker_values) - Best possible hand rank and tiebreakers
    """
    best = None
    for combo in combinations(cards, 5):
        rank = evaluate_five(combo)
        if best is None or rank > best:
            best = rank
    return best


def evaluate_five(five_cards: Tuple[Card, ...]) -> Tuple[int, List[int]]:
    """
    Evaluate exactly 5 cards and return hand rank with kickers.
        
    Args:
        five_cards: Exactly 5 cards to evaluate
        
    Returns:
        tuple: (hand_rank, ordered_values) where ordered_values follow WSOP tiebreak rules
    """
    values = sorted([c.value for c in five_cards], reverse=True)
    suits = [c.suit for c in five_cards]
    counts = {v: values.count(v) for v in set(values)}
    is_flush = len(set(suits)) == 1
    unique_vals = sorted(set(values), reverse=True)

    # Straight detection including Ace-low (A-2-3-4-5)
    is_straight = False
    straight_high = 0
    if len(unique_vals) == 5:
        if max(unique_vals) - min(unique_vals) == 4:
            is_straight = True
            straight_high = max(unique_vals)
        elif set(unique_vals) == {14, 2, 3, 4, 5}:
            is_straight = True
            straight_high = 5  # Ace-low straight, 5 is the high card

    # Hand ranking checks with WSOP tiebreaking rules
    if is_flush and is_straight:
        return (HandRank.STRAIGHT_FLUSH, [straight_high])
    
    if 4 in counts.values():
        # Four of a Kind: quad value, then kicker
        quad_val = [v for v, c in counts.items() if c == 4][0]
        kicker = [v for v, c in counts.items() if c == 1][0]
        return (HandRank.FOUR_KIND, [quad_val, kicker])
    
    if sorted(counts.values()) == [2, 3]:
        # Full House: triplet value, then pair value
        triplet_val = [v for v, c in counts.items() if c == 3][0]
        pair_val = [v for v, c in counts.items() if c == 2][0]
        return (HandRank.FULL_HOUSE, [triplet_val, pair_val])
    
    if is_flush:
        # Flush: all cards in descending order
        return (HandRank.FLUSH, values)
    
    if is_straight:
        # Straight: high card value (5 for ace-low)
        return (HandRank.STRAIGHT, [straight_high])
    
    if 3 in counts.values():
        # Three of a Kind: triplet value, then kickers in descending order
        triplet_val = [v for v, c in counts.items() if c == 3][0]
        kickers = sorted([v for v, c in counts.items() if c == 1], reverse=True)
        return (HandRank.THREE_KIND, [triplet_val] + kickers)
    
    if list(counts.values()).count(2) == 2:
        # Two Pair: higher pair, lower pair, then kicker
        pairs = sorted([v for v, c in counts.items() if c == 2], reverse=True)
        kicker = [v for v, c in counts.items() if c == 1][0]
        return (HandRank.TWO_PAIR, [pairs[0], pairs[1], kicker])
    
    if 2 in counts.values():
        # Pair: pair value, then kickers in descending order
        pair_val = [v for v, c in counts.items() if c == 2][0]
        kickers = sorted([v for v, c in counts.items() if c == 1], reverse=True)
        return (HandRank.PAIR, [pair_val] + kickers)
    
    # High Card: all cards in descending order
    return (HandRank.HIGH_CARD, values)


def compare_hands(hand1: Tuple[int, List[int]], hand2: Tuple[int, List[int]]) -> int:
    """
    Compare two evaluated hands.
    
    Args:
        hand1: First hand tuple (rank, kickers)
        hand2: Second hand tuple (rank, kickers)
        
    Returns:
        int: 1 if hand1 wins, -1 if hand2 wins, 0 if tie
    """
    if hand1 > hand2:
        return 1
    elif hand1 < hand2:
        return -1
    else:
        return 0


def get_hand_name(rank: int) -> str:
    """
    Get human-readable name for hand rank.
    
    Args:
        rank: HandRank value
        
    Returns:
        str: Name of the hand
    """
    names = {
        HandRank.HIGH_CARD: "High Card",
        HandRank.PAIR: "Pair",
        HandRank.TWO_PAIR: "Two Pair",
        HandRank.THREE_KIND: "Three of a Kind",
        HandRank.STRAIGHT: "Straight",
        HandRank.FLUSH: "Flush",
        HandRank.FULL_HOUSE: "Full House",
        HandRank.FOUR_KIND: "Four of a Kind",
        HandRank.STRAIGHT_FLUSH: "Straight Flush"
    }
    return names.get(rank, "Unknown")


def hand_to_string(hand_eval: Tuple[int, List[int]]) -> str:
    """
    Convert hand evaluation to readable string with WSOP tiebreaker info.
    
    Args:
        hand_eval: Tuple of (rank, kickers)
        
    Returns:
        str: Human-readable hand description with tiebreaker details
    """
    rank, kickers = hand_eval
    hand_name = get_hand_name(rank)
    
    if rank == HandRank.STRAIGHT_FLUSH or rank == HandRank.STRAIGHT:
        return f"{hand_name}, {kickers[0]} high"
    elif rank == HandRank.FOUR_KIND:
        return f"{hand_name}, {kickers[0]}s with {kickers[1]} kicker"
    elif rank == HandRank.FULL_HOUSE:
        return f"{hand_name}, {kickers[0]}s over {kickers[1]}s"
    elif rank == HandRank.THREE_KIND:
        return f"{hand_name}, {kickers[0]}s with {', '.join(str(k) for k in kickers[1:])}"
    elif rank == HandRank.TWO_PAIR:
        return f"{hand_name}, {kickers[0]}s and {kickers[1]}s with {kickers[2]} kicker"
    elif rank == HandRank.PAIR:
        return f"{hand_name} of {kickers[0]}s with {', '.join(str(k) for k in kickers[1:])}"
    else:  # HIGH_CARD or FLUSH
        return f"{hand_name}, {', '.join(str(k) for k in kickers[:3])} high"
