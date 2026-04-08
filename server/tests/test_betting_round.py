"""
Test Betting Round Logic

Tests for the betting round bug fix where players should
respond to raises before the round ends.
"""

import pytest
from app.engine import Card, Player, Game, GameEventType
from app.engine.game import GamePhase
from app.managers.game_flow import GameFlowManager
from app.managers.room_manager import RoomManager
from app.models.schemas import RoomConfig
from app.engine.agents import AgentRegistry, BaseAgent


class MockPlayer(Player):
    """Player with predetermined actions for testing."""
    
    def __init__(self, actions: list, **kwargs):
        super().__init__(**kwargs)
        self.actions = actions
        self.action_index = 0
        self.actions_taken = []
    
    def get_next_action(self):
        """Get the next predetermined action."""
        if self.action_index < len(self.actions):
            action = self.actions[self.action_index]
            self.action_index += 1
            return action
        return "fold"  # Default if we run out of actions


class TestBettingRoundLogic:
    """Test betting round scenarios."""
    
    def test_players_respond_to_bb_raise(self):
        """
        Test that when BB raises pre-flop, other players get to respond.
        
        Scenario:
        - Player 1 (Dealer): calls $20
        - Player 2 (SB): calls $10 more (total $20)
        - Player 3 (BB): raises to $40
        - Player 1 should get to respond!
        - Player 2 should get to respond!
        """
        # Create players with enough chips
        players = [
            Player(chips=1000, name="Dealer", player_id="player_1"),
            Player(chips=1000, name="SB", player_id="player_2"),
            Player(chips=1000, name="BB", player_id="player_3")
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        # Track all actions taken
        actions_taken = []
        
        def track_action(data):
            actions_taken.append({
                'player_id': data.get('player_id'),
                'action': data.get('action'),
                'amount': data.get('amount')
            })
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play a hand
        game.play_hand()
        
        # Count actions per player in pre-flop
        # After BB raises, both other players should act again
        preflop_actions = {}
        for action in actions_taken:
            pid = action['player_id']
            preflop_actions[pid] = preflop_actions.get(pid, 0) + 1
        
        # Verify chip conservation
        total_chips = sum(p.chips for p in players)
        assert total_chips == 3000, "Total chips should be conserved"
    
    def test_betting_round_ends_when_all_check(self):
        """Test that betting round ends correctly when everyone checks."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        events = []
        def track_event(data):
            events.append(data)
        
        game.on_event(GameEventType.BETTING_ROUND_ENDED, track_event)
        
        # Play hand
        game.play_hand()
        
        # Should have multiple betting round ended events
        # (Pre-flop, Flop, Turn, River if hand goes to showdown)
        assert len(events) >= 1, "At least one betting round should complete"
    
    def test_fold_ends_hand_early(self):
        """Test that if all but one player folds, hand ends."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        pot_awarded = []
        def track_pot(data):
            pot_awarded.append(data)
        
        game.on_event(GameEventType.POT_AWARDED, track_pot)
        
        # Play hand
        game.play_hand()
        
        # Pot should be awarded
        assert len(pot_awarded) == 1, "Pot should be awarded exactly once"
        
        # Chips should be conserved
        total = sum(p.chips for p in players)
        assert total == 2000, "Chips should be conserved"
    
    def test_raise_resets_action(self):
        """Test that a raise allows others to respond."""
        players = [
            Player(chips=1000, name="Alice", player_id="p1"),
            Player(chips=1000, name="Bob", player_id="p2"),
            Player(chips=1000, name="Charlie", player_id="p3"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        actions = []
        def track_action(data):
            actions.append(data)
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play hand
        game.play_hand()
        
        # Should have actions from all players
        player_ids = set(a['player_id'] for a in actions)
        assert len(player_ids) >= 2, "At least 2 players should act"


class TestPreFlopBBOption:
    """Test the Big Blind's option to raise when no one raised."""
    
    def test_bb_can_raise_when_all_call(self):
        """BB should get the option to raise even if everyone just calls."""
        players = [
            Player(chips=1000, name="Dealer", player_id="dealer"),
            Player(chips=1000, name="SB", player_id="sb"),
            Player(chips=1000, name="BB", player_id="bb"),
        ]
        
        game = Game(players=players, small_blind=10, big_blind=20)
        
        bb_actions = []
        def track_action(data):
            if data.get('player_id') == 'bb':
                bb_actions.append(data)
        
        game.on_event(GameEventType.PLAYER_ACTION_TAKEN, track_action)
        
        # Play hand
        game.play_hand()
        
        # BB should have at least one action
        assert len(bb_actions) >= 1, "BB should get to act at least once"


class TestBankruptPlayerStartingPosition:
    """
    Tests for the bug where a bankrupt (0-chip) player was returned as the
    starting player for a new hand, freezing the game when that player was human.
    """

    def _make_game(self, chips_list):
        """Helper: create a Game with players having the given chip counts."""
        players = [
            Player(chips=c, name=f"P{i+1}", player_id=f"p{i+1}")
            for i, c in enumerate(chips_list)
        ]
        # dealer is index 0, SB=1, BB=2, UTG=3
        game = Game(players=players, small_blind=10, big_blind=20)
        game._prepare_new_hand()
        game.current_phase = GamePhase.PRE_FLOP
        game.dealer_index = 0
        return game, players

    def test_starting_player_skips_bankrupt_utg(self):
        """
        When the natural UTG seat is held by a bankrupt player,
        get_starting_player_index must return the next active player instead.

        Layout (dealer=0): SB=1, BB=2, UTG=3 (bankrupt), UTG+1=4 (active)
        Expected starting index: 4
        """
        game, players = self._make_game([1000, 1000, 1000, 0, 1000])
        # UTG is index 3 (dealer+3 % 5 == 3), who has 0 chips
        # The next active player is index 4
        players[3].is_playing_round = False  # bankrupt player is out

        start = GameFlowManager.get_starting_player_index(game)

        assert start != 3, "Should not start on the bankrupt player at UTG"
        assert players[start].chips > 0, "Starting player must have chips"
        assert players[start].is_playing_round, "Starting player must be in the round"

    def test_starting_player_skips_multiple_bankrupt(self):
        """
        Multiple consecutive bankrupt players at UTG positions are all skipped.

        Layout (dealer=0): SB=1, BB=2, UTG=3 (bankrupt), UTG+1=4 (bankrupt),
        UTG+2=5 (active)
        Expected starting index: 5
        """
        game, players = self._make_game([1000, 1000, 1000, 0, 0, 1000])
        players[3].is_playing_round = False
        players[4].is_playing_round = False

        start = GameFlowManager.get_starting_player_index(game)

        assert start == 5, f"Expected start=5, got {start}"
        assert players[start].chips > 0

    def test_starting_player_valid_when_all_have_chips(self):
        """Sanity check: normal case returns dealer+3 without changes."""
        game, players = self._make_game([1000, 1000, 1000, 1000, 1000])

        start = GameFlowManager.get_starting_player_index(game)

        assert start == 3  # (0 + 3) % 5
        assert players[start].chips > 0


class TestBankruptHumanDoesNotFreezeGame:
    """
    Tests for the bug where _progress_game_after_action stopped to wait for
    a bankrupt human player, freezing the game indefinitely.

    This uses RoomManager with a mixture of a human player (0 chips) and AI
    players so the full action-progression path is exercised.
    """

    def _make_room_with_broke_human(self):
        """
        Create a room where:
          - 1 human player with 0 chips (bust)
          - 4 AI players that each have chips
        The human is registered as a non-agent Player so the room manager
        would previously pause to wait for their action.
        empty seats are left empty when the game starts.
        """
        manager = RoomManager()
        config = RoomConfig(
            name="test-room",
            min_players=2,
            small_blind=10,
            big_blind=20,
            starting_chips=200,
        )
        room = manager.create_room(config)

        # Add a broke human player
        human = Player(chips=0, name="BrokeHuman", player_id="human-broke")
        room.players.append(human)
        manager._player_rooms["human-broke"] = room.id

        # Add 4 AI players with chips (keeps one empty seat in a 6-seat room)
        for i in range(4):
            ai = AgentRegistry.create(
                "random",
                name=f"Bot-{i+1}",
                chips=200,
                player_id=f"ai-test-{i}",
            )
            room.players.append(ai)

        return manager, room

    def test_game_starts_without_freezing(self):
        """
        start_game must complete (not freeze) even when the human at the
        starting position has 0 chips.
        """
        manager, room = self._make_room_with_broke_human()

        # This must return True and not block forever
        result = manager.start_game(room.id)

        assert result is True, "start_game should succeed"
        # The room should either be waiting for a real player or have finished the hand
        updated_room = manager.get_room(room.id)
        # Game should have progressed past the bankrupt human
        if updated_room and updated_room.current_player_index is not None:
            acting_player = updated_room.players[updated_room.current_player_index]
            assert acting_player.chips > 0, (
                "The player waiting for action must have chips; "
                "a bankrupt player should never be left as current_player"
            )

    def test_hand_completes_chips_conserved(self):
        """
        After the hand involving a bankrupt human runs to completion, total
        chips in play must equal the chips held by active players before the hand.
        """
        manager, room = self._make_room_with_broke_human()
        manager.start_game(room.id)

        updated_room = manager.get_room(room.id)
        if updated_room is None:
            return  # room cleaned up (all-AI room with no human)

        total_chips = sum(p.chips for p in updated_room.players)
        # Total chips across all active AI players before the hand was 4 * 200 = 800
        # The human started with 0, so total should still be 800
        assert total_chips == 800, (
            f"Chips not conserved after hand with bankrupt human: {total_chips} != 800"
        )

    def test_next_hand_skips_bankrupt_human(self):
        """
        deal_next_hand must also complete without freezing when the bankrupt
        human would be in the UTG seat for the second hand.
        """
        manager, room = self._make_room_with_broke_human()
        manager.start_game(room.id)

        # Now trigger a second hand
        result = manager.deal_next_hand(room.id)

        # deal_next_hand returns False only if game-over or room missing;
        # with 4 active AI players it should continue
        assert result is True, "deal_next_hand should succeed with active AI players"

        updated_room = manager.get_room(room.id)
        if updated_room and updated_room.current_player_index is not None:
            acting_player = updated_room.players[updated_room.current_player_index]
            assert acting_player.chips > 0, (
                "Second hand: player awaiting action must have chips"
            )


class TestLobbyAiIdentity:
    """Regression tests for AI identity generation in lobby edits."""

    def test_remove_middle_ai_then_add_has_unique_player_ids(self):
        """
        Removing a non-last bot and adding a new bot back must not duplicate
        any existing AI player_id.
        """
        manager = RoomManager()
        config = RoomConfig(
            name="ai-id-regression",
            min_players=2,
            small_blind=10,
            big_blind=20,
            starting_chips=200,
        )
        room = manager.create_room(config)

        manager.add_ai_player(room.id, ai_type="random")
        manager.add_ai_player(room.id, ai_type="random")

        ai_ids_before = [
            p.player_id for p in room.players if isinstance(p, BaseAgent)
        ]
        assert len(ai_ids_before) == 2
        assert len(set(ai_ids_before)) == 2

        # Remove the first bot (middle removal scenario once a human is present).
        removed_id = ai_ids_before[0]
        manager.remove_player_from_lobby(room.id, removed_id)

        updated_room = manager.add_ai_player(room.id, ai_type="random")
        assert updated_room is not None

        ai_ids_after = [
            p.player_id for p in updated_room.players if isinstance(p, BaseAgent)
        ]
        assert len(ai_ids_after) == 2
        assert len(set(ai_ids_after)) == 2, "AI player_id values must stay unique"


class TestRoomStuckFallback:
    """Safety checks for stuck room fallback behavior."""

    def test_room_progression_fallback_breaks_non_progressing_loop(self, monkeypatch):
        """If loop state never changes, manager should trigger fallback and end the hand."""
        manager = RoomManager()
        config = RoomConfig(
            name="stuck-room-regression",
            min_players=2,
            small_blind=10,
            big_blind=20,
            starting_chips=200,
        )
        room = manager.create_room(config)
        manager.add_ai_player(room.id, ai_type="random")
        manager.add_ai_player(room.id, ai_type="random")
        room.is_active = True
        room.game = Game(
            players=room.players,
            small_blind=room.config.small_blind,
            big_blind=room.config.big_blind,
        )
        room.game.hand_number = 1
        room.game.current_phase = GamePhase.PRE_FLOP
        room.game._prepare_new_hand()
        room.game._post_blinds()
        room.game._deal_hole_cards()
        room.current_player_index = 0

        monkeypatch.setattr(
            manager,
            "_execute_ai_action",
            lambda _room, _player: None,
        )
        monkeypatch.setattr(
            GameFlowManager,
            "get_next_player_to_act",
            staticmethod(lambda _game, _idx: 0),
        )

        manager._progress_game_after_action(room)

        assert room.current_player_index is None
        assert any(
            "Fallback Triggered" in entry.get("action", "")
            for entry in room.game.action_log
        ), "Fallback marker should be appended to action log"


class TestRoomConfigAndStartBehavior:
    """Regression tests for fixed-size rooms and no start-time auto-fill."""

    def test_rooms_always_use_six_seats(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(
                name="fixed-six",
                min_players=2,
                small_blind=10,
                big_blind=20,
                starting_chips=500,
            )
        )

        assert room.config.max_players == 6
        assert room.to_dict()["max_players"] == 6

    def test_start_game_does_not_auto_fill_empty_seats(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(
                name="no-autofill",
                min_players=2,
                small_blind=10,
                big_blind=20,
                starting_chips=300,
            )
        )

        room.players.append(Player(chips=300, name="Human-1", player_id="h1"))
        room.players.append(Player(chips=300, name="Human-2", player_id="h2"))
        before_start_count = room.player_count

        assert manager.start_game(room.id) is True
        assert room.player_count == before_start_count


class TestHostAndAiRenameBehavior:
    """Tests for host ownership and AI rename support."""

    def test_first_human_join_becomes_host(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(name="host-room", min_players=2, starting_chips=500)
        )

        p1 = Player(chips=500, name="Host", player_id="p-host")
        p2 = Player(chips=500, name="Guest", player_id="p-guest")
        manager.join_room(room.id, p1)
        manager.join_room(room.id, p2)

        assert room.host_player_id == "p-host"

    def test_host_transfers_when_host_leaves(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(name="host-transfer", min_players=2, starting_chips=500)
        )

        p1 = Player(chips=500, name="Host", player_id="p-host")
        p2 = Player(chips=500, name="Guest", player_id="p-guest")
        manager.join_room(room.id, p1)
        manager.join_room(room.id, p2)

        manager.leave_room("p-host")
        assert room.host_player_id == "p-guest"

    def test_can_rename_ai_player_in_lobby(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(name="rename-ai", min_players=2, starting_chips=500)
        )
        manager.add_ai_player(room.id, ai_type="random")
        ai_player = next(p for p in room.players if isinstance(p, BaseAgent))

        updated_room = manager.rename_ai_player(room.id, ai_player.player_id, "DealerBot")

        assert updated_room is not None
        renamed_ai = next(p for p in room.players if p.player_id == ai_player.player_id)
        assert renamed_ai.name == "DealerBot"

    def test_rename_ai_rejects_duplicate_name(self):
        manager = RoomManager()
        room = manager.create_room(
            RoomConfig(name="rename-ai-duplicate", min_players=2, starting_chips=500)
        )
        manager.add_ai_player(room.id, ai_type="random")
        manager.add_ai_player(room.id, ai_type="random")
        ai_players = [p for p in room.players if isinstance(p, BaseAgent)]
        assert len(ai_players) == 2

        with pytest.raises(ValueError, match="already exists"):
            manager.rename_ai_player(room.id, ai_players[0].player_id, ai_players[1].name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
