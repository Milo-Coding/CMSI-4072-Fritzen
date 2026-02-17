import { useState, useEffect } from "react";
import "./HomePage.css";

interface Room {
  room_id: string;
  name: string;
  player_count: number;
  max_players: number;
  small_blind: number;
  big_blind: number;
  status: string;
}

interface RoomConfig {
  name?: string;
  small_blind: number;
  big_blind?: number;
  min_players: number;
  max_players: number;
  starting_chips: number;
  ai_players: number;
  ai_type: string;
}

const API_BASE = "http://localhost:8000/api";

interface HomePageProps {
  onJoinRoom: (roomId: string, playerName: string) => void;
}

function HomePage({ onJoinRoom }: HomePageProps) {
  const [view, setView] = useState<"home" | "create" | "browse">("home");
  const [playerName, setPlayerName] = useState("");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [roomName, setRoomName] = useState("");
  const [smallBlind, setSmallBlind] = useState(10);
  const [bigBlind, setBigBlind] = useState(20);
  const [maxPlayers, setMaxPlayers] = useState(6);
  const [startingChips, setStartingChips] = useState(1000);
  const [aiPlayers, setAiPlayers] = useState(0);
  const [aiType, setAiType] = useState("random");

  useEffect(() => {
    if (view === "browse") {
      fetchRooms();
    }
  }, [view]);

  const fetchRooms = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/rooms`);
      if (!response.ok) throw new Error("Failed to fetch rooms");
      const data = await response.json();
      setRooms(data.rooms || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rooms");
    } finally {
      setLoading(false);
    }
  };

  const createRoom = async () => {
    if (!playerName.trim()) {
      setError("Please enter your name");
      return;
    }

    setLoading(true);
    setError(null);

    const config: RoomConfig = {
      name: roomName || undefined,
      small_blind: smallBlind,
      big_blind: bigBlind,
      min_players: 2,
      max_players: maxPlayers,
      starting_chips: startingChips,
      ai_players: aiPlayers,
      ai_type: aiType,
    };

    try {
      const response = await fetch(`${API_BASE}/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) throw new Error("Failed to create room");

      const room = await response.json();
      // Auto-join the created room
      onJoinRoom(room.id, playerName);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create room");
    } finally {
      setLoading(false);
    }
  };

  const joinRoom = (roomId: string) => {
    if (!playerName.trim()) {
      setError("Please enter your name");
      return;
    }
    onJoinRoom(roomId, playerName);
  };

  if (view === "create") {
    return (
      <div className="home-page">
        <div className="header">
          <button onClick={() => setView("home")} className="back-button">
            ← Back
          </button>
          <h1>Create Room</h1>
        </div>

        <div className="create-room-form">
          {error && <div className="error-message">{error}</div>}

          <div className="form-group">
            <label htmlFor="player-name">Your Name *</label>
            <input
              id="player-name"
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              placeholder="Enter your name"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="room-name">Room Name (optional)</label>
            <input
              id="room-name"
              type="text"
              value={roomName}
              onChange={(e) => setRoomName(e.target.value)}
              placeholder="My Poker Room"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="small-blind">Small Blind</label>
              <input
                id="small-blind"
                type="number"
                value={smallBlind}
                onChange={(e) => setSmallBlind(Number(e.target.value))}
                min="1"
              />
            </div>

            <div className="form-group">
              <label htmlFor="big-blind">Big Blind</label>
              <input
                id="big-blind"
                type="number"
                value={bigBlind}
                onChange={(e) => setBigBlind(Number(e.target.value))}
                min="1"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="max-players">Max Players</label>
              <input
                id="max-players"
                type="number"
                value={maxPlayers}
                onChange={(e) => setMaxPlayers(Number(e.target.value))}
                min="2"
                max="12"
              />
            </div>

            <div className="form-group">
              <label htmlFor="starting-chips">Starting Chips</label>
              <input
                id="starting-chips"
                type="number"
                value={startingChips}
                onChange={(e) => setStartingChips(Number(e.target.value))}
                min="100"
                step="100"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="ai-players">AI Players</label>
              <input
                id="ai-players"
                type="number"
                value={aiPlayers}
                onChange={(e) => setAiPlayers(Number(e.target.value))}
                min="0"
                max="11"
              />
            </div>

            <div className="form-group">
              <label htmlFor="ai-type">AI Type</label>
              <select
                id="ai-type"
                value={aiType}
                onChange={(e) => setAiType(e.target.value)}
              >
                <option value="random">Random</option>
                <option value="dqn">DQN (Trained)</option>
              </select>
            </div>
          </div>

          <button
            onClick={createRoom}
            disabled={loading}
            className="primary-button"
          >
            {loading ? "Creating..." : "Create Room"}
          </button>
        </div>
      </div>
    );
  }

  if (view === "browse") {
    return (
      <div className="home-page">
        <div className="header">
          <button onClick={() => setView("home")} className="back-button">
            ← Back
          </button>
          <h1>Available Rooms</h1>
          <button onClick={fetchRooms} className="refresh-button">
            ↻ Refresh
          </button>
        </div>

        <div
          className="form-group"
          style={{ maxWidth: "400px", margin: "0 auto 2rem" }}
        >
          <label htmlFor="browse-player-name">Your Name *</label>
          <input
            id="browse-player-name"
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            placeholder="Enter your name"
            required
          />
        </div>

        {error && <div className="error-message">{error}</div>}

        {loading ? (
          <div className="loading">Loading rooms...</div>
        ) : rooms.length === 0 ? (
          <div className="empty-state">
            <p>No rooms available</p>
            <button
              onClick={() => setView("create")}
              className="primary-button"
            >
              Create First Room
            </button>
          </div>
        ) : (
          <div className="rooms-grid">
            {rooms.map((room) => (
              <div key={room.room_id} className="room-card">
                <div className="room-header">
                  <h3>{room.name || `Room ${room.room_id.slice(0, 6)}`}</h3>
                  <span className={`status-badge ${room.status}`}>
                    {room.status}
                  </span>
                </div>

                <div className="room-info">
                  <div className="info-row">
                    <span className="label">Players:</span>
                    <span className="value">
                      {room.player_count} / {room.max_players}
                    </span>
                  </div>
                  <div className="info-row">
                    <span className="label">Blinds:</span>
                    <span className="value">
                      {room.small_blind} / {room.big_blind}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => joinRoom(room.room_id)}
                  className="join-button"
                  disabled={room.player_count >= room.max_players}
                >
                  {room.player_count >= room.max_players ? "Full" : "Join Room"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Home view
  return (
    <div className="home-page">
      <div className="hero">
        <h1 className="title">♠️ MultiplAIyer Poker ♥️</h1>
        <p className="subtitle">Play Texas Hold'em with friends online</p>
      </div>

      <div className="action-cards">
        <div className="action-card" onClick={() => setView("create")}>
          <div className="card-icon">+</div>
          <h2>Create Room</h2>
          <p>Start a new poker game and invite friends</p>
          <button className="card-button">Create</button>
        </div>

        <div className="action-card" onClick={() => setView("browse")}>
          <div className="card-icon">🎲</div>
          <h2>Join Room</h2>
          <p>Browse and join existing poker games</p>
          <button className="card-button">Browse</button>
        </div>
      </div>

      <div className="footer">
        <p>Built with React + FastAPI + WebSockets</p>
      </div>
    </div>
  );
}

export default HomePage;
