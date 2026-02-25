"""
Simple tests to verify the poker engine works.

This demonstrates basic game flow using the game engine.
"""

import sys
sys.path.append('..')

from app.engine import Card, Deck, Player, Game, GameEventType


def test_basic_game():
    """Test a basic poker hand."""
    # Create players
    players = [
        Player(chips=1000, name="Alice", player_id="player_1"),
        Player(chips=1000, name="Bob", player_id="player_2"),
        Player(chips=1000, name="Charlie", player_id="player_3")
    ]
    
    # Create game
    game = Game(players=players, small_blind=10, big_blind=20)
    
    # Track events
    events = []
    
    def track_event(event_type):
        def handler(data):
            events.append({'type': event_type, 'data': data})
        return handler
    
    # Register event trackers
    game.on_event(GameEventType.HAND_STARTED, track_event('HAND_STARTED'))
    game.on_event(GameEventType.BLINDS_POSTED, track_event('BLINDS_POSTED'))
    game.on_event(GameEventType.HOLE_CARDS_DEALT, track_event('HOLE_CARDS_DEALT'))
    game.on_event(GameEventType.BETTING_ROUND_STARTED, track_event('BETTING_ROUND_STARTED'))
    game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_event('PLAYER_ACTION_TAKEN'))
    game.on_event(GameEventType.COMMUNITY_CARDS_DEALT, track_event('COMMUNITY_CARDS_DEALT'))
    game.on_event(GameEventType.POT_AWARDED, track_event('POT_AWARDED'))
    
    # Store initial chip counts
    initial_total = sum(p.chips for p in players)
    
    # Play one hand
    game.play_hand()
    
    # Verify chip conservation (total chips should remain constant)
    final_total = sum(p.chips for p in players)
    assert initial_total == final_total, "Total chips should be conserved"
    
    # Verify events were fired
    assert len(events) > 0, "Events should have been fired"
    assert any(e['type'] == 'HAND_STARTED' for e in events), "Hand should have started"
    assert any(e['type'] == 'BLINDS_POSTED' for e in events), "Blinds should have been posted"
    assert any(e['type'] == 'HOLE_CARDS_DEALT' for e in events), "Hole cards should have been dealt"
    
    # Verify game state serialization works
    state = game.get_state()
    assert 'players' in state
    assert 'pot' in state
    assert 'hand_number' in state
    assert len(state['players']) == 3


def test_card_and_deck():
    """Test Card and Deck classes."""
    # Test card creation
    card1 = Card("Hearts", 14)  # Ace of Hearts
    card2 = Card("Spades", 13)  # King of Spades
    
    # Test card string representation
    assert str(card1) == "A♥"
    assert str(card2) == "K♠"
    
    # Test card serialization
    card1_dict = card1.to_dict()
    assert card1_dict['suit'] == "Hearts"
    assert card1_dict['value'] == 14
    assert card1_dict['display'] == "A♥"
    
    # Test deck creation
    deck = Deck()
    assert len(deck) == 52, "Deck should have 52 cards"
    
    # Test deck shuffle
    deck.shuffle()
    assert len(deck) == 52, "Deck should still have 52 cards after shuffle"
    
    # Test dealing cards
    dealt = [deck.deal_card() for _ in range(5)]
    assert len(dealt) == 5, "Should deal 5 cards"
    assert all(isinstance(c, Card) for c in dealt), "All dealt items should be Cards"
    assert len(deck) == 47, "Deck should have 47 cards remaining"
    
    # Test deck serialization
    deck_dict = deck.to_dict()
    assert 'remaining' in deck_dict
    assert len(deck_dict['remaining']) == 47


def test_hand_evaluation():
    # TODO add tests for all hand types, not just a few examples
    # add tests for tie-breaking logic as well
    """Test hand evaluation."""
    from app.engine import evaluate_best_five, get_hand_name
    
    # Test royal flush / straight flush
    cards = [
        Card("Hearts", 10),
        Card("Hearts", 11),
        Card("Hearts", 12),
        Card("Spades", 2),
        Card("Hearts", 13),
        Card("Hearts", 14),
        Card("Clubs", 3)
    ]
    rank, kickers = evaluate_best_five(cards)
    hand_name = get_hand_name(rank)
    assert "Straight Flush" in hand_name or "Royal Flush" in hand_name, f"Expected straight/royal flush, got {hand_name}"
    assert rank >= 8, "Straight flush should have high rank"
    
    # Test pair
    cards = [
        Card("Hearts", 10),
        Card("Diamonds", 10),
        Card("Spades", 5),
        Card("Clubs", 8),
        Card("Hearts", 2),
        Card("Spades", 3),
        Card("Clubs", 4)
    ]
    rank, kickers = evaluate_best_five(cards)
    hand_name = get_hand_name(rank)
    assert "Pair" in hand_name, f"Expected pair, got {hand_name}"
    assert rank == 2, "Pair should have rank 2"
    
    # Test high card
    cards = [
        Card("Hearts", 14),
        Card("Diamonds", 10),
        Card("Spades", 5),
        Card("Clubs", 8),
        Card("Hearts", 2),
        Card("Spades", 3),
        Card("Clubs", 6)
    ]
    rank, kickers = evaluate_best_five(cards)
    hand_name = get_hand_name(rank)
    assert "High Card" in hand_name, f"Expected high card, got {hand_name}"
    assert rank == 1, "High card should have rank 1"


if __name__ == "__main__":
    # Run with pytest for better output:
    # pytest test_engine.py -v
    import pytest
    pytest.main([__file__, "-v"])
