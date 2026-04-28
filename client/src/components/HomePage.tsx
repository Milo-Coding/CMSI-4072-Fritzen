import { useState, useEffect } from "react";
import "./HomePage.css";

type HomePageView = "home" | "create" | "browse";

interface RoomApi {
  id?: string;
  room_id?: string;
  name: string;
  player_count: number;
  max_players: number;
  small_blind: number;
  big_blind: number;
  status?: string;
  phase?: string;
  is_active?: boolean;
}

interface Room {
  id: string;
  name: string;
  player_count: number;
  max_players: number;
  small_blind: number;
  big_blind: number;
  status: "waiting" | "playing";
}

interface RoomConfig {
  name?: string;
  small_blind: number;
  big_blind?: number;
  min_players: number;
  starting_chips: number;
}

const API_BASE = import.meta.env.DEV
  ? "/api"
  : (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000/api");

const getNetworkErrorMessage = (err: unknown, action: string): string => {
  const fallback = `Unable to ${action}. Check that the API is running and reachable at ${API_BASE}.`;
  if (!(err instanceof Error)) {
    return fallback;
  }

  if (err.name === "TypeError" && err.message.toLowerCase().includes("fetch")) {
    return fallback;
  }

  return err.message || fallback;
};

interface HomePageProps {
  onJoinRoom: (roomId: string, playerName: string) => void;
  initialView?: HomePageView;
  initialError?: string | null;
  initialPlayerName?: string;
}

const normalizeRoomStatus = (
  status?: string,
  phase?: string,
  isActive?: boolean,
): "waiting" | "playing" => {
  const normalized = (status ?? phase ?? "").toLowerCase();
  if (normalized === "waiting") {
    return "waiting";
  }
  if (normalized) {
    return "playing";
  }
  return isActive ? "playing" : "waiting";
};

const normalizeRooms = (rawRooms: RoomApi[]): Room[] => {
  return rawRooms
    .map((room): Room | null => {
      const id = room.id ?? room.room_id;
      if (!id) {
        return null;
      }

      return {
        id,
        name: room.name,
        player_count: room.player_count,
        max_players: room.max_players,
        small_blind: room.small_blind,
        big_blind: room.big_blind ?? room.small_blind * 2,
        status: normalizeRoomStatus(room.status, room.phase, room.is_active),
      };
    })
    .filter((room): room is Room => room !== null);
};

function HomePage({
  onJoinRoom,
  initialView = "home",
  initialError = null,
  initialPlayerName = "",
}: HomePageProps) {
  const [view, setView] = useState<HomePageView>(initialView);
  const [playerName, setPlayerName] = useState(initialPlayerName);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(initialError);

  // Form state
  const [roomName, setRoomName] = useState("");
  const [smallBlind, setSmallBlind] = useState(10);
  const [bigBlind, setBigBlind] = useState(20);
  const [startingChips, setStartingChips] = useState(1000);

  useEffect(() => {
    setView(initialView);
  }, [initialView]);

  useEffect(() => {
    setError(initialError);
  }, [initialError]);

  useEffect(() => {
    setPlayerName(initialPlayerName);
  }, [initialPlayerName]);

  useEffect(() => {
    const wakeBackend = async () => {
      try {
        await fetch(`${API_BASE}/rooms`, { method: "GET", keepalive: true });
      } catch (err) {
        console.warn("Backend wake-up ping failed:", err);
      }
    };

    wakeBackend();
  }, []);

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
      if (!response.ok) {
        throw new Error(`Failed to fetch rooms (${response.status})`);
      }
      const data = await response.json();
      setRooms(normalizeRooms(data.rooms || []));
    } catch (err) {
      setError(getNetworkErrorMessage(err, "load rooms"));
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
      starting_chips: startingChips,
    };

    try {
      const response = await fetch(`${API_BASE}/rooms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const details = await response.text();
        throw new Error(
          `Failed to create room (${response.status})${details ? `: ${details}` : ""}`,
        );
      }

      const room = await response.json();
      // Auto-join the created room
      onJoinRoom(room.id, playerName);
    } catch (err) {
      setError(getNetworkErrorMessage(err, "create a room"));
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

          <p className="form-hint">All rooms are created with 6 seats.</p>

          <button
            onClick={createRoom}
            disabled={loading}
            className="primary-button"
          >
            {loading ? "Creating..." : "Create Room & Enter Lobby"}
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
              <div key={room.id} className="room-card">
                <div className="room-header">
                  <h3>{room.name || `Room ${room.id.slice(0, 6)}`}</h3>
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
                  onClick={() => joinRoom(room.id)}
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
