package agents

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/qninhdt/world-card-ai-2/server/internal/cards"
)

// loadPrompt reads a Jinja2 template file from the prompts directory
func loadPrompt(filename string) (string, error) {
	// Try multiple possible paths
	possiblePaths := []string{
		filepath.Join("prompts", filename),
		filepath.Join("..", "..", "prompts", filename),
		filepath.Join("../../prompts", filename),
	}

	for _, path := range possiblePaths {
		content, err := os.ReadFile(path)
		if err == nil {
			return string(content), nil
		}
	}

	return "", fmt.Errorf("could not find prompt file: %s", filename)
}

// renderArchitectPrompts renders the architect system and user prompts
func renderArchitectPrompts(theme string, statCount int) (systemPrompt, userPrompt string, err error) {
	systemContent, err := loadPrompt("architect_system.j2")
	if err != nil {
		return "", "", err
	}

	userContent, err := loadPrompt("architect_user.j2")
	if err != nil {
		return "", "", err
	}

	// Simple template rendering for architect_user.j2
	userPrompt = strings.ReplaceAll(userContent, "{{ language_instruction }}", "English")
	userPrompt = strings.ReplaceAll(userPrompt, "{{ theme if theme else \"Surprise me with something creative and unique\" }}", theme)
	userPrompt = strings.ReplaceAll(userPrompt, "{{ stat_count }}", fmt.Sprintf("%d", statCount))

	return systemContent, userPrompt, nil
}

// ArchitectAgent generates worlds using OpenRouter API
type ArchitectAgent struct {
	client *OpenRouterClient
}

// NewArchitectAgent creates a new architect agent
func NewArchitectAgent() *ArchitectAgent {
	return &ArchitectAgent{
		client: NewOpenRouterClient(),
	}
}

// GenerateWorld generates a world from a prompt using Claude via OpenRouter
func (a *ArchitectAgent) GenerateWorld(ctx context.Context, prompt string) (*WorldGenSchema, error) {
	systemPrompt, userPrompt, err := renderArchitectPrompts(prompt, 5)
	if err != nil {
		// Fallback to inline prompts if template loading fails
		systemPrompt = `You are The Architect — a world-builder for a card-based survival game similar to Reigns.

Your job is to generate a COMPLETE world. Output it as STREAMING SECTIONS — each section starts with a markdown heading
(# Creative Title...) followed by a JSON code block.

FORMAT:
# <Creative thematic title for this section>
  ` + "`" + `json
  { ... section data ... }
  ` + "`" + `

The heading MUST start with a VERB (action word ending in -ing) followed by "..." (e.g. "Forging the Iron Throne...",
"Summoning the court..."). Do not start with nouns.

Generate these sections IN THIS EXACT ORDER:

SECTION 1 — WORLD CORE:
SECTION 2 — PLAYER CHARACTER & STATS:
SECTION 3 — NPCS & RELATIONSHIPS:
SECTION 4 — TAGS:
SECTION 5 — STORY DAG:
SECTION 6 — SEASONS:

CRITICAL RULES:
- ALL IDs, tags, conditions, traits, and function params must be in ENGLISH (snake_case)
- Display text (names, descriptions, flavor) in the TARGET LANGUAGE
- Stats should be thematically tied to the world
- Conditions are Python expressions evaluated via eval() — keep them simple and safe
- Generate 12-15 plot nodes total`
		userPrompt = prompt
	}

	req := &CompletionRequest{
		Model:     "claude-3-5-sonnet-20241022",
		MaxTokens: 4096,
		Messages: []Message{
			{
				Role:    "system",
				Content: systemPrompt,
			},
			{
				Role:    "user",
				Content: userPrompt,
			},
		},
	}

	resp, err := a.client.CreateCompletion(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to call OpenRouter API: %w", err)
	}

	if len(resp.Choices) == 0 {
		return nil, fmt.Errorf("no response from API")
	}

	responseText := resp.Choices[0].Message.Content

	// Parse JSON
	var schema WorldGenSchema
	if err := json.Unmarshal([]byte(responseText), &schema); err != nil {
		return nil, fmt.Errorf("failed to parse world schema: %w", err)
	}

	return &schema, nil
}

// WriterAgent generates cards using OpenRouter API
type WriterAgent struct {
	client *OpenRouterClient
}

// CardGenJob specifies a card generation job
type CardGenJob struct {
	Type    string                 `json:"type"` // "plot", "event_start", "event_phase", "chain", "info"
	Context map[string]interface{} `json:"context"`
}

// NewWriterAgent creates a new writer agent
func NewWriterAgent() *WriterAgent {
	return &WriterAgent{
		client: NewOpenRouterClient(),
	}
}

// GenerateCards generates cards from jobs using Claude via OpenRouter
func (w *WriterAgent) GenerateCards(ctx context.Context, jobs []CardGenJob, worldContext map[string]interface{}) ([]cards.Card, error) {
	if len(jobs) == 0 {
		return []cards.Card{}, nil
	}

	systemContent, err := loadPrompt("writer_system.j2")
	if err != nil {
		// Fallback to inline prompt
		systemContent = `You are The Writer — a real-time card generator for a card-based survival game similar to Reigns.

You generate cards in BATCHES. Each batch contains a mix of:
- COMMON cards: everyday events, character interactions, moral dilemmas
- JOB cards: specific requests (plot events, death messages, reborn messages, welcome messages)

CARD DESIGN RULES:
1. React to the current situation (stats, tags, ongoing events, current phase)
2. Present meaningful dilemmas with real tradeoffs — no obviously correct choice
3. Feature NPCs from the ENABLED NPC list only (use NPC IDs as character field)
4. Left and right choices should BOTH have downsides
5. Keep descriptions to 1-3 punchy sentences
6. Effects are expressed as FUNCTION CALLS (left_calls / right_calls), NOT raw stat dicts

TAG DISCIPLINE:
- You MUST ONLY use tag IDs from the available_tags list provided in context
- Tags are permanent world state modifiers — use them sparingly (1-2 per batch at most)
- 80%+ of choices should use ONLY update_stat calls, no tags`
	}

	userContent, err := loadPrompt("writer_user.j2")
	if err != nil {
		// Fallback to inline prompt
		userContent = "Generate a batch of cards for the current game state."
	}

	contextJSON, _ := json.Marshal(worldContext)

	// Simple template rendering for writer_user.j2
	userPrompt := strings.ReplaceAll(userContent, "{{ language_instruction }}", "English")
	userPrompt = strings.ReplaceAll(userPrompt, "{{ world_context }}", fmt.Sprintf("%v", worldContext))
	userPrompt = strings.ReplaceAll(userPrompt, "{{ stat_names }}", "[]")
	userPrompt = strings.ReplaceAll(userPrompt, "{{ snapshot | tojson(indent=2) }}", string(contextJSON))
	userPrompt = strings.ReplaceAll(userPrompt, "{{ common_count }}", "5")
	userPrompt = strings.ReplaceAll(userPrompt, "{{ jobs | length }}", fmt.Sprintf("%d", len(jobs)))

	req := &CompletionRequest{
		Model:     "claude-3-5-sonnet-20241022",
		MaxTokens: 2048,
		Messages: []Message{
			{
				Role:    "system",
				Content: systemContent,
			},
			{
				Role:    "user",
				Content: userPrompt,
			},
		},
	}

	resp, err := w.client.CreateCompletion(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to call OpenRouter API: %w", err)
	}

	if len(resp.Choices) == 0 {
		return nil, fmt.Errorf("no response from API")
	}

	responseText := resp.Choices[0].Message.Content

	// Parse cards
	var cardData []map[string]interface{}
	if err := json.Unmarshal([]byte(responseText), &cardData); err != nil {
		return nil, fmt.Errorf("failed to parse cards: %w", err)
	}

	// Convert to Card objects
	var result []cards.Card
	for _, data := range cardData {
		if cardType, ok := data["type"].(string); ok {
			if cardType == "choice" {
				card := &cards.ChoiceCard{
					ID:          data["id"].(string),
					Title:       data["title"].(string),
					Description: data["description"].(string),
					Character:   data["character"].(string),
					Source:      data["source"].(string),
					Priority:    int(data["priority"].(float64)),
				}

				if leftChoice, ok := data["left_choice"].(map[string]interface{}); ok {
					card.LeftChoice = &cards.Choice{
						Label: leftChoice["label"].(string),
						Calls: []cards.FunctionCall{},
					}
				}

				if rightChoice, ok := data["right_choice"].(map[string]interface{}); ok {
					card.RightChoice = &cards.Choice{
						Label: rightChoice["label"].(string),
						Calls: []cards.FunctionCall{},
					}
				}

				result = append(result, card)
			} else {
				card := &cards.InfoCard{
					ID:          data["id"].(string),
					Title:       data["title"].(string),
					Description: data["description"].(string),
					Character:   data["character"].(string),
					Source:      data["source"].(string),
					Priority:    int(data["priority"].(float64)),
				}
				result = append(result, card)
			}
		}
	}

	return result, nil
}
