package db

import (
	"database/sql"
	"encoding/json"
	"sync"

	_ "github.com/mattn/go-sqlite3"
	"github.com/qninhdt/world-card-ai-2/server/internal/game"
	"github.com/qninhdt/world-card-ai-2/server/internal/story"
)

// DB wraps database operations
type DB struct {
	conn *sql.DB
	mu   sync.RWMutex
}

// NewDB creates a new database connection
func NewDB(dbPath string) (*DB, error) {
	conn, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}

	if err := conn.Ping(); err != nil {
		return nil, err
	}

	db := &DB{conn: conn}

	// Run migrations
	if err := db.migrate(); err != nil {
		return nil, err
	}

	return db, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.conn.Close()
}

// migrate runs database migrations
func (db *DB) migrate() error {
	schema := `
	CREATE TABLE IF NOT EXISTS games (
		id TEXT PRIMARY KEY,
		name TEXT NOT NULL,
		era TEXT NOT NULL,
		year INTEGER NOT NULL,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS game_states (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		game_id TEXT NOT NULL,
		day INTEGER NOT NULL,
		season INTEGER NOT NULL,
		year_in_game INTEGER NOT NULL,
		stats_json TEXT NOT NULL,
		tags_json TEXT NOT NULL,
		events_json TEXT NOT NULL,
		dag_json TEXT NOT NULL,
		is_alive INTEGER NOT NULL,
		current_life INTEGER NOT NULL,
		death_cause TEXT,
		death_turn INTEGER,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS dag_nodes (
		id TEXT PRIMARY KEY,
		game_id TEXT NOT NULL,
		plot_description TEXT NOT NULL,
		condition TEXT,
		calls_json TEXT,
		is_ending INTEGER NOT NULL,
		is_fired INTEGER NOT NULL,
		predecessor_ids_json TEXT,
		successor_ids_json TEXT,
		FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
	);

	CREATE TABLE IF NOT EXISTS dag_edges (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		game_id TEXT NOT NULL,
		from_node_id TEXT NOT NULL,
		to_node_id TEXT NOT NULL,
		FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
		FOREIGN KEY (from_node_id) REFERENCES dag_nodes(id),
		FOREIGN KEY (to_node_id) REFERENCES dag_nodes(id)
	);

	CREATE TABLE IF NOT EXISTS game_ownership (
		game_id TEXT PRIMARY KEY,
		user_id TEXT NOT NULL,
		created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
	);

	CREATE INDEX IF NOT EXISTS idx_game_states_game_id ON game_states(game_id);
	CREATE INDEX IF NOT EXISTS idx_dag_nodes_game_id ON dag_nodes(game_id);
	CREATE INDEX IF NOT EXISTS idx_dag_edges_game_id ON dag_edges(game_id);
	CREATE INDEX IF NOT EXISTS idx_game_ownership_user_id ON game_ownership(user_id);
	`

	_, err := db.conn.Exec(schema)
	return err
}

// SaveGameOwnership saves game ownership
func (db *DB) SaveGameOwnership(gameID, userID string) error {
	db.mu.Lock()
	defer db.mu.Unlock()

	_, err := db.conn.Exec(`
		INSERT OR REPLACE INTO game_ownership (game_id, user_id)
		VALUES (?, ?)
	`, gameID, userID)
	return err
}

// GetGameOwner returns the owner of a game
func (db *DB) GetGameOwner(gameID string) (string, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()

	var userID string
	err := db.conn.QueryRow(`
		SELECT user_id FROM game_ownership WHERE game_id = ?
	`, gameID).Scan(&userID)

	if err != nil {
		return "", err
	}
	return userID, nil
}

// IsGameOwner checks if user owns the game
func (db *DB) IsGameOwner(gameID, userID string) (bool, error) {
	owner, err := db.GetGameOwner(gameID)
	if err != nil {
		return false, err
	}
	return owner == userID, nil
}

// GetUserGames returns all games owned by a user
func (db *DB) GetUserGames(userID string) ([]string, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()

	rows, err := db.conn.Query(`
		SELECT game_id FROM game_ownership WHERE user_id = ? ORDER BY created_at DESC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var gameIDs []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		gameIDs = append(gameIDs, id)
	}

	return gameIDs, rows.Err()
}

// SaveGame saves a game and its state
func (db *DB) SaveGame(gameID string, state *game.GlobalBlackboard, dag *story.MacroDAG) error {
	db.mu.Lock()
	defer db.mu.Unlock()

	tx, err := db.conn.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Upsert game
	_, err = tx.Exec(`
		INSERT INTO games (id, name, era, year, created_at, updated_at)
		VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
		ON CONFLICT(id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
	`, gameID, state.WorldName, state.Era, state.Year)
	if err != nil {
		return err
	}

	// Serialize state
	statsJSON, _ := json.Marshal(state.Stats)
	tagsJSON, _ := json.Marshal(state.Tags)
	eventsJSON, _ := json.Marshal(state.Events)
	dagJSON, _ := json.Marshal(dag)

	// Insert game state
	_, err = tx.Exec(`
		INSERT INTO game_states (
			game_id, day, season, year_in_game, stats_json, tags_json, events_json, dag_json,
			is_alive, current_life, death_cause, death_turn
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`, gameID, state.Day, state.Season, state.Year, statsJSON, tagsJSON, eventsJSON, dagJSON,
		boolToInt(state.IsAlive), state.CurrentLife, state.DeathCause, state.DeathTurn)
	if err != nil {
		return err
	}

	// Save DAG nodes
	for _, node := range dag.GetAllNodes() {
		callsJSON, _ := json.Marshal(node.Calls)
		predJSON, _ := json.Marshal(node.PredecessorIDs)
		succJSON, _ := json.Marshal(node.SuccessorIDs)

		_, err = tx.Exec(`
			INSERT OR REPLACE INTO dag_nodes (
				id, game_id, plot_description, condition, calls_json, is_ending, is_fired,
				predecessor_ids_json, successor_ids_json
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		`, node.ID, gameID, node.PlotDescription, node.Condition, callsJSON,
			boolToInt(node.IsEnding), boolToInt(node.IsFired), predJSON, succJSON)
		if err != nil {
			return err
		}
	}

	return tx.Commit()
}

// LoadGame loads a game and its latest state
func (db *DB) LoadGame(gameID string) (*game.GlobalBlackboard, *story.MacroDAG, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()

	// Load latest game state
	var (
		day, season, yearInGame, isAlive, currentLife, deathTurn int
		statsJSON, tagsJSON, eventsJSON, dagJSON                 string
		deathCause                                               sql.NullString
	)

	err := db.conn.QueryRow(`
		SELECT day, season, year_in_game, stats_json, tags_json, events_json, dag_json,
		       is_alive, current_life, death_cause, death_turn
		FROM game_states
		WHERE game_id = ?
		ORDER BY created_at DESC
		LIMIT 1
	`, gameID).Scan(&day, &season, &yearInGame, &statsJSON, &tagsJSON, &eventsJSON, &dagJSON,
		&isAlive, &currentLife, &deathCause, &deathTurn)

	if err != nil {
		return nil, nil, err
	}

	// Deserialize state
	state := &game.GlobalBlackboard{}
	if err := json.Unmarshal([]byte(statsJSON), &state.Stats); err != nil {
		return nil, nil, err
	}
	if err := json.Unmarshal([]byte(tagsJSON), &state.Tags); err != nil {
		return nil, nil, err
	}
	if err := json.Unmarshal([]byte(eventsJSON), &state.Events); err != nil {
		return nil, nil, err
	}

	state.Day = day
	state.Season = season
	state.Year = yearInGame
	state.IsAlive = intToBool(isAlive)
	state.CurrentLife = currentLife
	if deathCause.Valid {
		state.DeathCause = deathCause.String
	}
	state.DeathTurn = deathTurn

	// Deserialize DAG
	dag := story.NewMacroDAG()
	if err := json.Unmarshal([]byte(dagJSON), dag); err != nil {
		return nil, nil, err
	}

	return state, dag, nil
}

// GetGameList returns all game IDs
func (db *DB) GetGameList() ([]string, error) {
	db.mu.RLock()
	defer db.mu.RUnlock()

	rows, err := db.conn.Query("SELECT id FROM games ORDER BY updated_at DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var gameIDs []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		gameIDs = append(gameIDs, id)
	}

	return gameIDs, rows.Err()
}

// DeleteGame deletes a game and all its data
func (db *DB) DeleteGame(gameID string) error {
	db.mu.Lock()
	defer db.mu.Unlock()

	_, err := db.conn.Exec("DELETE FROM games WHERE id = ?", gameID)
	return err
}

// Helper functions
func boolToInt(b bool) int {
	if b {
		return 1
	}
	return 0
}

func intToBool(i int) bool {
	return i != 0
}
