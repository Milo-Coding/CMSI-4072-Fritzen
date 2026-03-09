"""
Room Manager - Multi-room game management

Handles creating, joining, and managing multiple concurrent poker games.
"""

import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..engine import Game, Player, GameEventType
from ..engine.game import GamePhase
from ..engine.agents import AgentRegistry, BaseAgent
from ..models.schemas import RoomConfig
from .game_flow import GameFlowManager


@dataclass
class Room:
    """
    Represents a poker room/table.
    
    Contains a game instance and tracks connected players.
    """
    id: str
    name: str
    config: RoomConfig
    game: Optional[Game] = None
    players: List[Player] = field(default_factory=list)
    is_active: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    current_player_index: Optional[int] = None  # Track whose turn it is
    
    # Event callbacks for broadcasting
    _event_callbacks: List[Callable] = field(default_factory=list)
    
    @property
    def player_count(self) -> int:
        return len(self.players)
    
    @property
    def is_full(self) -> bool:
        return self.player_count >= self.config.max_players
    
    @property
    def can_start(self) -> bool:
        return self.player_count >= self.config.min_players and not self.is_active
    
    @property
    def phase(self) -> str:
        if self.game:
            return self.game.current_phase.value
        return "waiting"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "player_count": self.player_count,
            "max_players": self.config.max_players,
            "is_active": self.is_active,
            "phase": self.phase,
            "small_blind": self.config.small_blind,
            "big_blind": self.config.big_blind or self.config.small_blind * 2,
            "pot": self.game.pot if self.game else 0,
            "players": [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "is_agent": isinstance(p, BaseAgent)
                }
                for p in self.players
            ]
        }
    
    def add_event_callback(self, callback: Callable[[str, dict], None]):
        """Add a callback for game events."""
        self._event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable):
        """Remove an event callback."""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)
    
    def _broadcast_event(self, event_data: dict):
        """Broadcast event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(self.id, event_data)
            except Exception as e:
                print(f"Error in event callback: {e}")


class RoomManager:
    """
    Manages multiple poker rooms.
    
    Provides room creation, player joining/leaving, and game lifecycle.
    """
    
    def __init__(self):
        self._rooms: Dict[str, Room] = {}
        self._player_rooms: Dict[str, str] = {}  # player_id -> room_id
    
    def create_room(self, config: RoomConfig) -> Room:
        """
        Create a new poker room.
        
        Args:
            config: Room configuration
            
        Returns:
            The created room
        """
        room_id = str(uuid.uuid4())[:8]
        room_name = config.name or f"Table-{room_id}"
        
        room = Room(
            id=room_id,
            name=room_name,
            config=config
        )
        
        # Add AI players if requested
        for i in range(config.ai_players):
            try:
                ai_player = AgentRegistry.create(
                    config.ai_type,
                    name=f"Bot-{i+1}",
                    chips=config.starting_chips,
                    player_id=f"ai-{room_id}-{i}"
                )
                room.players.append(ai_player)
            except ValueError as e:
                print(f"Warning: Could not create AI player: {e}")
        
        self._rooms[room_id] = room
        return room
    
    def add_ai_player(self, room_id: str) -> Optional[Room]:
        """
        Add a single AI player to a room (pre-game only).

        Returns:
            The room if successful, None otherwise
        """
        room = self.get_room(room_id)
        if not room or room.is_active or room.is_full:
            return None

        ai_count = sum(1 for p in room.players if isinstance(p, BaseAgent))
        try:
            ai_player = AgentRegistry.create(
                room.config.ai_type,
                name=f"Bot-{ai_count + 1}",
                chips=room.config.starting_chips,
                player_id=f"ai-{room_id}-{ai_count}"
            )
            room.players.append(ai_player)
            return room
        except ValueError as e:
            print(f"Warning: Could not create AI player: {e}")
            return None

    def remove_player_from_lobby(self, room_id: str, target_player_id: str) -> Optional[Room]:
        """
        Remove a player (human or AI) from the lobby before the game starts.

        Returns:
            The room if successful, None otherwise
        """
        room = self.get_room(room_id)
        if not room or room.is_active:
            return None

        # Clean up human player session mapping if applicable
        if target_player_id in self._player_rooms:
            del self._player_rooms[target_player_id]

        room.players = [p for p in room.players if p.player_id != target_player_id]
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        return self._rooms.get(room_id)
    
    def list_rooms(self, include_full: bool = True) -> List[Room]:
        """
        List all rooms.
        
        Args:
            include_full: Include rooms that are full
        """
        rooms = list(self._rooms.values())
        if not include_full:
            rooms = [r for r in rooms if not r.is_full]
        return rooms
    
    def delete_room(self, room_id: str) -> bool:
        """Delete a room."""
        if room_id in self._rooms:
            room = self._rooms[room_id]
            # Remove player mappings
            for player in room.players:
                if player.player_id in self._player_rooms:
                    del self._player_rooms[player.player_id]
            del self._rooms[room_id]
            return True
        return False
    
    def join_room(
        self, 
        room_id: str, 
        player: Player
    ) -> Optional[Room]:
        """
        Add a player to a room.
        
        Args:
            room_id: Room to join
            player: Player to add
            
        Returns:
            The room if successful, None if failed
        """
        room = self.get_room(room_id)
        if not room:
            return None
        
        if room.is_full:
            return None
        
        if room.is_active:
            # Could allow joining active games in the future
            return None
        
        # Check if player already in a room
        if player.player_id in self._player_rooms:
            # Leave current room first
            self.leave_room(player.player_id)
        
        room.players.append(player)
        self._player_rooms[player.player_id] = room_id
        
        return room
    
    def leave_room(self, player_id: str) -> Optional[Room]:
        """
        Remove a player from their current room.
        
        Args:
            player_id: Player to remove
            
        Returns:
            The room they left, or None
        """
        room_id = self._player_rooms.get(player_id)
        if not room_id:
            return None
        
        room = self.get_room(room_id)
        if not room:
            del self._player_rooms[player_id]
            return None
        
        # Find and remove player
        room.players = [p for p in room.players if p.player_id != player_id]
        del self._player_rooms[player_id]
        
        # Delete room if empty (except AI players)
        human_players = [p for p in room.players if not isinstance(p, BaseAgent)]
        if not human_players:
            self.delete_room(room_id)
        
        return room
    
    def get_player_room(self, player_id: str) -> Optional[Room]:
        """Get the room a player is in."""
        room_id = self._player_rooms.get(player_id)
        if room_id:
            return self.get_room(room_id)
        return None
    
    def start_game(self, room_id: str) -> bool:
        """
        Start the game in a room.
        
        Args:
            room_id: Room to start
            
        Returns:
            True if game started, False otherwise
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        if not room.can_start:
            return False

        # Auto-fill remaining empty seats with AI players
        empty_seats = room.config.max_players - room.player_count
        ai_count = sum(1 for p in room.players if isinstance(p, BaseAgent))
        for i in range(empty_seats):
            try:
                ai_player = AgentRegistry.create(
                    room.config.ai_type,
                    name=f"Bot-{ai_count + i + 1}",
                    chips=room.config.starting_chips,
                    player_id=f"ai-{room_id}-fill-{i}"
                )
                room.players.append(ai_player)
            except ValueError as e:
                print(f"Warning: Could not auto-fill AI player: {e}")

        # Create game instance
        room.game = Game(
            players=room.players,
            small_blind=room.config.small_blind,
            big_blind=room.config.big_blind
        )
        
        # Set dealer to first player with chips
        for i, player in enumerate(room.players):
            if player.chips > 0:
                room.game.dealer_index = i
                break
        
        # Register event handler for broadcasting
        for event_type in GameEventType:
            room.game.on_event(event_type, lambda data: room._broadcast_event(data))
        
        room.is_active = True
        
        # Initialize the first hand (deal cards, post blinds) but don't play it
        # The play will be driven by WebSocket player actions
        room.game.hand_number += 1
        room.game.current_phase = GamePhase.PRE_FLOP
        room.game.emit_event(GameEventType.HAND_STARTED, {
            "hand_number": room.game.hand_number,
            "dealer_index": room.game.dealer_index
        })
        room.game._prepare_new_hand()
        room.game._post_blinds()
        room.game._deal_hole_cards()
        room.game.emit_event(GameEventType.HOLE_CARDS_DEALT, {
            "players": [p.to_dict(hide_cards=True) for p in room.players]
        })
        
        # Set the first player to act
        room.current_player_index = GameFlowManager.get_starting_player_index(room.game)
        
        # Kick off the action sequence - if first player is AI, they'll act automatically
        self._start_action_sequence(room)
        
        return True
    
    def _start_action_sequence(self, room: "Room"):
        """Start the action sequence, checking if current player needs to act."""
        if not room.game or room.current_player_index is None:
            return
        
        current_player = room.players[room.current_player_index]
        
        # If current player is AI, have them act and continue the flow
        if isinstance(current_player, BaseAgent) or (hasattr(current_player, 'decide_action') and not hasattr(current_player, 'is_human')):
            try:
                self._execute_ai_action(room, current_player)
                # Continue the game flow
                self._progress_game_after_action(room)
            except Exception as e:
                print(f"Error in initial AI action: {e}")
                import traceback
                traceback.print_exc()
        # Otherwise it's a human's turn, they'll act via WebSocket
    
    def play_hand(self, room_id: str) -> bool:
        """
        Play a hand in a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            True if hand played, False otherwise
        """
        room = self.get_room(room_id)
        if not room or not room.game or not room.is_active:
            return False
        
        room.game.play_hand()
        return True
    
    def _log_action(self, room: 'Room', player_id: str, action: str, amount: Optional[int] = None):
        """Log a player action to the game's action log."""
        player = next((p for p in room.players if p.player_id == player_id), None)
        if player and room.game:
            log_entry = {
                "player_id": player_id,
                "player_name": player.name,
                "action": action,
                "timestamp": room.game.hand_number
            }
            if amount is not None:
                log_entry["amount"] = amount
            room.game.action_log.append(log_entry)
    
    def get_game_state(self, room_id: str, player_id: Optional[str] = None) -> Optional[dict]:
        """
        Get game state for a room.
        
        Args:
            room_id: Room ID
            player_id: If provided, get player-specific view
            
        Returns:
            Game state dictionary
        """
        room = self.get_room(room_id)
        if not room or not room.game:
            return None
        
        state = room.game.get_player_view(player_id) if player_id else room.game.get_state()
        
        # Extract current player's hand for easy frontend access
        if player_id:
            for player_data in state.get("players", []):
                if player_data["player_id"] == player_id:
                    state["your_hand"] = player_data.get("hand", [])
                    # Find player index
                    for idx, p in enumerate(room.players):
                        if p.player_id == player_id:
                            state["your_index"] = idx
                            break
                    break
            # Set default if not found
            if "your_hand" not in state:
                state["your_hand"] = []
                state["your_index"] = -1
        
        # Add whose turn it is and available actions
        if room.current_player_index is not None:
            current_player = room.players[room.current_player_index]
            state["current_player_id"] = current_player.player_id
            state["current_player_index"] = room.current_player_index
            
            # If this is the current player's view, add available actions
            if player_id and player_id == current_player.player_id:
                call_amount = room.game.current_table_bet - current_player.current_bet_in_round
                state["available_actions"] = room.game._get_available_actions(current_player, call_amount)
                state["call_amount"] = call_amount
                state["is_your_turn"] = True
            else:
                state["available_actions"] = []
                state["call_amount"] = 0
                state["is_your_turn"] = False
        else:
            state["current_player_id"] = None
            state["current_player_index"] = None
            state["available_actions"] = []
            state["call_amount"] = 0
            state["is_your_turn"] = False
        
        # Add hand_over flag - true if no current player (hand finished)
        state["hand_over"] = room.current_player_index is None and room.is_active
        
        # Check if game is over (only one player has chips)
        players_with_chips = [p for p in room.players if p.chips > 0]
        state["game_over"] = len(players_with_chips) <= 1 and room.is_active
        if state["game_over"] and len(players_with_chips) == 1:
            state["winner"] = {
                "player_id": players_with_chips[0].player_id,
                "name": players_with_chips[0].name,
                "chips": players_with_chips[0].chips
            }
        else:
            state["winner"] = None
        
        return state
    
    def deal_next_hand(self, room_id: str) -> bool:
        """
        Deal the next hand in a room.
        
        Args:
            room_id: Room ID
            
        Returns:
            True if next hand started, False otherwise
        """
        room = self.get_room(room_id)
        if not room or not room.game or not room.is_active:
            return False
        
        # Check if game is over (only one player has chips)
        players_with_chips = [p for p in room.players if p.chips > 0]
        if len(players_with_chips) <= 1:
            # Game is over, can't deal next hand
            return False
        
        # Reset for new hand
        room.game.hand_number += 1
        room.game.current_phase = GamePhase.PRE_FLOP
        
        # Advance dealer to next player with chips
        original_dealer = room.game.dealer_index
        next_dealer = room.game._find_next_player_with_chips(room.game.dealer_index)
        if next_dealer is not None:
            room.game.dealer_index = next_dealer
        else:
            # No player with chips found, should not happen if we checked earlier
            room.game.dealer_index = (room.game.dealer_index + 1) % len(room.players)
        
        room.game.emit_event(GameEventType.HAND_STARTED, {
            "hand_number": room.game.hand_number,
            "dealer_index": room.game.dealer_index
        })
        
        # Prepare and deal new hand
        room.game._prepare_new_hand()
        room.game._post_blinds()
        room.game._deal_hole_cards()
        
        room.game.emit_event(GameEventType.HOLE_CARDS_DEALT, {
            "players": [p.to_dict(hide_cards=True) for p in room.players]
        })
        
        # Set the first player to act
        room.current_player_index = GameFlowManager.get_starting_player_index(room.game)
        
        # Kick off the action sequence
        self._start_action_sequence(room)
        
        return True
    
    def reset_room(self, room_id: str, starting_chips: int = None) -> bool:
        """
        Reset a room - give all players their starting chips back.
        
        Args:
            room_id: Room ID
            starting_chips: Chips to give each player (uses room config if None)
            
        Returns:
            True if reset successful, False otherwise
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        # Use room's configured starting chips if not specified
        chips = starting_chips if starting_chips is not None else room.config.starting_chips
        
        # Reset all players' chips and state
        for player in room.players:
            player.chips = chips
            player.reset_for_new_hand()
        
        # Reset game state
        room.is_active = False
        room.game = None
        room.current_player_index = None
        
        return True
    
    def execute_action(
        self, 
        room_id: str, 
        player_id: str, 
        action: str, 
        amount: Optional[int] = None,
        auto_progress: bool = True
    ) -> dict:
        """
        Execute a player action in a room.
        
        Args:
            room_id: Room ID
            player_id: Player making action
            action: Action type
            amount: Amount for bet/raise
            auto_progress: Whether to auto-progress the game after action
            
        Returns:
            Result of the action
        """
        room = self.get_room(room_id)
        if not room or not room.game:
            return {"success": False, "error": "Room or game not found"}
        
        # Find player
        player = None
        for p in room.players:
            if p.player_id == player_id:
                player = p
                break
        
        if not player:
            return {"success": False, "error": "Player not found in room"}
        
        # Execute action based on type
        try:
            if action == "fold":
                player.do_fold()
                self._log_action(room, player_id, "fold")
            elif action == "check":
                if not player.do_check(room.game.current_table_bet):
                    return {"success": False, "error": "Cannot check"}
                self._log_action(room, player_id, "check")
            elif action == "call":
                contributed = player.do_call(room.game.current_table_bet)
                room.game.pot += contributed
                self._log_action(room, player_id, "call", contributed)
                # If player is now out of chips, they're all-in
                if player.chips == 0 and player.is_playing_round:
                    action = "all_in"  # Update action name for display
            elif action == "all_in":
                contributed = player.do_all_in()
                room.game.pot += contributed
                self._log_action(room, player_id, "all-in", contributed)
                # Update table bet if this all-in raises it
                if player.current_bet_in_round > room.game.current_table_bet:
                    room.game.current_table_bet = player.current_bet_in_round
            elif action == "bet":
                if amount is None:
                    return {"success": False, "error": "Bet requires amount"}
                contributed = player.do_bet(amount)
                room.game.current_table_bet = contributed
                room.game.pot += contributed
                self._log_action(room, player_id, "bet", amount)
                # If player is now out of chips, they're all-in
                if player.chips == 0 and player.is_playing_round:
                    action = "all_in"
            elif action == "raise":
                if amount is None:
                    return {"success": False, "error": "Raise requires amount"}
                new_wager, added = player.do_raise(room.game.current_table_bet, amount)
                if new_wager != -1:
                    room.game.current_table_bet = new_wager
                    room.game.pot += added
                    self._log_action(room, player_id, "raise", amount)
                    # If player is now out of chips, they're all-in
                    if player.chips == 0 and player.is_playing_round:
                        action = "all_in"
                else:
                    return {"success": False, "error": "Invalid raise"}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
            
            # Mark that the player has acted
            player.has_acted_this_round = True
            
            # Progress the game if requested
            if auto_progress:
                self._progress_game_after_action(room)
            
            return {
                "success": True,
                "action": action,
                "amount": amount,
                "player_id": player_id,
                "pot": room.game.pot,
                "is_all_in": player.chips == 0 and player.is_playing_round
            }
        except Exception as e:
            return {"success": False, "error": str(e)}    
    def _progress_game_after_action(self, room: "Room"):
        """Progress the game after a player action until it's a human's turn or hand ends."""
        if not room.game:
            return
        
        # First check if hand is already over (only one player left after fold)
        active_players = [p for p in room.players if p.is_playing_round]
        if len(active_players) <= 1:
            # Hand over due to folds
            GameFlowManager._award_pot(room.game)
            room.current_player_index = None
            room.game.emit_event(GameEventType.HAND_ENDED, {
                "hand_number": room.game.hand_number
            })
            return
        
        while True:
            # Find next player to act
            next_index = GameFlowManager.get_next_player_to_act(
                room.game, 
                room.current_player_index or 0
            )
            
            if next_index is None:
                # Betting round complete, advance to next phase
                continues = GameFlowManager.advance_to_next_phase(room.game)
                if not continues:
                    # Hand is over
                    room.current_player_index = None
                    break
                
                # Get first player for new phase
                next_index = GameFlowManager.get_starting_player_index(room.game)
            
            room.current_player_index = next_index
            next_player = room.players[next_index]
            
            # If it's an AI agent, have them act automatically
            if isinstance(next_player, BaseAgent) or (hasattr(next_player, 'decide_action') and not hasattr(next_player, 'is_human')):
                try:
                    self._execute_ai_action(room, next_player)
                    # Continue loop to process next player
                except Exception as e:
                    print(f"Error executing AI action: {e}")
                    # Stop on error to avoid infinite loop
                    break
            else:
                # It's a human player's turn - but only stop if they can actually act
                if not next_player.is_playing_round or next_player.chips == 0:
                    # Bankrupt / not in this hand – skip them
                    next_player.has_acted_this_round = True
                    continue
                break
        
        # If we exited the loop with current_player_index = None, hand is over
        if room.current_player_index is None:
            room.game.emit_event(GameEventType.HAND_ENDED, {
                "hand_number": room.game.hand_number
            })
    
    def _execute_ai_action(self, room: "Room", player: Player):
        """Execute an AI player's action."""
        if not room.game:
            return
        
        print(f"AI Player {player.name} ({player.player_id}) is taking action...")
        
        # Build game state for AI
        call_amount = room.game.current_table_bet - player.current_bet_in_round
        available_actions = room.game._get_available_actions(player, call_amount)
        
        # Safety check: all-in or folded players should have no actions
        if not available_actions:
            print(f"AI Player {player.name} has no available actions (likely all-in or folded)")
            return
        
        game_state = {
            "state_name": str(room.game.current_phase.value),
            "available_actions": available_actions,
            "call_amount": call_amount,
            "current_table_bet": room.game.current_table_bet,
            "pot": room.game.pot,
            "community_cards": [c.to_dict() for c in room.game.community_cards],
            "opponents_chips": [p.chips for p in room.players if p != player and p.is_playing_round],
            "dealer_index": room.game.dealer_index,
            "agent_index": room.players.index(player),
            "players": [p.to_dict(hide_cards=(p != player)) for p in room.players]
        }
        
        # Get AI decision
        decision = player.decide_action(game_state)
        print(f"AI decision: {decision}")
        
        # Execute the decision without auto-progressing (we're already in progress loop)
        if isinstance(decision, tuple):
            action, amount = decision
            result = self.execute_action(room.id, player.player_id, action, amount, auto_progress=False)
            print(f"AI action result: {result}")
        else:
            result = self.execute_action(room.id, player.player_id, decision, auto_progress=False)
            print(f"AI action result: {result}")