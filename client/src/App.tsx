import { useState } from "react";
import HomePage from "./components/HomePage";
import GameRoom from "./components/GameRoom";

interface GameSession {
  roomId: string;
  playerName: string;
}

type HomePageView = "home" | "create" | "browse";

interface LeaveRoomOptions {
  destinationView?: HomePageView;
  errorMessage?: string;
  playerName?: string;
}

interface HomePageState {
  view: HomePageView;
  error: string | null;
  playerName: string;
}

function App() {
  const [gameSession, setGameSession] = useState<GameSession | null>(null);
  const [homePageState, setHomePageState] = useState<HomePageState>({
    view: "home",
    error: null,
    playerName: "",
  });

  const handleJoinRoom = (roomId: string, playerName: string) => {
    setHomePageState({
      view: "home",
      error: null,
      playerName,
    });
    setGameSession({ roomId, playerName });
  };

  const handleLeaveRoom = (options?: LeaveRoomOptions) => {
    setHomePageState({
      view: options?.destinationView ?? "home",
      error: options?.errorMessage ?? null,
      playerName: options?.playerName ?? "",
    });
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
        <HomePage
          onJoinRoom={handleJoinRoom}
          initialView={homePageState.view}
          initialError={homePageState.error}
          initialPlayerName={homePageState.playerName}
        />
      )}
    </div>
  );
}

export default App;
