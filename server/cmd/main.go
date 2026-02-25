package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/qninhdt/world-card-ai-2/server/internal/api"
	"github.com/qninhdt/world-card-ai-2/server/internal/db"
)

func main() {
	// Get configuration from environment
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "game.db"
	}

	// Initialize database
	database, err := db.NewDB(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Create API server
	server := api.NewServer(database)

	// Start HTTP server
	addr := fmt.Sprintf(":%s", port)
	log.Printf("Starting server on %s", addr)

	if err := http.ListenAndServe(addr, server); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
