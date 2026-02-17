"""
Test chip conservation and side pot distribution

Ensures that no chips are lost during pot distribution.
"""

import pytest
from app.engine import Card, Player, Game, GameEventType
from app.engine.game import GamePhase


def test_chip_conservation_no_all_in():
    """
    Test that chips are conserved when there's no all-in (no side pots needed).
    
    Scenario:
    - 3 players, each with 1000 chips
    - Normal betting, no all-ins
    - Total chips should remain 3000
    """
    players = [
        Player(chips=1000, name="Player1", player_id="p1"),
        Player(chips=1000, name="Player2", player_id="p2"),
        Player(chips=1000, name="Player3", player_id="p3")
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    
    initial_total = sum(p.chips for p in players)
    assert initial_total == 3000
    
    game._prepare_new_hand()
    game._post_blinds()
    
    # Everyone calls 20
    for p in players:
        if p.current_bet_in_round < 20:
            contrib = p.do_call(20)
            game.pot += contrib
    
    # Check no side pots created (no one is all-in)
    game._calculate_side_pots()
    assert len(game.side_pots) == 0, "Should not create side pots when no all-ins"
    
    # Simulate showdown - P1 wins
    for p in players:
        p.hand = [Card("Hearts", 14), Card("Spades", 13)]  # Ace, King
    game.community_cards = [
        Card("Hearts", 12),   # Queen
        Card("Hearts", 11),   # Jack
        Card("Hearts", 10),
        Card("Clubs", 2),
        Card("Diamonds", 3)
    ]
    
    # Award using simple showdown (no side pots)
    game._showdown_simple()
    
    # Verify chips conserved
    final_total = sum(p.chips for p in players)
    assert final_total == initial_total, f"Chips lost! Started with {initial_total}, ended with {final_total}"


def test_chip_conservation_with_all_in():
    """
    Test that chips are conserved when there are all-ins and side pots.
    
    Scenario:
    - 3 players: 100, 500, 1000 chips
    - Player 1 all-in for 100
    - Players 2 and 3 bet more
    - Total chips should remain 1600
    """
    players = [
        Player(chips=100, name="ShortStack", player_id="p1"),
        Player(chips=500, name="MediumStack", player_id="p2"),
        Player(chips=1000, name="BigStack", player_id="p3")
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    
    initial_total = sum(p.chips for p in players)
    assert initial_total == 1600
    
    game._prepare_new_hand()
    game._post_blinds()
    
    # P1 all-in for 100
    players[0].do_all_in()
    game.pot += 100
    
    # P2 calls 100
    p2_contrib = players[1].do_call(100)
    game.pot += p2_contrib
    
    # P3 calls 100
    p3_contrib = players[2].do_call(100)
    game.pot += p3_contrib
    
    # Move to flop
    for p in players:
        p.reset_for_new_betting_round()
    
    # P2 bets 200, P3 calls
    p2_bet = players[1].do_bet(200)
    game.pot += p2_bet
    
    p3_call = players[2].do_call(200)
    game.pot += p3_call
    
    # Give everyone hands
    for p in players:
        p.hand = [Card("Hearts", 14), Card("Spades", 13)]  # Ace, King
    
    game.community_cards = [
        Card("Hearts", 12),   # Queen
        Card("Hearts", 11),   # Jack
        Card("Hearts", 10),
        Card("Clubs", 2),
        Card("Diamonds", 3)
    ]
    
    # Calculate side pots
    game._calculate_side_pots()
    assert len(game.side_pots) > 0, "Should create side pots when all-in"
    
    # Verify pot amounts add up correctly
    total_in_pots = sum(pot["amount"] for pot in game.side_pots)
    assert total_in_pots == game.pot, f"Pots don't add up: {total_in_pots} != {game.pot}"
    
    # Award pots
    game._award_pots()
    
    # Verify chips conserved
    final_total = sum(p.chips for p in players)
    assert final_total == initial_total, f"Chips lost! Started with {initial_total}, ended with {final_total}"


def test_chip_conservation_odd_split():
    """
    Test that remainder chips are properly distributed when pot doesn't divide evenly.
    
    Scenario:
    - 3 players tie with pot of 100
    - 100 / 3 = 33 remainder 1
    - Should distribute 34, 33, 33 (not lose the 1 chip)
    """
    players = [
        Player(chips=1000, name="Player1", player_id="p1"),
        Player(chips=1000, name="Player2", player_id="p2"),
        Player(chips=1000, name="Player3", player_id="p3")
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    
    initial_total = sum(p.chips for p in players)
    
    game._prepare_new_hand()
    
    # Simulate betting to get pot to 100 chips
    # Each player puts in about 33 chips
    for i, p in enumerate(players):
        amount = 33 if i < 2 else 34  # Last player puts in 34 to make 100 total
        p._remove_chips(amount)
        p.total_bet_in_hand = amount
    game.pot = 100
    
    # All players have same hand (tie)
    for p in players:
        p.hand = [Card("Hearts", 14), Card("Spades", 13)]  # Ace, King
        p.is_playing_round = True
    
    game.community_cards = [
        Card("Hearts", 12),   # Queen
        Card("Hearts", 11),   # Jack
        Card("Hearts", 10),
        Card("Clubs", 2),
        Card("Diamonds", 3)
    ]
    
    # Award pot (should handle remainder)
    game._showdown_simple()
    
    # Verify chips conserved
    final_total = sum(p.chips for p in players)
    assert final_total == initial_total, f"Chips lost! Started with {initial_total}, ended with {final_total}"
    
    # Verify distribution (33, 33, 34 in some order due to remainder)
    # Players should get back their 100 chips from pot minus what they put in
    chip_changes = [p.chips - (1000 - p.total_bet_in_hand) for p in players]
    chip_changes.sort()
    # Winners get 33, 33, 34 from the 100 pot distribution
    assert chip_changes == [33, 33, 34], f"Incorrect distribution: {chip_changes}"


def test_six_player_game_chip_conservation():
    """
    Test that a 6-player game conserves all chips through multiple actions.
    
    This mirrors the user's reported issue.
    """
    players = [
        Player(chips=1000, name=f"Player{i}", player_id=f"p{i}")
        for i in range(1, 7)
    ]
    
    game = Game(players, small_blind=10, big_blind=20)
    
    initial_total = sum(p.chips for p in players)
    assert initial_total == 6000
    
    game._prepare_new_hand()
    game._post_blinds()
    
    # Everyone calls the big blind
    for p in players:
        if p.current_bet_in_round < 20:
            contrib = p.do_call(20)
            game.pot += contrib
    
    # Verify pot is correct
    assert game.pot == 120  # 20 from each of 6 players
    
    # Give everyone hands
    for p in players:
        p.hand = [Card("Hearts", 14), Card("Spades", 13)]  # Ace, King
    
    game.community_cards = [
        Card("Hearts", 12),   # Queen
        Card("Hearts", 11),   # Jack
        Card("Hearts", 10),
        Card("Clubs", 2),
        Card("Diamonds", 3)
    ]
    
    # Calculate side pots (should be none since no all-ins)
    game._calculate_side_pots()
    assert len(game.side_pots) == 0, "Should not create side pots without all-ins"
    
    # Award pot (everyone tied)
    game._showdown_simple()
    
    # Verify chips conserved
    final_total = sum(p.chips for p in players)
    assert final_total == initial_total, f"Chips lost! Started with {initial_total}, ended with {final_total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
