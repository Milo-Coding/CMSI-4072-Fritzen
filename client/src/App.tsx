import { useState } from "react";
import HomePage from "./components/HomePage";
import GameRoom from "./components/GameRoom";

interface GameSession {
  roomId: string;
  playerName: string;
}

function App() {
  const [gameSession, setGameSession] = useState<GameSession | null>(null);

  const handleJoinRoom = (roomId: string, playerName: string) => {
    setGameSession({ roomId, playerName });
  };

  const handleLeaveRoom = () => {
    setGameSession(null);
  };

  return (
    <div className="app">
      {gameSession ? (
        <GameRoom
          roomId={gameSession.roomId}
          playerName={gameSession.playerName}
          onLeave={handleLeaveRoom}
        />
      ) : (
        <HomePage onJoinRoom={handleJoinRoom} />
      )}
    </div>
  );
}

export default App;
