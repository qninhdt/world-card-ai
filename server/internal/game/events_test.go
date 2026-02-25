package game

import (
	"testing"
)

// TestPhaseEventIsFinished tests phase event completion
func TestPhaseEventIsFinished(t *testing.T) {
	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Phases: []EventPhase{
			{Name: "Phase 1", Description: "First phase"},
			{Name: "Phase 2", Description: "Second phase"},
		},
		CurrentPhase: 0,
	}

	if event.IsFinished() {
		t.Error("Expected event not to be finished")
	}

	event.CurrentPhase = 2
	if !event.IsFinished() {
		t.Error("Expected event to be finished")
	}
}

// TestPhaseEventAdvancePhase tests phase advancement
func TestPhaseEventAdvancePhase(t *testing.T) {
	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Phases: []EventPhase{
			{Name: "Phase 1", Description: "First phase"},
			{Name: "Phase 2", Description: "Second phase"},
		},
		CurrentPhase: 0,
	}

	phase := event.AdvancePhase()

	if phase == nil {
		t.Fatal("Advanced phase is nil")
	}

	if phase.Name != "Phase 1" {
		t.Errorf("Expected phase name 'Phase 1', got '%s'", phase.Name)
	}

	if event.CurrentPhase != 1 {
		t.Errorf("Expected current phase 1, got %d", event.CurrentPhase)
	}
}

// TestPhaseEventProgressDisplay tests progress display
func TestPhaseEventProgressDisplay(t *testing.T) {
	event := &PhaseEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Phases: []EventPhase{
			{Name: "Phase 1", Description: "First phase"},
		},
		CurrentPhase: 0,
	}

	display := event.ProgressDisplay()

	if display == "" {
		t.Error("Progress display is empty")
	}

	if len(display) == 0 {
		t.Error("Progress display has no content")
	}
}

// TestProgressEventIsFinished tests progress event completion
func TestProgressEventIsFinished(t *testing.T) {
	event := &ProgressEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Target:  10,
		Current: 5,
	}

	if event.IsFinished() {
		t.Error("Expected event not to be finished")
	}

	event.Current = 10
	if !event.IsFinished() {
		t.Error("Expected event to be finished")
	}
}

// TestProgressEventUpdateProgress tests progress update
func TestProgressEventUpdateProgress(t *testing.T) {
	event := &ProgressEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Target:  10,
		Current: 5,
	}

	event.UpdateProgress(3)

	if event.Current != 8 {
		t.Errorf("Expected current 8, got %d", event.Current)
	}
}

// TestProgressEventProgressDisplay tests progress display
func TestProgressEventProgressDisplay(t *testing.T) {
	event := &ProgressEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		Target:        10,
		Current:       5,
		ProgressLabel: "Items collected",
	}

	display := event.ProgressDisplay()

	if display == "" {
		t.Error("Progress display is empty")
	}

	if len(display) == 0 {
		t.Error("Progress display has no content")
	}
}

// TestTimedEventIsExpired tests timed event expiration
func TestTimedEventIsExpired(t *testing.T) {
	event := &TimedEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		DeadlineDay:    10,
		DeadlineSeason: 0,
		DeadlineYear:   1,
	}

	// Not expired yet
	if event.IsExpired(5, 0, 1) {
		t.Error("Expected event not to be expired")
	}

	// Expired
	if !event.IsExpired(10, 0, 1) {
		t.Error("Expected event to be expired")
	}

	// Expired (past deadline)
	if !event.IsExpired(15, 0, 1) {
		t.Error("Expected event to be expired")
	}
}

// TestTimedEventSetDeadline tests deadline setting
func TestTimedEventSetDeadline(t *testing.T) {
	event := &TimedEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
	}

	event.SetDeadline(15, 2, 1)

	if event.DeadlineDay != 15 {
		t.Errorf("Expected deadline day 15, got %d", event.DeadlineDay)
	}

	if event.DeadlineSeason != 2 {
		t.Errorf("Expected deadline season 2, got %d", event.DeadlineSeason)
	}

	if event.DeadlineYear != 1 {
		t.Errorf("Expected deadline year 1, got %d", event.DeadlineYear)
	}
}

// TestTimedEventProgressDisplay tests progress display
func TestTimedEventProgressDisplay(t *testing.T) {
	event := &TimedEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		DeadlineDay:    10,
		DeadlineSeason: 0,
		DeadlineYear:   1,
	}

	display := event.ProgressDisplay()

	if display == "" {
		t.Error("Progress display is empty")
	}

	if len(display) == 0 {
		t.Error("Progress display has no content")
	}
}

// TestConditionEventProgressDisplay tests progress display
func TestConditionEventProgressDisplay(t *testing.T) {
	event := &ConditionEvent{
		BaseEvent: BaseEvent{
			ID:   "test",
			Name: "Test",
		},
		EndCondition: "stats['health'] < 50",
	}

	display := event.ProgressDisplay()

	if display != "Active" {
		t.Errorf("Expected 'Active', got '%s'", display)
	}
}

// TestEventInterface tests event interface implementation
func TestEventInterface(t *testing.T) {
	events := []Event{
		&PhaseEvent{
			BaseEvent: BaseEvent{
				ID:   "phase",
				Name: "Phase Event",
				Icon: "⚡",
			},
		},
		&ProgressEvent{
			BaseEvent: BaseEvent{
				ID:   "progress",
				Name: "Progress Event",
				Icon: "📊",
			},
		},
		&TimedEvent{
			BaseEvent: BaseEvent{
				ID:   "timed",
				Name: "Timed Event",
				Icon: "⏰",
			},
		},
		&ConditionEvent{
			BaseEvent: BaseEvent{
				ID:   "condition",
				Name: "Condition Event",
				Icon: "🔔",
			},
		},
	}

	for _, event := range events {
		if event.GetID() == "" {
			t.Error("Event ID is empty")
		}

		if event.GetName() == "" {
			t.Error("Event name is empty")
		}

		if event.GetType() == "" {
			t.Error("Event type is empty")
		}

		if event.GetIcon() == "" {
			t.Error("Event icon is empty")
		}
	}
}
