package api

import (
	"encoding/json"
	"net/http"
	"sync"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/google/uuid"
	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
	"github.com/qninhdt/world-card-ai-2/server/internal/db"
	"github.com/qninhdt/world-card-ai-2/server/internal/game"
	mw "github.com/qninhdt/world-card-ai-2/server/internal/middleware"
	"github.com/qninhdt/world-card-ai-2/server/internal/validation"
)

// Server handles HTTP requests
type Server struct {
	router      chi.Router
	db          *db.DB
	games       map[string]*game.GameEngine
	gamesMu     sync.RWMutex
	rateLimiter *mw.RateLimiter
}

// NewServer creates a new API server
func NewServer(database *db.DB) *Server {
	s := &Server{
		router:      chi.NewRouter(),
		db:          database,
		games:       make(map[string]*game.GameEngine),
		rateLimiter: mw.NewRateLimiter(),
	}

	s.setupRoutes()
	return s
}

// setupRoutes configures all API routes
func (s *Server) setupRoutes() {
	s.router.Use(middleware.Logger)
	s.router.Use(middleware.Recoverer)
	s.router.Use(middleware.SetHeader("Content-Type", "application/json"))
	s.router.Use(s.rateLimiter.Middleware)
	s.router.Use(mw.SecurityHeadersMiddleware)
	s.router.Use(mw.MaxBodySizeMiddleware(1024 * 1024)) // 1MB max

	// Public endpoint (no auth required)
	s.router.Post("/api/games", s.createGame)

	// Protected endpoints (auth required)
	s.router.Group(func(r chi.Router) {
		r.Use(mw.AuthMiddleware)
		r.Get("/api/games", s.listGames)
		r.Get("/api/games/{id}", s.getGame)
		r.Post("/api/games/{id}/save", s.saveGame)
		r.Post("/api/games/{id}/draw", s.drawCards)
		r.Post("/api/games/{id}/resolve", s.resolveCard)
		r.Post("/api/games/{id}/advance", s.advanceWeek)
		r.Get("/api/games/{id}/dag", s.getDAG)
		r.Post("/api/games/{id}/resurrect", s.resurrect)
		r.Get("/api/games/{id}/history", s.getHistory)
	})
}

// ServeHTTP implements http.Handler
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.router.ServeHTTP(w, r)
}

// Response wraps API responses
type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}

// writeJSON writes a JSON response
func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes an error response (sanitized)
func writeError(w http.ResponseWriter, status int, message string) {
	// SECURITY FIX: Sanitize error messages
	if status >= 500 {
		message = "Internal server error"
	}
	writeJSON(w, status, Response{
		Success: false,
		Error:   message,
	})
}

// getUserID extracts user ID from context
func getUserID(r *http.Request) string {
	userID, ok := r.Context().Value("user_id").(string)
	if !ok {
		return ""
	}
	return userID
}

// checkGameOwnership verifies user owns the game
func (s *Server) checkGameOwnership(w http.ResponseWriter, r *http.Request, gameID string) bool {
	userID := getUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "Missing user ID")
		return false
	}

	isOwner, err := s.db.IsGameOwner(gameID, userID)
	if err != nil || !isOwner {
		writeError(w, http.StatusForbidden, "Access denied")
		return false
	}
	return true
}

// createGame creates a new game
func (s *Server) createGame(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Schema *agents.WorldGenSchema `json:"schema"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	if req.Schema == nil {
		writeError(w, http.StatusBadRequest, "Missing schema")
		return
	}

	// SECURITY FIX: Generate server-side game ID (don't trust client)
	gameID := uuid.New().String()

	engine, err := game.NewGameEngine(gameID, req.Schema)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to create game")
		return
	}

	s.gamesMu.Lock()
	s.games[gameID] = engine
	s.gamesMu.Unlock()

	// SECURITY FIX: Save game ownership (for public endpoint, use empty user ID)
	// In production, you might want to require auth for game creation
	if err := s.db.SaveGameOwnership(gameID, "public"); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to save game")
		return
	}

	writeJSON(w, http.StatusCreated, Response{
		Success: true,
		Data:    engine.GetGameInfo(),
	})
}

// listGames lists all games owned by the user
func (s *Server) listGames(w http.ResponseWriter, r *http.Request) {
	userID := getUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "Missing user ID")
		return
	}

	gameIDs, err := s.db.GetUserGames(userID)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to list games")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    gameIDs,
	})
}

// getGame gets a game's current state
func (s *Server) getGame(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data: map[string]interface{}{
			"info":  engine.GetGameInfo(),
			"state": engine.GetState(),
		},
	})
}

// saveGame saves a game
func (s *Server) saveGame(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	if err := s.db.SaveGame(gameID, engine.GetState(), engine.GetDAG()); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to save game")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    "Game saved",
	})
}

// drawCards draws cards for the week
func (s *Server) drawCards(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	cards, err := engine.DrawCards(7)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to draw cards")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    cards,
	})
}

// resolveCard resolves a card choice
func (s *Server) resolveCard(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	var req struct {
		CardID    string `json:"card_id"`
		Direction string `json:"direction"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// SECURITY FIX: Validate card ID and direction
	if err := validation.ValidateCardID(req.CardID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid card ID")
		return
	}

	if err := validation.ValidateDirection(req.Direction); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid direction")
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	result, err := engine.ResolveCard(req.CardID, req.Direction)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Failed to resolve card")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    result,
	})
}

// advanceWeek advances the game by one week
func (s *Server) advanceWeek(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	if err := engine.AdvanceWeek(); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to advance week")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    engine.GetGameInfo(),
	})
}

// getDAG returns the DAG visualization
func (s *Server) getDAG(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	dag := engine.GetDAG()
	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    dag.GetVisualGraph(),
	})
}

// resurrect resurrects the player
func (s *Server) resurrect(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	var req struct {
		TempTags map[string]bool `json:"temp_tags"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	if err := engine.Resurrect(req.TempTags); err != nil {
		writeError(w, http.StatusInternalServerError, "Failed to resurrect")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data:    engine.GetGameInfo(),
	})
}

// getHistory returns game history
func (s *Server) getHistory(w http.ResponseWriter, r *http.Request) {
	gameID := chi.URLParam(r, "id")

	// SECURITY FIX: Validate game ID format
	if err := validation.ValidateGameID(gameID); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid game ID")
		return
	}

	// SECURITY FIX: Check game ownership
	if !s.checkGameOwnership(w, r, gameID) {
		return
	}

	s.gamesMu.RLock()
	engine, ok := s.games[gameID]
	s.gamesMu.RUnlock()

	if !ok {
		writeError(w, http.StatusNotFound, "Game not found")
		return
	}

	writeJSON(w, http.StatusOK, Response{
		Success: true,
		Data: map[string]interface{}{
			"game_info": engine.GetGameInfo(),
			"state":     engine.GetState(),
		},
	})
}
