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
  total_bet_in_hand: number;
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
  showdown_winner_ids?: string[];
}

interface Room {
  id: string;
  name: string;
  player_count: number;
  max_players: number;
  is_active: boolean;
  phase: string;
  host_player_id?: string | null;
  small_blind: number;
  big_blind: number;
  pot: number;
  players: { player_id: string; name: string; is_agent: boolean }[];
}

interface GameRoomProps {
  roomId: string;
  playerName: string;
  onLeave: (options?: {
    destinationView?: "home" | "create" | "browse";
    errorMessage?: string;
    playerName?: string;
  }) => void;
}

const WS_BASE = import.meta.env.DEV
  ? window.location.origin.replace(/^http/, "ws")
  : (import.meta.env.VITE_WS_BASE ?? "ws://127.0.0.1:8000");
const API_BASE = import.meta.env.DEV
  ? "/api"
  : (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000/api");

function GameRoom({ roomId, playerName, onLeave }: GameRoomProps) {
  const [connected, setConnected] = useState(false);
  const [joinComplete, setJoinComplete] = useState(false);
  const [room, setRoom] = useState<Room | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [betAmount, setBetAmount] = useState(0);
  const [myPlayerId, setMyPlayerId] = useState<string | null>(null);
  const [selectedAiType, setSelectedAiType] = useState<"random" | "dqn">(
    "random",
  );
  const [dqnModelPath, setDqnModelPath] = useState("");
  const [availableModels, setAvailableModels] = useState<
    { name: string; path: string }[]
  >([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [communityAreaHeight, setCommunityAreaHeight] = useState<number | null>(
    null,
  );
  const ws = useRef<WebSocket | null>(null);
  const communityAreaRef = useRef<HTMLDivElement | null>(null);
  const errorTimeoutRef = useRef<number | null>(null);
  const joinFailureCodes = new Set([
    "JOIN_FAILED",
    "ROOM_NOT_FOUND",
    "ROOM_FULL",
    "ROOM_ACTIVE",
    "GAME_ALREADY_STARTED",
  ]);

  const formatNetworkError = (err: unknown, action: string): string => {
    const fallback = `Unable to ${action}. Verify server reachability at ${API_BASE} and ${WS_BASE}.`;
    if (!(err instanceof Error)) {
      return fallback;
    }

    if (
      err.name === "TypeError" &&
      err.message.toLowerCase().includes("fetch")
    ) {
      return fallback;
    }

    return err.message || fallback;
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (errorTimeoutRef.current) {
        window.clearTimeout(errorTimeoutRef.current);
      }
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [roomId, playerName]);

  useEffect(() => {
    if (!error) {
      return;
    }

    if (errorTimeoutRef.current) {
      window.clearTimeout(errorTimeoutRef.current);
    }

    errorTimeoutRef.current = window.setTimeout(() => {
      setError(null);
    }, 6000);

    return () => {
      if (errorTimeoutRef.current) {
        window.clearTimeout(errorTimeoutRef.current);
      }
    };
  }, [error]);

  useEffect(() => {
    if (!connected || !joinComplete) {
      return;
    }

    const intervalId = window.setInterval(() => {
      fetch(`${API_BASE}/rooms/${roomId}`, {
        method: "GET",
        keepalive: true,
      }).catch((err) => {
        console.warn("Keepalive ping failed:", err);
      });
    }, 60000);

    return () => window.clearInterval(intervalId);
  }, [connected, joinComplete, roomId]);

  useEffect(() => {
    const communityArea = communityAreaRef.current;
    if (!communityArea) {
      setCommunityAreaHeight(null);
      return;
    }

    const syncHeight = () => {
      setCommunityAreaHeight(
        Math.round(communityArea.getBoundingClientRect().height),
      );
    };

    syncHeight();

    const observer = new ResizeObserver(() => {
      syncHeight();
    });
    observer.observe(communityArea);

    return () => observer.disconnect();
  }, [room?.is_active]);

  useEffect(() => {
    if (
      room?.is_active ||
      selectedAiType !== "dqn" ||
      availableModels.length > 0
    ) {
      return;
    }

    let isCancelled = false;
    setLoadingModels(true);

    fetch(`${API_BASE}/models`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load DQN models (${response.status})`);
        }
        return response.json();
      })
      .then((data) => {
        if (isCancelled) {
          return;
        }

        const models = data.models || [];
        setAvailableModels(models);
        if (models.length > 0) {
          setDqnModelPath(models[0].path);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.error(
            "Failed to fetch DQN models from",
            `${API_BASE}/models`,
          );
          setAvailableModels([]);
          setError(formatNetworkError(err, "load DQN models"));
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setLoadingModels(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [room?.is_active, selectedAiType, availableModels.length]);

  const connectWebSocket = () => {
    setJoinComplete(false);
    setRoom(null);
    setGameState(null);
    setError(null);

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
          setJoinComplete(Boolean(message.data.room));
          break;

        case "player_joined":
          console.log("Player joined:", message.data);
          refreshRoomState();
          break;

        case "player_left":
          console.log("Player left:", message.data);
          refreshRoomState();
          break;

        case "player_action_taken":
          console.log("Action taken:", message.data);
          break;

        case "error":
          {
            const code = message.data?.code;
            const messageText =
              message.data?.message ?? "Unable to join room right now.";
            const looksLikeJoinFailure =
              joinFailureCodes.has(code) ||
              messageText.toLowerCase().includes("could not join room");

            if (!joinComplete && looksLikeJoinFailure) {
              if (ws.current && ws.current.readyState === WebSocket.OPEN) {
                ws.current.close(1000, "join-failed");
              }
              onLeave({
                destinationView: "browse",
                errorMessage: messageText,
                playerName,
              });
              return;
            }

            setError(messageText);
          }
          console.error("Error:", message.data);
          break;

        default:
          console.log("Unknown message type:", message.type);
      }
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setError(`Connection error. Could not reach ${wsUrl}.`);
    };

    ws.current.onclose = (event) => {
      console.log("WebSocket disconnected", event);
      setConnected(false);
      if (!event.wasClean) {
        setError(
          `Connection closed unexpectedly (code ${event.code}). Verify backend and CORS configuration.`,
        );
      }
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

  const refreshRoomState = async () => {
    try {
      const playerQuery = myPlayerId
        ? `?player_id=${encodeURIComponent(myPlayerId)}`
        : "";
      const stateResponse = await fetch(
        `${API_BASE}/rooms/${roomId}/state${playerQuery}`,
      );
      if (!stateResponse.ok) {
        throw new Error(
          `Failed to refresh room state (${stateResponse.status})`,
        );
      }
      const statePayload = await stateResponse.json();
      if (statePayload.room) {
        setRoom(statePayload.room);
      }
      if (statePayload.game_state) {
        setGameState(statePayload.game_state);
      } else {
        setGameState(null);
      }
    } catch (err) {
      console.warn("Failed to refresh room state:", err);
    }
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

    if (selectedAiType === "dqn" && !dqnModelPath.trim()) {
      setError("Please select a DQN model before adding a DQN agent.");
      return;
    }

    setError(null);

    ws.current.send(
      JSON.stringify({
        type: "add_ai",
        data: {
          ai_type: selectedAiType,
          ...(selectedAiType === "dqn" && dqnModelPath
            ? { dqn_model_path: dqnModelPath }
            : {}),
        },
      }),
    );
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

  const renameAIPlayer = (targetPlayerId: string, currentName: string) => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError("Not connected to server");
      return;
    }

    const newName = window.prompt("Rename AI player", currentName);
    if (newName === null) {
      return;
    }

    const trimmedName = newName.trim();
    if (!trimmedName) {
      setError("AI name cannot be empty.");
      return;
    }

    setError(null);
    ws.current.send(
      JSON.stringify({
        type: "rename_ai",
        data: {
          player_id: targetPlayerId,
          new_name: trimmedName,
        },
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
    onLeave({
      playerName,
    });
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

  const showdownWinnerIds = new Set(gameState?.showdown_winner_ids ?? []);
  const hasShowdownHands = (gameState?.showdown_hands?.length ?? 0) > 0;
  const showdownHandByPlayerId = new Map(
    (gameState?.showdown_hands ?? []).map((hand) => [hand.player_id, hand]),
  );
  const handWinnerIds = (() => {
    if (showdownWinnerIds.size > 0) {
      return showdownWinnerIds;
    }
    if (gameState?.hand_over && !hasShowdownHands) {
      return new Set(
        (gameState.players || [])
          .filter((player) => player.is_playing_round)
          .map((player) => player.player_id),
      );
    }
    return new Set<string>();
  })();
  const yourPlayer =
    gameState && gameState.your_index >= 0
      ? gameState.players[gameState.your_index]
      : null;
  const raiseAdditionalCost = Math.max(
    0,
    betAmount - (yourPlayer?.current_bet_in_round ?? 0),
  );
  const roundBetByPlayerId = (() => {
    if (!gameState) {
      return {} as Record<string, number>;
    }

    const log = gameState.action_log || [];
    const totals: Record<string, number> = {};

    // Current betting street starts after the most recent phase divider.
    let roundStartIndex = 0;
    for (let i = log.length - 1; i >= 0; i -= 1) {
      const entry = log[i];
      if (entry.player_name === null && entry.action.startsWith("---")) {
        roundStartIndex = i + 1;
        break;
      }
    }

    for (let i = roundStartIndex; i < log.length; i += 1) {
      const entry = log[i];
      if (!entry.player_id || entry.amount == null) {
        continue;
      }

      const normalizedAction = entry.action.toLowerCase();
      const contributesChips =
        normalizedAction === "small blind" ||
        normalizedAction === "big blind" ||
        normalizedAction === "call" ||
        normalizedAction === "bet" ||
        normalizedAction === "raise" ||
        normalizedAction === "all-in" ||
        normalizedAction === "all in";

      if (contributesChips) {
        totals[entry.player_id] = (totals[entry.player_id] || 0) + entry.amount;
      }
    }

    return totals;
  })();
  const isHost = Boolean(myPlayerId && room?.host_player_id === myPlayerId);

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

  if (!joinComplete) {
    return (
      <div className="game-room">
        {error && <div className="error-message">{error}</div>}
        <div className="loading">
          <h2>Joining room...</h2>
          <button onClick={handleLeave} className="secondary-button">
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="game-room">
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
                {player.is_agent && isHost ? (
                  <button
                    type="button"
                    className="seat-name seat-name-button"
                    onClick={() =>
                      renameAIPlayer(player.player_id, player.name)
                    }
                    title="Rename AI player"
                  >
                    {player.name}
                  </button>
                ) : (
                  <div className="seat-name">{player.name}</div>
                )}
                <div className="seat-type">
                  {player.is_agent ? "AI" : "Human"}
                </div>
                {isHost && player.player_id !== myPlayerId && (
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
            {isHost && (
              <div className="ai-controls">
                <div className="ai-control-group">
                  <label htmlFor="ai-type-select" className="ai-control-label">
                    AI Type
                  </label>
                  <select
                    id="ai-type-select"
                    className="ai-control-select"
                    value={selectedAiType}
                    onChange={(e) =>
                      setSelectedAiType(e.target.value as "random" | "dqn")
                    }
                  >
                    <option value="random">Random</option>
                    <option value="dqn">DQN (Trained)</option>
                  </select>
                </div>

                {selectedAiType === "dqn" && (
                  <div className="ai-control-group">
                    <label
                      htmlFor="dqn-model-select"
                      className="ai-control-label"
                    >
                      DQN Model
                    </label>
                    <select
                      id="dqn-model-select"
                      className="ai-control-select"
                      value={dqnModelPath}
                      onChange={(e) => setDqnModelPath(e.target.value)}
                      disabled={loadingModels || availableModels.length === 0}
                    >
                      {loadingModels ? (
                        <option value="">Loading models...</option>
                      ) : availableModels.length === 0 ? (
                        <option value="">No models found</option>
                      ) : (
                        availableModels.map((model) => (
                          <option key={model.path} value={model.path}>
                            {model.name}
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                )}
              </div>
            )}

            {isHost && (room?.player_count || 0) < (room?.max_players || 0) && (
              <button
                onClick={addAI}
                className="secondary-button"
                disabled={
                  selectedAiType === "dqn" &&
                  (loadingModels || availableModels.length === 0)
                }
              >
                + Add AI Player
              </button>
            )}
            {isHost && (room?.player_count || 0) >= 2 && (
              <button onClick={startGame} className="primary-button">
                Start Game
              </button>
            )}
          </div>

          <p className="lobby-hint">
            {isHost
              ? "Click an AI name to rename it. Empty seats stay empty when the game starts."
              : "Only the room host can add AI players, rename AI names, and start the game."}
          </p>
        </div>
      )}

      {room?.is_active && gameState && (
        <div className="game-area">
          <div className="game-main">
            {/* Community Cards */}
            <div className="community-area" ref={communityAreaRef}>
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
            </div>

            {/* Action Log */}
            <div
              className="action-log"
              style={
                communityAreaHeight
                  ? {
                      height: `${communityAreaHeight}px`,
                      maxHeight: `${communityAreaHeight}px`,
                    }
                  : undefined
              }
            >
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
            {(gameState.players || []).map((player, idx) => {
              const showdownHand = showdownHandByPlayerId.get(player.player_id);
              const isHandWinner =
                gameState.hand_over && handWinnerIds.has(player.player_id);

              return (
                <div
                  key={player.player_id}
                  className={`player-card ${
                    idx === gameState.dealer_index ? "dealer" : ""
                  } ${idx === gameState.your_index ? "you" : ""} ${
                    isHandWinner ? "hand-winner" : ""
                  }`}
                >
                  <div className="player-name-row">
                    <div className="player-name">
                      {player.name}
                      {idx === gameState.dealer_index && " 🎯"}
                      {idx === gameState.your_index && " (You)"}
                    </div>
                    {isHandWinner && (
                      <div className="player-winner-badge">Winner</div>
                    )}
                  </div>
                  <div className="player-chips">${player.chips}</div>
                  <div className="player-bet">
                    {(roundBetByPlayerId[player.player_id] || 0) > 0 &&
                      `Bet: $${roundBetByPlayerId[player.player_id]}`}
                  </div>
                  {gameState.hand_over && showdownHand ? (
                    <>
                      <div className="player-showdown-cards">
                        {showdownHand.hand.map((card, cardIdx) => (
                          <div
                            key={cardIdx}
                            className={`card tiny ${getSuitColor(card.suit)}`}
                          >
                            <div className="card-value">{card.display}</div>
                          </div>
                        ))}
                      </div>
                      <div className="player-showdown-rank">
                        {showdownHand.hand_rank}
                      </div>
                    </>
                  ) : (
                    <div className="player-cards">
                      {!gameState.hand_over &&
                        player.hand_size > 0 &&
                        `${player.hand_size} card${player.hand_size > 1 ? "s" : ""}`}
                    </div>
                  )}
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
              );
            })}
          </div>

          {/* Your Hand */}
          <div className="your-area">
            <div className="your-area-content">
              {/* Action Buttons */}
              <div className="action-column">
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
                      <div className="action-stack">
                        <div className="action-row action-row-top">
                          {(gameState.available_actions || []).includes(
                            "fold",
                          ) && (
                            <button
                              onClick={() => sendAction("fold")}
                              className="action-button fold"
                            >
                              Fold
                            </button>
                          )}
                          {(gameState.available_actions || []).includes(
                            "check",
                          ) && (
                            <button
                              onClick={() => sendAction("check")}
                              className="action-button check"
                            >
                              Check
                            </button>
                          )}
                          {(gameState.available_actions || []).includes(
                            "call",
                          ) && (
                            <button
                              onClick={() => sendAction("call")}
                              className="action-button call"
                            >
                              Call ${gameState.call_amount || 0}
                            </button>
                          )}
                          {(gameState.available_actions || []).includes(
                            "all_in",
                          ) && (
                            <button
                              onClick={() => sendAction("all_in")}
                              className="action-button all-in"
                              style={{
                                backgroundColor: "#FF9800",
                                fontWeight: "bold",
                              }}
                            >
                              All-In (
                              {gameState.players[gameState.your_index]?.chips ||
                                0}
                              )
                            </button>
                          )}
                        </div>

                        <div className="action-row action-row-bottom">
                          {(gameState.available_actions || []).includes(
                            "bet",
                          ) && (
                            <div className="bet-controls">
                              <input
                                type="number"
                                value={betAmount}
                                onChange={(e) =>
                                  setBetAmount(Number(e.target.value))
                                }
                                min={gameState.big_blind || 10}
                                placeholder="Amount"
                                className="bet-input"
                              />
                              <button
                                onClick={() => sendAction("bet", betAmount)}
                                className="action-button bet"
                                disabled={
                                  betAmount < (gameState.big_blind || 10)
                                }
                              >
                                Bet
                              </button>
                            </div>
                          )}
                          {(gameState.available_actions || []).includes(
                            "raise",
                          ) && (
                            <div className="bet-controls">
                              <input
                                type="number"
                                value={betAmount}
                                onChange={(e) =>
                                  setBetAmount(Number(e.target.value))
                                }
                                min={
                                  (gameState.call_amount || 0) +
                                  (gameState.big_blind || 10)
                                }
                                placeholder="Raise to"
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
                                Raise To ${betAmount || 0}
                              </button>
                              <div className="raise-cost-readout">
                                Additional chips to commit: $
                                {raiseAdditionalCost}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="waiting-turn">Waiting for your turn...</div>
                  )}
                </div>
              </div>

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

              <aside className="bet-tracker" aria-label="Bet tracker">
                <h3>Bet Tracker</h3>
                <div className="bet-tracker-header">
                  <span>Player</span>
                  <span>Round</span>
                  <span>Hand</span>
                </div>
                <div className="bet-tracker-list">
                  {gameState.players.map((player, idx) => (
                    <div
                      key={player.player_id}
                      className={`bet-tracker-row ${
                        idx === gameState.your_index ? "you" : ""
                      }`}
                    >
                      <span className="tracker-player-name">{player.name}</span>
                      <span>
                        $
                        {roundBetByPlayerId[player.player_id] ??
                          player.current_bet_in_round ??
                          0}
                      </span>
                      <span>${player.total_bet_in_hand || 0}</span>
                    </div>
                  ))}
                  {gameState.players.length === 0 && (
                    <div className="bet-tracker-empty">No players yet</div>
                  )}
                </div>
              </aside>
            </div>
          </div>
        </div>
      )}

      <div className="game-footer" role="contentinfo">
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
    </div>
  );
}

export default GameRoom;
