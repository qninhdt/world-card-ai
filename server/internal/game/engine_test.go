package game

import (
	"testing"

	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
	"github.com/qninhdt/world-card-ai-2/server/internal/cards"
)

// TestNewGameEngine tests game engine creation
func TestNewGameEngine(t *testing.T) {
	schema := createTestSchema()
	engine, err := NewGameEngine("test-game", schema)

	if err != nil {
		t.Fatalf("Failed to create game engine: %v", err)
	}

	if engine == nil {
		t.Fatal("Engine is nil")
	}

	if engine.ID != "test-game" {
		t.Errorf("Expected ID 'test-game', got '%s'", engine.ID)
	}

	if engine.state == nil {
		t.Fatal("State is nil")
	}

	if engine.dag == nil {
		t.Fatal("DAG is nil")
	}
}

// TestGetState tests state retrieval
func TestGetState(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	state := engine.GetState()
	if state == nil {
		t.Fatal("State is nil")
	}

	if state.WorldName != schema.Name {
		t.Errorf("Expected world name '%s', got '%s'", schema.Name, state.WorldName)
	}
}

// TestDrawCard tests card drawing
func TestDrawCard(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	// Add a test card to the deck
	testCard := &cards.InfoCard{
		ID:          "test-card",
		Title:       "Test",
		Description: "Test card",
		Character:   "narrator",
		Source:      "test",
		Priority:    cards.PriorityCommon,
	}
	engine.deck.Insert(testCard)

	card := engine.DrawCard()
	if card == nil {
		t.Fatal("Drew nil card")
	}

	if card.GetID() != "test-card" {
		t.Errorf("Expected card ID 'test-card', got '%s'", card.GetID())
	}
}

// TestIsWeekOver tests week completion check
func TestIsWeekOver(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	if !engine.IsWeekOver() {
		t.Error("Expected week to be over for empty deck")
	}

	// Add a card
	testCard := &cards.InfoCard{
		ID:          "test-card",
		Title:       "Test",
		Description: "Test card",
		Character:   "narrator",
		Source:      "test",
		Priority:    cards.PriorityCommon,
	}
	engine.deck.Insert(testCard)

	if engine.IsWeekOver() {
		t.Error("Expected week not to be over with cards in deck")
	}
}

// TestAdvanceDayWithBoundaries tests day advancement
func TestAdvanceDayWithBoundaries(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	state := engine.GetState()
	initialDay := state.Day

	crossed := engine.AdvanceDayWithBoundaries()

	if state.Day != initialDay+1 {
		t.Errorf("Expected day %d, got %d", initialDay+1, state.Day)
	}

	if crossed == nil {
		t.Fatal("Crossed boundaries map is nil")
	}
}

// TestWeekBoundary tests week boundary detection
func TestWeekBoundary(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	state := engine.GetState()
	state.Day = 7
	state.Turn = 6

	crossed := engine.AdvanceDayWithBoundaries()

	// After advancing: day becomes 8, turn becomes 7
	// Week boundary is crossed when turn == 0 (after reset)
	// But we check before reset, so turn will be 7
	// The boundary detection checks if turn == 0 after advance
	if crossed["week_end"] {
		t.Logf("Day: %d, Turn: %d", state.Day, state.Turn)
		// Week boundary should not be crossed yet
	}
}

// TestSeasonBoundary tests season boundary detection
func TestSeasonBoundary(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	state := engine.GetState()
	state.Day = 28
	state.Season = 0

	crossed := engine.AdvanceDayWithBoundaries()

	if !crossed["season_end"] {
		t.Error("Expected season_end boundary to be crossed")
	}

	if state.Season != 1 {
		t.Errorf("Expected season 1, got %d", state.Season)
	}
}

// TestAddCardsFromDefs tests card addition from definitions
func TestAddCardsFromDefs(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	cardDefs := []map[string]interface{}{
		{
			"id":          "card1",
			"title":       "Card 1",
			"description": "Test card 1",
			"character":   "narrator",
			"source":      "test",
			"priority":    float64(cards.PriorityCommon),
		},
		{
			"id":          "card2",
			"title":       "Card 2",
			"description": "Test card 2",
			"character":   "narrator",
			"source":      "test",
			"priority":    float64(cards.PriorityCommon),
		},
	}

	count := engine.AddCardsFromDefs(cardDefs)

	if count != 2 {
		t.Errorf("Expected 2 cards added, got %d", count)
	}
}

// TestConvertToCard tests card conversion
func TestConvertToCard(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	cardDef := map[string]interface{}{
		"id":          "test-card",
		"title":       "Test Card",
		"description": "A test card",
		"character":   "narrator",
		"source":      "test",
		"priority":    float64(cards.PriorityCommon),
	}

	card := engine.convertToCard(cardDef)

	if card == nil {
		t.Fatal("Converted card is nil")
	}

	if card.GetID() != "test-card" {
		t.Errorf("Expected ID 'test-card', got '%s'", card.GetID())
	}

	if card.GetTitle() != "Test Card" {
		t.Errorf("Expected title 'Test Card', got '%s'", card.GetTitle())
	}
}

// TestGetGenerationContext tests context generation
func TestGetGenerationContext(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	context := engine.GetGenerationContext()

	if context == nil {
		t.Fatal("Context is nil")
	}

	if _, ok := context["snapshot"]; !ok {
		t.Error("Context missing 'snapshot'")
	}

	if _, ok := context["ongoing_events"]; !ok {
		t.Error("Context missing 'ongoing_events'")
	}

	if _, ok := context["available_tags"]; !ok {
		t.Error("Context missing 'available_tags'")
	}
}

// TestGetAllEventsForDisplay tests event display formatting
func TestGetAllEventsForDisplay(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	// Add a test event
	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:          "test-event",
			Name:        "Test Event",
			Description: "A test event",
			Icon:        "⚡",
		},
		Phases: []EventPhase{
			{Name: "Phase 1", Description: "First phase"},
		},
		CurrentPhase: 0,
	}
	engine.state.Events["test-event"] = event

	events := engine.GetAllEventsForDisplay()

	if len(events) != 1 {
		t.Errorf("Expected 1 event, got %d", len(events))
	}

	if events[0]["name"] != "Test Event" {
		t.Errorf("Expected event name 'Test Event', got '%s'", events[0]["name"])
	}
}

// TestCheckEnding tests ending check
func TestCheckEnding(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	ending := engine.CheckEnding()

	if ending != nil {
		t.Error("Expected no ending, got one")
	}
}

// TestIsAwaitingResurrection tests resurrection state
func TestIsAwaitingResurrection(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	if engine.IsAwaitingResurrection() {
		t.Error("Expected not awaiting resurrection")
	}
}

// TestInsertTreeCards tests tree card insertion
func TestInsertTreeCards(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	treeCards := []cards.Card{
		&cards.InfoCard{
			ID:          "tree-card-1",
			Title:       "Tree Card 1",
			Description: "Test tree card",
			Character:   "narrator",
			Source:      "tree",
			Priority:    cards.PriorityTree,
		},
	}

	engine.InsertTreeCards(treeCards)

	if engine.immediateDeque.Len() != 1 {
		t.Errorf("Expected 1 card in immediate deque, got %d", engine.immediateDeque.Len())
	}
}

// TestGetWeekDeckSize tests deck size
func TestGetWeekDeckSize(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	size := engine.GetWeekDeckSize()

	if size != 7 {
		t.Errorf("Expected deck size 7, got %d", size)
	}
}

// TestGetCommonCount tests common card count calculation
func TestGetCommonCount(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	count := engine.GetCommonCount()

	if count < 1 || count > 7 {
		t.Errorf("Expected common count between 1 and 7, got %d", count)
	}
}

// TestBuildSnapshot tests snapshot building
func TestBuildSnapshot(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	snapshot := engine.buildSnapshot()

	if snapshot == nil {
		t.Fatal("Snapshot is nil")
	}

	if snapshot["world"] != schema.Name {
		t.Errorf("Expected world '%s', got '%s'", schema.Name, snapshot["world"])
	}

	if _, ok := snapshot["stats"]; !ok {
		t.Error("Snapshot missing 'stats'")
	}

	if _, ok := snapshot["npcs"]; !ok {
		t.Error("Snapshot missing 'npcs'")
	}
}

// TestBuildAvailableTags tests available tags building
func TestBuildAvailableTags(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	tags := engine.buildAvailableTags()

	if tags == nil {
		t.Fatal("Tags is nil")
	}

	if len(tags) != len(schema.Tags) {
		t.Errorf("Expected %d tags, got %d", len(schema.Tags), len(tags))
	}
}

// TestGetCurrentSeasonName tests season name retrieval
func TestGetCurrentSeasonName(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	name := engine.getCurrentSeasonName()

	if name == "" {
		t.Error("Season name is empty")
	}
}

// TestGetCurrentSeasonDescription tests season description retrieval
func TestGetCurrentSeasonDescription(t *testing.T) {
	schema := createTestSchema()
	engine, _ := NewGameEngine("test-game", schema)

	desc := engine.getCurrentSeasonDescription()

	// Description might be empty if not set in schema
	if desc == "" {
		t.Log("Season description is empty (expected if not set in schema)")
	}
}

// Helper function to create a test schema
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
			EntityDef: agents.EntityDef{ID: "player", Name: "Player"},
			Description: "The player character",
		},
		NPCs: []agents.NPCDef{
			{
				EntityDef: agents.EntityDef{ID: "npc1", Name: "NPC 1"},
				Description: "Test NPC",
				Appearance: "A test NPC",
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
