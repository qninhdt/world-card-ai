# World Card AI - Go Backend Server

A high-performance REST API backend for the World Card AI narrative game engine, written in Go.

## Features

- **Game Engine**: Core game loop with state management, card deck, and plot progression
- **Story DAG**: Directed acyclic graph for branching narrative with condition evaluation
- **Card System**: Priority-based deck with choice cards and info cards
- **Death & Resurrection**: Character death detection and resurrection with karma system
- **SQLite Persistence**: Save and load games with full state serialization
- **REST API**: Complete HTTP API for game lifecycle and player actions
- **Claude AI Integration**: Placeholder for world generation and card generation (ready for Anthropic SDK)

## Architecture

```
/server
├── cmd/main.go                 # Entry point
├── internal/
│   ├── game/                   # Game engine, state, events
│   ├── cards/                  # Card models, deck, resolver
│   ├── story/                  # Plot DAG system
│   ├── death/                  # Death detection & resurrection
│   ├── agents/                 # AI agents (Architect, Writer)
│   ├── db/                     # SQLite database layer
│   └── api/                    # REST API routes & handlers
├── go.mod
├── go.sum
├── Dockerfile
└── README.md
```

## Quick Start

### Prerequisites

- Go 1.21+
- SQLite3

### Build

```bash
cd server
go build -o bin/server ./cmd/main.go
```

### Run

```bash
export ANTHROPIC_API_KEY=sk-your-key-here  # Optional for AI features
./bin/server
```

Server starts on `http://localhost:8080`

### Docker

```bash
docker-compose up
```

## API Endpoints

### Game Lifecycle

- `POST /api/games` - Create new game
- `GET /api/games` - List all games
- `GET /api/games/{id}` - Get game state
- `POST /api/games/{id}/save` - Save game
- `POST /api/games/{id}/advance` - Advance week

### Gameplay

- `POST /api/games/{id}/draw` - Draw 7 cards
- `POST /api/games/{id}/resolve` - Resolve card choice
- `POST /api/games/{id}/resurrect` - Resurrect after death

### Visualization

- `GET /api/games/{id}/dag` - Get DAG visualization
- `GET /api/games/{id}/history` - Get game history

## Example: Create a Game

```bash
curl -X POST http://localhost:8080/api/games \
  -H "Content-Type: application/json" \
  -d '{
    "id": "game1",
    "schema": {
      "name": "Test World",
      "era": "Modern",
      "description": "A test world",
      "stats": [{"id": "health", "name": "Health", "description": "Health"}],
      "tags": [],
      "seasons": [],
      "player_character": {"id": "player", "name": "Hero", "description": "You"},
      "npcs": [],
      "relationships": [],
      "plot_nodes": [],
      "initial_stats": {"health": 50},
      "initial_tags": []
    }
  }'
```

## Database

SQLite database is created automatically at `game.db` (or path specified by `DB_PATH` env var).

Schema includes:
- `games` - Game metadata
- `game_states` - Snapshots of game state
- `dag_nodes` - Plot nodes
- `dag_edges` - Plot connections

## State Persistence

Unlike the Python version, the Go backend:
- ✅ Saves the complete DAG graph with each game state
- ✅ Persists all stats, tags, events, and NPC state
- ✅ Supports full game restoration from database
- ✅ Uses JSON serialization for complex objects

## Performance

- Priority queue deck operations: O(n log n)
- DAG condition evaluation: O(1) with pre-compiled expressions
- State updates: O(1) for most operations
- Database transactions: Atomic per save

## Next Steps

1. **Implement Claude API Integration**: Replace placeholder agents with real Anthropic SDK calls
2. **Add PostgreSQL Support**: Extend DB layer for production deployments
3. **Implement Card Generation Pipeline**: Batch card generation with Writer agent
4. **Add Event System**: Full event lifecycle management
5. **Add Tests**: Unit and integration tests for all systems
6. **Add Authentication**: JWT-based API authentication
7. **Add WebSocket Support**: Real-time game updates

## Development

### Run Tests

```bash
go test ./...
```

### Build Docker Image

```bash
docker build -t world-card-ai-server .
```

### Environment Variables

- `PORT` - Server port (default: 8080)
- `DB_PATH` - SQLite database path (default: game.db)
- `ANTHROPIC_API_KEY` - Claude API key (optional)

## License

MIT
