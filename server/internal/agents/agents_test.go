package agents

import (
	"context"
	"encoding/json"
	"testing"
	"time"
)

// TestOpenRouterClient tests the OpenRouter client
func TestOpenRouterClient(t *testing.T) {
	client := NewOpenRouterClient()

	if client.apiKey == "" {
		t.Skip("OPENROUTER_API_KEY not set, skipping integration test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	req := &CompletionRequest{
		Model:     "claude-3-5-sonnet-20241022",
		MaxTokens: 100,
		Messages: []Message{
			{
				Role:    "user",
				Content: "Say 'Hello' in JSON format: {\"greeting\": \"...\"}",
			},
		},
	}

	resp, err := client.CreateCompletion(ctx, req)
	if err != nil {
		t.Fatalf("CreateCompletion failed: %v", err)
	}

	if len(resp.Choices) == 0 {
		t.Fatal("No choices in response")
	}

	if resp.Choices[0].Message.Content == "" {
		t.Fatal("Empty response content")
	}

	t.Logf("Response: %s", resp.Choices[0].Message.Content)
}

// TestArchitectAgent tests world generation
func TestArchitectAgent(t *testing.T) {
	architect := NewArchitectAgent()

	if architect.client.apiKey == "" {
		t.Skip("OPENROUTER_API_KEY not set, skipping integration test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	schema, err := architect.GenerateWorld(ctx, "A small fantasy village with a mysterious forest")
	if err != nil {
		t.Fatalf("GenerateWorld failed: %v", err)
	}

	// Validate schema
	if schema.Name == "" {
		t.Fatal("World name is empty")
	}

	if len(schema.Stats) == 0 {
		t.Fatal("No stats generated")
	}

	if len(schema.PlotNodes) == 0 {
		t.Fatal("No plot nodes generated")
	}

	t.Logf("Generated world: %s (%s)", schema.Name, schema.Era)
	t.Logf("Stats: %d, NPCs: %d, Plot nodes: %d", len(schema.Stats), len(schema.NPCs), len(schema.PlotNodes))
}

// TestWriterAgent tests card generation
func TestWriterAgent(t *testing.T) {
	writer := NewWriterAgent()

	if writer.client.apiKey == "" {
		t.Skip("OPENROUTER_API_KEY not set, skipping integration test")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	jobs := []CardGenJob{
		{
			Type: "plot",
			Context: map[string]interface{}{
				"node_id":     "start",
				"description": "The adventure begins in a small village",
			},
		},
	}

	worldContext := map[string]interface{}{
		"world": "Fantasy Village",
		"npcs":  5,
	}

	cards, err := writer.GenerateCards(ctx, jobs, worldContext)
	if err != nil {
		t.Fatalf("GenerateCards failed: %v", err)
	}

	if len(cards) == 0 {
		t.Fatal("No cards generated")
	}

	t.Logf("Generated %d cards", len(cards))
	for i, card := range cards {
		t.Logf("  Card %d: %s (priority: %d)", i+1, card.GetTitle(), card.GetPriority())
	}
}

// TestCompletionRequestMarshaling tests JSON marshaling
func TestCompletionRequestMarshaling(t *testing.T) {
	req := &CompletionRequest{
		Model:     "claude-3-5-sonnet-20241022",
		MaxTokens: 100,
		Messages: []Message{
			{
				Role:    "user",
				Content: "Hello",
			},
		},
	}

	data, err := json.Marshal(req)
	if err != nil {
		t.Fatalf("Marshal failed: %v", err)
	}

	var unmarshaled CompletionRequest
	if err := json.Unmarshal(data, &unmarshaled); err != nil {
		t.Fatalf("Unmarshal failed: %v", err)
	}

	if unmarshaled.Model != req.Model {
		t.Fatalf("Model mismatch: %s != %s", unmarshaled.Model, req.Model)
	}
}

// BenchmarkOpenRouterClient benchmarks API calls
func BenchmarkOpenRouterClient(b *testing.B) {
	client := NewOpenRouterClient()

	if client.apiKey == "" {
		b.Skip("OPENROUTER_API_KEY not set")
	}

	ctx := context.Background()
	req := &CompletionRequest{
		Model:     "claude-3-5-sonnet-20241022",
		MaxTokens: 50,
		Messages: []Message{
			{
				Role:    "user",
				Content: "Say hello",
			},
		},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, err := client.CreateCompletion(ctx, req)
		if err != nil {
			b.Fatalf("CreateCompletion failed: %v", err)
		}
	}
}

// TestErrorHandling tests error scenarios
func TestErrorHandling(t *testing.T) {
	client := NewOpenRouterClient()

	// Test with empty API key
	client.apiKey = ""
	ctx := context.Background()
	req := &CompletionRequest{
		Model: "claude-3-5-sonnet-20241022",
	}

	_, err := client.CreateCompletion(ctx, req)
	if err == nil {
		t.Fatal("Expected error for empty API key")
	}

	if err.Error() != "OPENROUTER_API_KEY not set" {
		t.Fatalf("Unexpected error: %v", err)
	}
}

// TestWorldGeneration tests full world generation flow
func TestWorldGeneration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	architect := NewArchitectAgent()
	if architect.client.apiKey == "" {
		t.Skip("OPENROUTER_API_KEY not set")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	prompts := []string{
		"A cyberpunk megacity with AI overlords",
		"A post-apocalyptic wasteland with mutant creatures",
		"A steampunk airship civilization",
	}

	for _, prompt := range prompts {
		t.Run(prompt, func(t *testing.T) {
			schema, err := architect.GenerateWorld(ctx, prompt)
			if err != nil {
				t.Fatalf("GenerateWorld failed: %v", err)
			}

			// Validate all required fields
			if schema.Name == "" {
				t.Fatal("Name is empty")
			}
			if schema.Era == "" {
				t.Fatal("Era is empty")
			}
			if len(schema.Stats) == 0 {
				t.Fatal("No stats")
			}
			if len(schema.PlotNodes) == 0 {
				t.Fatal("No plot nodes")
			}

			t.Logf("✓ Generated: %s (%s)", schema.Name, schema.Era)
		})
	}
}

// TestCardGeneration tests full card generation flow
func TestCardGeneration(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	writer := NewWriterAgent()
	if writer.client.apiKey == "" {
		t.Skip("OPENROUTER_API_KEY not set")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	jobs := []CardGenJob{
		{Type: "plot", Context: map[string]interface{}{"description": "The hero arrives at the castle"}},
		{Type: "info", Context: map[string]interface{}{"topic": "lore"}},
		{Type: "plot", Context: map[string]interface{}{"description": "A mysterious stranger appears"}},
	}

	worldContext := map[string]interface{}{
		"world": "Medieval Kingdom",
		"npcs":  10,
	}

	cards, err := writer.GenerateCards(ctx, jobs, worldContext)
	if err != nil {
		t.Fatalf("GenerateCards failed: %v", err)
	}

	if len(cards) == 0 {
		t.Fatal("No cards generated")
	}

	if len(cards) != len(jobs) {
		t.Logf("Warning: Generated %d cards for %d jobs", len(cards), len(jobs))
	}

	t.Logf("✓ Generated %d cards", len(cards))
}
