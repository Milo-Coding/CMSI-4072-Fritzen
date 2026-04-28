# MultiplAIyer Poker

Play Texas Hold'em with friends in real time. The app includes a React client, a FastAPI backend, and WebSocket-based gameplay with optional AI opponents (random or DQN models).

## Online Version

- https://pokerface-zeta.vercel.app/

## Features

- Create rooms with configurable blinds and starting chips
- Real-time lobby and gameplay over WebSockets
- Human and AI players (random or DQN)
- Action log, side pots, and showdown display

## Tech Stack

- Frontend: React + Vite + TypeScript
- Backend: FastAPI + WebSockets
- AI: DQN models (.pth) served by backend

## Project Structure

- client/ - React UI
- server/ - FastAPI + game engine + WebSocket API
- docs/ - Course deliverables and feedback

## Local Development

### Backend

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs at http://localhost:8000

### Frontend

```bash
cd client
npm install
npm run dev
```

Open http://localhost:5173

The frontend expects the backend at http://localhost:8000 (REST) and ws://localhost:8000 (WebSocket).

## Tests

```bash
cd server
pytest
```

## Notes

- Room list data comes from the REST API; live game state comes from WebSockets.
- If you change backend ports, update VITE_API_BASE and VITE_WS_BASE in the client environment.
