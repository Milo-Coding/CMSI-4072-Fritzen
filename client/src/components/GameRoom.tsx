import { useState, useEffect, useRef } from "react";
import "./GameRoom.css";

interface Card {
  suit: string;
  value: number;
  display: string;
}

interface PlayerPublic {
  player_id: string;
  name: string;
  chips: number;
  hand_size: number;
  is_playing_round: boolean;
  current_bet_in_round: number;
  has_acted_this_round: boolean;
  is_agent: boolean;
  is_all_in: boolean;
}

interface GameState {
  hand_number: number;
  phase: string;
  dealer_index: number;
  pot: number;
  current_bet: number;
  small_blind: number;
  big_blind: number;
  community_cards: Card[];
  players: PlayerPublic[];
  your_hand: Card[];
  your_index: number;
  active_player_count: number;
  available_actions: string[];
  call_amount: number;
  is_your_turn: boolean;
  hand_over: boolean;
  game_over: boolean;
  winner: { player_id: string; name: string; chips: number } | null;
  side_pots: { amount: number; eligible_players: string[]; bet_cap: number }[];
  action_log: {
    player_id: string | null;
    player_name: string | null;
    action: string;
    amount?: number | null;
    timestamp: number;
  }[];
  showdown_hands: {
    player_id: string;
    player_name: string;
    hand: Card[];
    hand_rank: string;
    rank_value: number;
  }[];
}

interface Room {
  id: string;
  name: string;
  player_count: number;
  max_players: number;
  is_active: boolean;
  phase: string;
  small_blind: number;
  big_blind: number;
  pot: number;
  players: { player_id: string; name: string; is_agent: boolean }[];
}

interface GameRoomProps {
  roomId: string;
  playerName: string;
  onLeave: () => void;
}

const WS_BASE = "ws://localhost:8000";

function GameRoom({ roomId, playerName, onLeave }: GameRoomProps) {
  const [connected, setConnected] = useState(false);
  const [room, setRoom] = useState<Room | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [betAmount, setBetAmount] = useState(0);
  const [myPlayerId, setMyPlayerId] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [roomId, playerName]);

  const connectWebSocket = () => {
    const wsUrl = `${WS_BASE}/ws/game/${roomId}?player_name=${encodeURIComponent(
      playerName,
    )}`;
    console.log("Connecting to:", wsUrl);

    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log("WebSocket connected");
      setConnected(true);
      setError(null);
    };

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log("Received message:", message);

      switch (message.type) {
        case "connected":
          console.log("Player connected:", message.data);
          setMyPlayerId(message.data.player_id);
          break;

        case "game_state":
          setRoom(message.data.room);
          setGameState(message.data.game_state);
          break;

        case "player_joined":
          console.log("Player joined:", message.data);
          break;

        case "player_left":
          console.log("Player left:", message.data);
          break;

        case "player_action_taken":
          console.log("Action taken:", message.data);
          break;

        case "error":
          setError(message.data.message);
          console.error("Error:", message.data);
          break;

        default:
          console.log("Unknown message type:", message.type);
      }
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setError("Connection error");
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      setConnected(false);
    };
  };

  const sendAction = (action: string, amount?: number) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }

    const message = {
      type: "player_action",
      data: {
        action,
        ...(amount !== undefined && { amount }),
      },
    };

    console.log("Sending action:", message);
    ws.current.send(JSON.stringify(message));
  };

  const startGame = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }

    ws.current.send(
      JSON.stringify({
        type: "start_game",
        data: {},
      }),
    );
  };

  const nextHand = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }

    ws.current.send(
      JSON.stringify({
        type: "next_hand",
        data: {},
      }),
    );
  };

  const resetRoom = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }

    ws.current.send(
      JSON.stringify({
        type: "reset_room",
        data: {},
      }),
    );
  };

  const addAI = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }
    ws.current.send(JSON.stringify({ type: "add_ai", data: {} }));
  };

  const removePlayer = (targetPlayerId: string) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }
    ws.current.send(
      JSON.stringify({
        type: "remove_player",
        data: { player_id: targetPlayerId },
      }),
    );
  };

  const handleLeave = () => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          type: "leave_game",
          data: {},
        }),
      );
    }
    onLeave();
  };

  // const getSuitSymbol = (suit: string): string => {
  //   const symbols: { [key: string]: string } = {
  //     Hearts: "♥",
  //     Diamonds: "♦",
  //     Clubs: "♣",
  //     Spades: "♠",
  //   };
  //   return symbols[suit] || suit;
  // };

  const getSuitColor = (suit: string): string => {
    return suit === "Hearts" || suit === "Diamonds" ? "red" : "black";
  };

  if (!connected) {
    return (
      <div className="game-room">
        <div className="loading">
          <h2>Connecting to room...</h2>
          <button onClick={handleLeave} className="secondary-button">
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="game-room">
      <div className="game-header">
        <div className="room-info">
          <h2>{room?.name || `Room ${roomId}`}</h2>
          <span className="room-stats">
            {room?.player_count || 0} / {room?.max_players || 0} players
          </span>
          <span className="room-phase">{room?.phase || "waiting"}</span>
        </div>
        <button onClick={handleLeave} className="leave-button">
          Leave Room
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {!room?.is_active && (
        <div className="waiting-area">
          <h3>Lobby</h3>

          <div className="seat-grid">
            {(room?.players || []).map((player) => (
              <div
                key={player.player_id}
                className={`seat filled ${
                  player.is_agent ? "ai-seat" : "human-seat"
                }`}
              >
                <div className="seat-icon">{player.is_agent ? "🤖" : "👤"}</div>
                <div className="seat-name">{player.name}</div>
                <div className="seat-type">
                  {player.is_agent ? "AI" : "Human"}
                </div>
                {player.player_id !== myPlayerId && (
                  <button
                    className="remove-player-btn"
                    onClick={() => removePlayer(player.player_id)}
                    title="Remove player"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}

            {Array.from({
              length: (room?.max_players || 0) - (room?.players?.length || 0),
            }).map((_, idx) => (
              <div key={`empty-${idx}`} className="seat empty">
                <div className="seat-icon">⬜</div>
                <div className="seat-name">Empty Seat</div>
                <div className="seat-type">Waiting...</div>
              </div>
            ))}
          </div>

          <div className="lobby-actions">
            {(room?.player_count || 0) < (room?.max_players || 0) && (
              <button onClick={addAI} className="secondary-button">
                + Add AI Player
              </button>
            )}
            {(room?.player_count || 0) >= 2 && (
              <button onClick={startGame} className="primary-button">
                Start Game
              </button>
            )}
          </div>

          <p className="lobby-hint">
            Empty seats will be automatically filled with AI when the game
            starts.
          </p>
        </div>
      )}

      {room?.is_active && gameState && (
        <div className="game-area">
          <div className="game-main">
            {/* Community Cards */}
            <div className="community-area">
              <div className="pot-display">
                <span className="pot-label">Pot</span>
                <span className="pot-amount">${gameState.pot || 0}</span>
                {gameState.side_pots && gameState.side_pots.length > 0 && (
                  <div className="side-pots">
                    {gameState.side_pots.map((sidePot, idx) => {
                      const eligibleNames = sidePot.eligible_players.map(
                        (pid) =>
                          gameState.players.find((p) => p.player_id === pid)
                            ?.name ?? pid,
                      );
                      return (
                        <div key={idx} className="side-pot">
                          Side Pot {idx + 1}: ${sidePot.amount} —{" "}
                          {eligibleNames.join(", ")}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="community-cards">
                {(gameState.community_cards || []).map((card, idx) => (
                  <div key={idx} className={`card ${getSuitColor(card.suit)}`}>
                    <div className="card-value">{card.display}</div>
                  </div>
                ))}
                {(!gameState.community_cards ||
                  gameState.community_cards.length === 0) && (
                  <div className="no-cards">No community cards yet</div>
                )}
              </div>
              <div className="phase-indicator">
                {gameState.phase || "waiting"}
              </div>

              {/* Showdown Hands Display */}
              {gameState.showdown_hands &&
                gameState.showdown_hands.length > 0 && (
                  <div className="showdown-display">
                    <h3>Showdown!</h3>
                    <div className="showdown-hands">
                      {gameState.showdown_hands
                        .sort((a, b) => b.rank_value - a.rank_value)
                        .map((hand, idx) => (
                          <div
                            key={hand.player_id}
                            className={`showdown-hand ${idx === 0 ? "winner" : ""}`}
                          >
                            <div className="showdown-player">
                              {hand.player_name}
                            </div>
                            <div className="showdown-cards">
                              {hand.hand.map((card, cardIdx) => (
                                <div
                                  key={cardIdx}
                                  className={`card small ${getSuitColor(card.suit)}`}
                                >
                                  <div className="card-value">
                                    {card.display}
                                  </div>
                                </div>
                              ))}
                            </div>
                            <div className="showdown-rank">
                              {hand.hand_rank}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
            </div>

            {/* Action Log */}
            <div className="action-log">
              <h3>Action Log</h3>
              <div className="log-entries">
                {(gameState.action_log || [])
                  .slice()
                  .reverse()
                  .map((entry, idx) =>
                    entry.player_name === null ? (
                      <div key={idx} className="log-phase-divider">
                        {entry.action}
                      </div>
                    ) : (
                      <div key={idx} className="log-entry">
                        <span className="log-player">{entry.player_name}</span>
                        <span className="log-action">{entry.action}</span>
                        {entry.amount != null && (
                          <span className="log-amount">${entry.amount}</span>
                        )}
                      </div>
                    ),
                  )}
                {(!gameState.action_log ||
                  gameState.action_log.length === 0) && (
                  <div className="log-empty">No actions yet</div>
                )}
              </div>
            </div>
          </div>

          {/* Other Players */}
          <div className="players-area">
            {(gameState.players || []).map((player, idx) => (
              <div
                key={player.player_id}
                className={`player-card ${
                  idx === gameState.dealer_index ? "dealer" : ""
                } ${idx === gameState.your_index ? "you" : ""}`}
              >
                <div className="player-name">
                  {player.name}
                  {idx === gameState.dealer_index && " 🎯"}
                  {idx === gameState.your_index && " (You)"}
                </div>
                <div className="player-chips">${player.chips}</div>
                <div className="player-bet">
                  {player.current_bet_in_round > 0 &&
                    `Bet: $${player.current_bet_in_round}`}
                </div>
                <div className="player-cards">
                  {player.hand_size > 0 &&
                    `${player.hand_size} card${player.hand_size > 1 ? "s" : ""}`}
                </div>
                {!player.is_playing_round && (
                  <div className="player-status folded">Folded</div>
                )}
                {player.is_all_in && (
                  <div
                    className="player-status all-in"
                    style={{
                      backgroundColor: "#FF9800",
                      color: "white",
                      fontWeight: "bold",
                    }}
                  >
                    ALL-IN
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Your Hand */}
          <div className="your-area">
            <div className="your-hand">
              <h3>Your Hand</h3>
              <div className="hand-cards">
                {(gameState.your_hand || []).map((card, idx) => (
                  <div
                    key={idx}
                    className={`card large ${getSuitColor(card.suit)}`}
                  >
                    <div className="card-value">{card.display}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="action-area">
              {gameState.game_over ? (
                <div style={{ textAlign: "center" }}>
                  <h2 style={{ color: "#FFD700", marginBottom: "20px" }}>
                    🏆 {gameState.winner?.name} Wins! 🏆
                  </h2>
                  <p style={{ marginBottom: "20px", fontSize: "16px" }}>
                    Winner takes all {gameState.winner?.chips} chips!
                  </p>
                  <button
                    onClick={resetRoom}
                    className="action-button reset"
                    style={{
                      backgroundColor: "#2196F3",
                      fontSize: "18px",
                      padding: "15px 30px",
                    }}
                  >
                    Reset Room & Play Again
                  </button>
                </div>
              ) : gameState.hand_over ? (
                <button
                  onClick={nextHand}
                  className="action-button next-hand"
                  style={{
                    backgroundColor: "#4CAF50",
                    fontSize: "18px",
                    padding: "15px 30px",
                  }}
                >
                  Deal Next Hand
                </button>
              ) : gameState.is_your_turn ? (
                <>
                  <div className="action-buttons">
                    {(gameState.available_actions || []).includes("fold") && (
                      <button
                        onClick={() => sendAction("fold")}
                        className="action-button fold"
                      >
                        Fold
                      </button>
                    )}
                    {(gameState.available_actions || []).includes("check") && (
                      <button
                        onClick={() => sendAction("check")}
                        className="action-button check"
                      >
                        Check
                      </button>
                    )}
                    {(gameState.available_actions || []).includes("call") && (
                      <button
                        onClick={() => sendAction("call")}
                        className="action-button call"
                      >
                        Call ${gameState.call_amount || 0}
                      </button>
                    )}
                    {(gameState.available_actions || []).includes("all_in") && (
                      <button
                        onClick={() => sendAction("all_in")}
                        className="action-button all-in"
                        style={{
                          backgroundColor: "#FF9800",
                          fontWeight: "bold",
                        }}
                      >
                        All-In (
                        {gameState.players[gameState.your_index]?.chips || 0})
                      </button>
                    )}
                    {(gameState.available_actions || []).includes("bet") && (
                      <div className="bet-controls">
                        <input
                          type="number"
                          value={betAmount}
                          onChange={(e) => setBetAmount(Number(e.target.value))}
                          min={gameState.big_blind || 10}
                          placeholder="Amount"
                          className="bet-input"
                        />
                        <button
                          onClick={() => sendAction("bet", betAmount)}
                          className="action-button bet"
                          disabled={betAmount < (gameState.big_blind || 10)}
                        >
                          Bet
                        </button>
                      </div>
                    )}
                    {(gameState.available_actions || []).includes("raise") && (
                      <div className="bet-controls">
                        <input
                          type="number"
                          value={betAmount}
                          onChange={(e) => setBetAmount(Number(e.target.value))}
                          min={
                            (gameState.call_amount || 0) +
                            (gameState.big_blind || 10)
                          }
                          placeholder="Amount"
                          className="bet-input"
                        />
                        <button
                          onClick={() => sendAction("raise", betAmount)}
                          className="action-button raise"
                          disabled={
                            betAmount <
                            (gameState.call_amount || 0) +
                              (gameState.big_blind || 10)
                          }
                        >
                          Raise
                        </button>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="waiting-turn">Waiting for your turn...</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GameRoom;
