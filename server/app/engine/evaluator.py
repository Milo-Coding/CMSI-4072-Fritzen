"""
Hand Evaluator Module - Poker hand evaluation logic
Provides functions to evaluate poker hands, compare them,
and convert hand rankings to human-readable formats.
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
    
    Preserved all original logic including Ace-low straight handling.
    
    Args:
        five_cards: Exactly 5 cards to evaluate
        
    Returns:
        tuple: (hand_rank, ordered_values) where ordered_values are kickers
    """
    values = sorted([c.value for c in five_cards], reverse=True)
    suits = [c.suit for c in five_cards]
    counts = {v: values.count(v) for v in set(values)}
    is_flush = len(set(suits)) == 1
    unique_vals = sorted(set(values), reverse=True)

    # Straight detection including Ace-low (A-2-3-4-5)
    is_straight = False
    if len(unique_vals) == 5:
        if max(unique_vals) - min(unique_vals) == 4:
            is_straight = True
        elif set(unique_vals) == {14, 2, 3, 4, 5}:
            is_straight = True
            # For Ace-low straight, treat Ace as 1 for kicker ordering
            values = [5, 4, 3, 2, 1]

    # Frequency patterns
    freq_sorted = sorted(((cnt, val) for val, cnt in counts.items()), reverse=True)
    # Build kicker ordering by frequency then value
    ordered_vals = []
    for cnt, val in freq_sorted:
        ordered_vals.extend([val] * cnt)

    # Hand ranking checks (in order of strength)
    if is_flush and is_straight:
        return (HandRank.STRAIGHT_FLUSH, ordered_vals)
    if 4 in counts.values():
        return (HandRank.FOUR_KIND, ordered_vals)
    if sorted(counts.values()) == [2, 3]:
        return (HandRank.FULL_HOUSE, ordered_vals)
    if is_flush:
        return (HandRank.FLUSH, values)
    if is_straight:
        return (HandRank.STRAIGHT, values)
    if 3 in counts.values():
        return (HandRank.THREE_KIND, ordered_vals)
    if list(counts.values()).count(2) == 2:
        return (HandRank.TWO_PAIR, ordered_vals)
    if 2 in counts.values():
        return (HandRank.PAIR, ordered_vals)
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
    Convert hand evaluation to readable string.
    
    Args:
        hand_eval: Tuple of (rank, kickers)
        
    Returns:
        str: Human-readable hand description
    """
    rank, kickers = hand_eval
    return f"{get_hand_name(rank)} ({', '.join(str(k) for k in kickers[:3])})"
