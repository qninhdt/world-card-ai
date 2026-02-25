package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
	"github.com/qninhdt/world-card-ai-2/server/internal/game"
)

// Example demonstrates using the OpenRouter API integration
func main() {
	// Check for API key
	apiKey := os.Getenv("OPENROUTER_API_KEY")
	if apiKey == "" {
		log.Fatal("OPENROUTER_API_KEY environment variable not set")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// Example 1: Generate a world
	fmt.Println("=== Generating World ===")
	architect := agents.NewArchitectAgent()

	worldPrompt := `Create a fantasy world with:
- A medieval setting with magic
- Conflict between kingdoms
- Ancient prophecies
- Mysterious artifacts`

	schema, err := architect.GenerateWorld(ctx, worldPrompt)
	if err != nil {
		log.Fatalf("Failed to generate world: %v", err)
	}

	fmt.Printf("World: %s\n", schema.Name)
	fmt.Printf("Era: %s\n", schema.Era)
	fmt.Printf("Stats: %d\n", len(schema.Stats))
	fmt.Printf("NPCs: %d\n", len(schema.NPCs))
	fmt.Printf("Plot Nodes: %d\n", len(schema.PlotNodes))

	// Example 2: Create a game with the generated world
	fmt.Println("\n=== Creating Game ===")
	gameID := fmt.Sprintf("game_%d", time.Now().Unix())
	engine, err := game.NewGameEngine(gameID, schema)
	if err != nil {
		log.Fatalf("Failed to create game: %v", err)
	}

	fmt.Printf("Game ID: %s\n", gameID)
	fmt.Printf("Game State: %+v\n", engine.GetGameInfo())

	// Example 3: Generate cards for the game
	fmt.Println("\n=== Generating Cards ===")
	writer := agents.NewWriterAgent()

	jobs := []agents.CardGenJob{
		{
			Type: "plot",
			Context: map[string]interface{}{
				"node_id":       schema.PlotNodes[0].ID,
				"description":   schema.PlotNodes[0].PlotDescription,
				"world":         schema.Name,
			},
		},
		{
			Type: "info",
			Context: map[string]interface{}{
				"world": schema.Name,
				"topic": "world_lore",
			},
		},
	}

	worldContext := map[string]interface{}{
		"world_name": schema.Name,
		"era":        schema.Era,
		"npcs":       len(schema.NPCs),
		"stats":      len(schema.Stats),
	}

	cards, err := writer.GenerateCards(ctx, jobs, worldContext)
	if err != nil {
		log.Fatalf("Failed to generate cards: %v", err)
	}

	fmt.Printf("Generated %d cards\n", len(cards))
	for i, card := range cards {
		fmt.Printf("  Card %d: %s (priority: %d)\n", i+1, card.GetTitle(), card.GetPriority())
	}

	// Example 4: Test the API endpoint
	fmt.Println("\n=== Testing API Endpoint ===")
	testAPIEndpoint(gameID, schema)
}

// testAPIEndpoint demonstrates calling the REST API
func testAPIEndpoint(gameID string, schema *agents.WorldGenSchema) {
	// Create game via API
	createReq := map[string]interface{}{
		"id":     gameID,
		"schema": schema,
	}

	body, _ := json.Marshal(createReq)
	resp, err := http.Post(
		"http://localhost:8080/api/games",
		"application/json",
		bytes.NewReader(body),
	)

	if err != nil {
		fmt.Printf("API call failed (server not running?): %v\n", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusCreated {
		fmt.Printf("✓ Game created via API: %s\n", gameID)
	} else {
		fmt.Printf("✗ API returned status %d\n", resp.StatusCode)
	}

	// Get game state
	resp, err = http.Get(fmt.Sprintf("http://localhost:8080/api/games/%s", gameID))
	if err == nil && resp.StatusCode == http.StatusOK {
		fmt.Printf("✓ Game state retrieved\n")
		resp.Body.Close()
	}
}

// Example usage:
// 1. Set API key:
//    export OPENROUTER_API_KEY=sk-or-v1-xxxxx
//
// 2. Run example:
//    go run examples/openrouter_example.go
//
// 3. Expected output:
//    === Generating World ===
//    World: [Generated world name]
//    Era: [Generated era]
//    Stats: 5-8
//    NPCs: 5-8
//    Plot Nodes: 8-15
//
//    === Creating Game ===
//    Game ID: game_1708700000
//    Game State: {...}
//
//    === Generating Cards ===
//    Generated 2 cards
//      Card 1: [Generated title] (priority: 3)
//      Card 2: [Generated title] (priority: 1)
//
//    === Testing API Endpoint ===
//    ✓ Game created via API: game_1708700000
//    ✓ Game state retrieved
