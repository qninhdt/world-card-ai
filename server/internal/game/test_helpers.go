package game

import (
	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
)

// createTestSchema creates a test schema for unit tests
func createTestSchema() *agents.WorldGenSchema {
	return &agents.WorldGenSchema{
		Name:        "Test World",
		Era:         "Test Era",
		Description: "A test world",
		Stats: []agents.StatDef{
			{ID: "health", Name: "Health", Description: "Health stat"},
			{ID: "mana", Name: "Mana", Description: "Mana stat"},
		},
		Tags: []agents.TagDef{
			{ID: "tag1", Name: "Tag 1", Description: "Test tag 1", IsTemp: false},
			{ID: "tag2", Name: "Tag 2", Description: "Test tag 2", IsTemp: true},
		},
		Seasons: []agents.SeasonDef{
			{ID: "spring", Name: "Spring", Description: "Spring season"},
			{ID: "summer", Name: "Summer", Description: "Summer season"},
			{ID: "autumn", Name: "Autumn", Description: "Autumn season"},
			{ID: "winter", Name: "Winter", Description: "Winter season"},
		},
		PlayerChar: agents.PlayerCharacterDef{
			EntityDef:   agents.EntityDef{ID: "player", Name: "Player"},
			Description: "The player character",
		},
		NPCs: []agents.NPCDef{
			{
				EntityDef:   agents.EntityDef{ID: "npc1", Name: "NPC 1"},
				Description: "Test NPC",
				Appearance:  "A test NPC",
			},
		},
		Relationships: []agents.RelationshipDef{
			{From: "player", To: "npc1", Description: "Friendly"},
		},
		PlotNodes: []agents.PlotNodeDef{
			{
				ID:              "plot1",
				PlotDescription: "Test plot",
				Condition:       "true",
				IsEnding:        false,
				SuccessorIDs:    []string{},
			},
		},
		InitialStats: map[string]int{
			"health": 100,
			"mana":   50,
		},
		InitialTags: []string{"tag1"},
	}
}
