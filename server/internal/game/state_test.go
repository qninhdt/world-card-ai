package game

import (
	"testing"
	"time"
)

// TestNewGlobalBlackboard tests state creation
func TestNewGlobalBlackboard(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	if state == nil {
		t.Fatal("State is nil")
	}

	if state.WorldName != schema.Name {
		t.Errorf("Expected world name '%s', got '%s'", schema.Name, state.WorldName)
	}

	if state.Day != 1 {
		t.Errorf("Expected day 1, got %d", state.Day)
	}

	if state.Season != 0 {
		t.Errorf("Expected season 0, got %d", state.Season)
	}

	if state.LifeNumber != 1 {
		t.Errorf("Expected life number 1, got %d", state.LifeNumber)
	}
}

// TestGetStat tests stat retrieval
func TestGetStat(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	stat := state.GetStat("health")

	if stat != 100 {
		t.Errorf("Expected stat 100, got %d", stat)
	}
}

// TestSetStat tests stat setting with clamping
func TestSetStat(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.SetStat("health", 150)

	if state.GetStat("health") != 100 {
		t.Errorf("Expected stat clamped to 100, got %d", state.GetStat("health"))
	}

	state.SetStat("health", -10)

	if state.GetStat("health") != 0 {
		t.Errorf("Expected stat clamped to 0, got %d", state.GetStat("health"))
	}
}

// TestUpdateStat tests stat updating
func TestUpdateStat(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.UpdateStat("health", -20)

	if state.GetStat("health") != 80 {
		t.Errorf("Expected stat 80, got %d", state.GetStat("health"))
	}
}

// TestHasTag tests tag checking
func TestHasTag(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	if !state.HasTag("tag1") {
		t.Error("Expected tag1 to be present")
	}

	if state.HasTag("nonexistent") {
		t.Error("Expected nonexistent tag to not be present")
	}
}

// TestAddTag tests tag addition
func TestAddTag(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.AddTag("new-tag")

	if !state.HasTag("new-tag") {
		t.Error("Expected new-tag to be present after adding")
	}
}

// TestRemoveTag tests tag removal
func TestRemoveTag(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.RemoveTag("tag1")

	if state.HasTag("tag1") {
		t.Error("Expected tag1 to be removed")
	}
}

// TestGetNPC tests NPC retrieval
func TestGetNPC(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	npc := state.GetNPC("npc1")

	if npc == nil {
		t.Fatal("NPC is nil")
	}

	if npc.Name != "NPC 1" {
		t.Errorf("Expected NPC name 'NPC 1', got '%s'", npc.Name)
	}
}

// TestEnableNPC tests NPC enabling
func TestEnableNPC(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.DisableNPC("npc1")
	state.EnableNPC("npc1")

	npc := state.GetNPC("npc1")
	if !npc.Enabled {
		t.Error("Expected NPC to be enabled")
	}
}

// TestDisableNPC tests NPC disabling
func TestDisableNPC(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.DisableNPC("npc1")

	npc := state.GetNPC("npc1")
	if npc.Enabled {
		t.Error("Expected NPC to be disabled")
	}
}

// TestAddEvent tests event addition
func TestAddEvent(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:          "test-event",
			Name:        "Test Event",
			Description: "A test event",
		},
	}

	state.AddEvent(event)

	retrieved := state.GetEvent("test-event")
	if retrieved == nil {
		t.Fatal("Event not found after adding")
	}
}

// TestRemoveEvent tests event removal
func TestRemoveEvent(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:          "test-event",
			Name:        "Test Event",
			Description: "A test event",
		},
	}

	state.AddEvent(event)
	state.RemoveEvent("test-event")

	retrieved := state.GetEvent("test-event")
	if retrieved != nil {
		t.Error("Event still exists after removal")
	}
}

// TestAdvanceDay tests day advancement
func TestAdvanceDay(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	initialDay := state.Day
	state.AdvanceDay()

	if state.Day != initialDay+1 {
		t.Errorf("Expected day %d, got %d", initialDay+1, state.Day)
	}
}

// TestAdvanceDayWeekBoundary tests week boundary during day advancement
func TestAdvanceDayWeekBoundary(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 7
	state.Turn = 6

	state.AdvanceDay()

	// After advancing: day becomes 8, turn becomes 7
	// Turn is reset to 0 when turn >= 7 (which is 7 days per week)
	// But the reset happens in the next iteration, so turn will be 7 after first advance
	if state.Turn != 7 {
		t.Errorf("Expected turn 7, got %d", state.Turn)
	}

	if state.Day != 8 {
		t.Errorf("Expected day 8, got %d", state.Day)
	}
}

// TestAdvanceDaySeasonBoundary tests season boundary during day advancement
func TestAdvanceDaySeasonBoundary(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 28
	state.Season = 0

	state.AdvanceDay()

	// After advancing: day becomes 29, but when day > 28, it resets to 1
	if state.Day != 1 {
		t.Errorf("Expected day reset to 1, got %d", state.Day)
	}

	if state.Season != 1 {
		t.Errorf("Expected season 1, got %d", state.Season)
	}
}

// TestGetElapsedDays tests elapsed days calculation
func TestGetElapsedDays(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 5
	state.Season = 0
	state.Year = 0
	state.StartDay = 1
	state.StartSeason = 0
	state.StartYear = 0

	elapsed := state.GetElapsedDays()

	// Elapsed = (0 * 112) + (0 * 28) + 5 - ((0 * 112) + (0 * 28) + 1) = 4
	if elapsed != 4 {
		t.Errorf("Expected 4 elapsed days, got %d", elapsed)
	}
}

// TestWeekInSeason tests week calculation
func TestWeekInSeason(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 1
	if state.WeekInSeason() != 1 {
		t.Errorf("Expected week 1, got %d", state.WeekInSeason())
	}

	state.Day = 8
	if state.WeekInSeason() != 2 {
		t.Errorf("Expected week 2, got %d", state.WeekInSeason())
	}

	state.Day = 15
	if state.WeekInSeason() != 3 {
		t.Errorf("Expected week 3, got %d", state.WeekInSeason())
	}

	state.Day = 22
	if state.WeekInSeason() != 4 {
		t.Errorf("Expected week 4, got %d", state.WeekInSeason())
	}
}

// TestDateDisplay tests date display formatting
func TestDateDisplay(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 5
	state.Season = 0
	state.Year = 1

	display := state.DateDisplay()

	if display == "" {
		t.Error("Date display is empty")
	}

	if len(display) == 0 {
		t.Error("Date display has no content")
	}
}

// TestElapsedDisplay tests elapsed time display formatting
func TestElapsedDisplay(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Day = 5
	state.Season = 0
	state.Year = 0

	display := state.ElapsedDisplay()

	if display == "" {
		t.Error("Elapsed display is empty")
	}
}

// TestGetEnabledNPCs tests enabled NPC retrieval
func TestGetEnabledNPCs(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	enabled := state.GetEnabledNPCs()

	if len(enabled) != 1 {
		t.Errorf("Expected 1 enabled NPC, got %d", len(enabled))
	}

	state.DisableNPC("npc1")
	enabled = state.GetEnabledNPCs()

	if len(enabled) != 0 {
		t.Errorf("Expected 0 enabled NPCs after disabling, got %d", len(enabled))
	}
}

// TestGetEnabledNPCNames tests enabled NPC names retrieval
func TestGetEnabledNPCNames(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	names := state.GetEnabledNPCNames()

	if len(names) != 1 {
		t.Errorf("Expected 1 NPC name, got %d", len(names))
	}

	if names[0] != "NPC 1" {
		t.Errorf("Expected NPC name 'NPC 1', got '%s'", names[0])
	}
}

// TestAdvanceToNextSeason tests season advancement
func TestAdvanceToNextSeason(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Season = 0
	state.AdvanceToNextSeason()

	if state.Season != 1 {
		t.Errorf("Expected season 1, got %d", state.Season)
	}

	if state.Day != 1 {
		t.Errorf("Expected day reset to 1, got %d", state.Day)
	}
}

// TestAdvanceToNextSeasonYearBoundary tests year advancement at season boundary
func TestAdvanceToNextSeasonYearBoundary(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.Season = 3
	state.Year = 1

	state.AdvanceToNextSeason()

	if state.Season != 0 {
		t.Errorf("Expected season 0, got %d", state.Season)
	}

	if state.Year != 2 {
		t.Errorf("Expected year 2, got %d", state.Year)
	}
}

// TestGetStats tests stats retrieval
func TestGetStats(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	stats := state.GetStats()

	if len(stats) != 2 {
		t.Errorf("Expected 2 stats, got %d", len(stats))
	}

	if stats["health"] != 100 {
		t.Errorf("Expected health 100, got %d", stats["health"])
	}
}

// TestGetTags tests tags retrieval
func TestGetTags(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	tags := state.GetTags()

	if len(tags) != 1 {
		t.Errorf("Expected 1 tag, got %d", len(tags))
	}

	if !tags["tag1"] {
		t.Error("Expected tag1 to be present")
	}
}

// TestGetNPCIDs tests NPC IDs retrieval
func TestGetNPCIDs(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	ids := state.GetNPCIDs()

	if len(ids) != 1 {
		t.Errorf("Expected 1 NPC ID, got %d", len(ids))
	}
}

// TestClearEvents tests event clearing
func TestClearEvents(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:          "test-event",
			Name:        "Test Event",
			Description: "A test event",
		},
	}

	state.AddEvent(event)
	state.ClearEvents()

	if len(state.Events) != 0 {
		t.Errorf("Expected 0 events after clearing, got %d", len(state.Events))
	}
}

// TestSetIsAlive tests alive state setting
func TestSetIsAlive(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.SetIsAlive(false)

	if state.IsAlive {
		t.Error("Expected IsAlive to be false")
	}
}

// TestSetDeathCause tests death cause setting
func TestSetDeathCause(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.SetDeathCause("health")

	if state.DeathCause != "health" {
		t.Errorf("Expected death cause 'health', got '%s'", state.DeathCause)
	}
}

// TestSetDeathTurn tests death turn setting
func TestSetDeathTurn(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.SetDeathTurn(42)

	if state.DeathTurn != 42 {
		t.Errorf("Expected death turn 42, got %d", state.DeathTurn)
	}
}

// TestSetCurrentLife tests current life setting
func TestSetCurrentLife(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	state.SetCurrentLife(3)

	if state.CurrentLife != 3 {
		t.Errorf("Expected current life 3, got %d", state.CurrentLife)
	}
}

// TestTimestamps tests timestamp updates
func TestTimestamps(t *testing.T) {
	schema := createTestSchema()
	state := NewGlobalBlackboard(schema)

	createdAt := state.CreatedAt
	updatedAt := state.UpdatedAt

	if createdAt.IsZero() {
		t.Error("CreatedAt is zero")
	}

	if updatedAt.IsZero() {
		t.Error("UpdatedAt is zero")
	}

	if createdAt.After(time.Now()) {
		t.Error("CreatedAt is in the future")
	}

	if updatedAt.After(time.Now()) {
		t.Error("UpdatedAt is in the future")
	}
}
