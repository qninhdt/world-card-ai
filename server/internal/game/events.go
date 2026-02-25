package game

import (
	"encoding/json"
	"fmt"
)

// EventType represents the type of event
type EventType string

const (
	EventTypePhase     EventType = "phase"
	EventTypeProgress  EventType = "progress"
	EventTypeTimed     EventType = "timed"
	EventTypeCondition EventType = "condition"
)

// Event is the base interface for all events
type Event interface {
	GetID() string
	GetName() string
	GetDescription() string
	GetType() EventType
	GetOnActionEndCalls() []map[string]interface{}
	GetOnPhaseEndCalls() []map[string]interface{}
	GetIcon() string
	IsFinished() bool
	ProgressDisplay() string
}

// BaseEvent contains common event fields
type BaseEvent struct {
	ID                string                   `json:"id"`
	Name              string                   `json:"name"`
	Description       string                   `json:"description"`
	Icon              string                   `json:"icon"`
	OnActionEndCalls  []map[string]interface{} `json:"on_action_end_calls"`
	OnPhaseEndCalls   []map[string]interface{} `json:"on_phase_end_calls"`
}

// EventPhase represents a phase in a PhaseEvent
type EventPhase struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

// PhaseEvent progresses through named phases
type PhaseEvent struct {
	BaseEvent
	Phases       []EventPhase `json:"phases"`
	CurrentPhase int          `json:"current_phase"`
}

// ProgressEvent tracks numeric progress toward a goal
type ProgressEvent struct {
	BaseEvent
	Target         int    `json:"target"`
	Current        int    `json:"current"`
	ProgressLabel  string `json:"progress_label"`
}

// TimedEvent expires at a calendar deadline
type TimedEvent struct {
	BaseEvent
	DeadlineDay    int `json:"deadline_day"`
	DeadlineSeason int `json:"deadline_season"`
	DeadlineYear   int `json:"deadline_year"`
}

// ConditionEvent ends when a condition evaluates to true
type ConditionEvent struct {
	BaseEvent
	EndCondition string `json:"end_condition"`
}

// Implement Event interface for BaseEvent
func (e *BaseEvent) GetID() string                          { return e.ID }
func (e *BaseEvent) GetName() string                        { return e.Name }
func (e *BaseEvent) GetDescription() string                { return e.Description }
func (e *BaseEvent) GetIcon() string                        { return e.Icon }
func (e *BaseEvent) GetOnActionEndCalls() []map[string]interface{} { return e.OnActionEndCalls }
func (e *BaseEvent) GetOnPhaseEndCalls() []map[string]interface{}  { return e.OnPhaseEndCalls }

// Implement Event interface for PhaseEvent
func (e *PhaseEvent) GetType() EventType { return EventTypePhase }
func (e *PhaseEvent) IsFinished() bool   { return e.CurrentPhase >= len(e.Phases) }
func (e *PhaseEvent) ProgressDisplay() string {
	if e.IsFinished() {
		return "Done"
	}
	if e.CurrentPhase < len(e.Phases) {
		phase := e.Phases[e.CurrentPhase]
		return fmt.Sprintf("Phase %d/%d: %s", e.CurrentPhase+1, len(e.Phases), phase.Name)
	}
	return "Unknown"
}

func (e *PhaseEvent) AdvancePhase() *EventPhase {
	if e.IsFinished() {
		return nil
	}
	completed := e.Phases[e.CurrentPhase]
	e.CurrentPhase++
	return &completed
}

func (e *PhaseEvent) CurrentPhaseObj() *EventPhase {
	if e.IsFinished() {
		return nil
	}
	return &e.Phases[e.CurrentPhase]
}

// Implement Event interface for ProgressEvent
func (e *ProgressEvent) GetType() EventType { return EventTypeProgress }
func (e *ProgressEvent) IsFinished() bool   { return e.Current >= e.Target }
func (e *ProgressEvent) ProgressDisplay() string {
	if e.IsFinished() {
		return "Done"
	}
	return fmt.Sprintf("%s: %d/%d", e.ProgressLabel, e.Current, e.Target)
}

func (e *ProgressEvent) UpdateProgress(delta int) {
	e.Current += delta
}

// Implement Event interface for TimedEvent
func (e *TimedEvent) GetType() EventType { return EventTypeTimed }
func (e *TimedEvent) IsFinished() bool   { return false } // checked externally
func (e *TimedEvent) ProgressDisplay() string {
	return fmt.Sprintf("Deadline: %d/%d/%d", e.DeadlineDay, e.DeadlineSeason, e.DeadlineYear)
}

func (e *TimedEvent) IsExpired(currentDay, currentSeason, currentYear int) bool {
	if currentYear > e.DeadlineYear {
		return true
	}
	if currentYear == e.DeadlineYear {
		if currentSeason > e.DeadlineSeason {
			return true
		}
		if currentSeason == e.DeadlineSeason {
			return currentDay >= e.DeadlineDay
		}
	}
	return false
}

func (e *TimedEvent) SetDeadline(day, season, year int) {
	e.DeadlineDay = day
	e.DeadlineSeason = season
	e.DeadlineYear = year
}

// Implement Event interface for ConditionEvent
func (e *ConditionEvent) GetType() EventType { return EventTypeCondition }
func (e *ConditionEvent) IsFinished() bool   { return false } // checked externally
func (e *ConditionEvent) ProgressDisplay() string {
	return "Active"
}

// UnmarshalEvent unmarshals JSON into the correct event type
func UnmarshalEvent(data []byte) (Event, error) {
	var raw map[string]interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	eventType := EventTypePhase // default
	if typeStr, ok := raw["type"].(string); ok {
		eventType = EventType(typeStr)
	}

	switch eventType {
	case EventTypePhase:
		var e PhaseEvent
		if err := json.Unmarshal(data, &e); err != nil {
			return nil, err
		}
		return &e, nil
	case EventTypeProgress:
		var e ProgressEvent
		if err := json.Unmarshal(data, &e); err != nil {
			return nil, err
		}
		return &e, nil
	case EventTypeTimed:
		var e TimedEvent
		if err := json.Unmarshal(data, &e); err != nil {
			return nil, err
		}
		return &e, nil
	case EventTypeCondition:
		var e ConditionEvent
		if err := json.Unmarshal(data, &e); err != nil {
			return nil, err
		}
		return &e, nil
	default:
		var e PhaseEvent
		if err := json.Unmarshal(data, &e); err != nil {
			return nil, err
		}
		return &e, nil
	}
}
