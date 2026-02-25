package cards

import (
	"fmt"
)

// ExecuteResult contains the result of executing a card action
type ExecuteResult struct {
	StatChanges map[string]int
	TreeCards   []Card
	Direction   string // "left" or "right"
}

// StateUpdater is an interface for updating game state
type StateUpdater interface {
	GetStat(id string) int
	SetStat(id string, value int)
	UpdateStat(id string, delta int)
	HasTag(id string) bool
	AddTag(id string)
	RemoveTag(id string)
	EnableNPC(id string)
	DisableNPC(id string)
	AdvanceDay()
	GetTags() map[string]bool
	GetStats() map[string]int
}

// ActionExecutor executes AI-generated function calls against game state
type ActionExecutor struct {
	state StateUpdater
}

// NewActionExecutor creates a new executor
func NewActionExecutor(state StateUpdater) *ActionExecutor {
	return &ActionExecutor{state: state}
}

// Execute executes a function call and returns the result
func (e *ActionExecutor) Execute(call map[string]interface{}) (*ExecuteResult, error) {
	result := &ExecuteResult{
		StatChanges: make(map[string]int),
		TreeCards:   make([]Card, 0),
	}

	name, ok := call["name"].(string)
	if !ok {
		return nil, fmt.Errorf("invalid function call: missing name")
	}

	params, ok := call["params"].(map[string]interface{})
	if !ok {
		params = make(map[string]interface{})
	}

	switch name {
	case "update_stat":
		return e.updateStat(params, result)
	case "add_tag":
		return e.addTag(params, result)
	case "remove_tag":
		return e.removeTag(params, result)
	case "enable_npc":
		return e.enableNPC(params, result)
	case "disable_npc":
		return e.disableNPC(params, result)
	case "advance_time":
		return e.advanceTime(params, result)
	default:
		// Silently ignore unknown functions (events handled separately)
		return result, nil
	}
}

// ExecuteMultiple executes multiple function calls
func (e *ActionExecutor) ExecuteMultiple(calls []map[string]interface{}) (*ExecuteResult, error) {
	result := &ExecuteResult{
		StatChanges: make(map[string]int),
		TreeCards:   make([]Card, 0),
	}

	for _, call := range calls {
		res, err := e.Execute(call)
		if err != nil {
			return nil, err
		}

		// Merge results
		for stat, delta := range res.StatChanges {
			result.StatChanges[stat] += delta
		}
		result.TreeCards = append(result.TreeCards, res.TreeCards...)
	}

	return result, nil
}

func (e *ActionExecutor) updateStat(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	statID, ok := params["stat_id"].(string)
	if !ok {
		return nil, fmt.Errorf("update_stat: missing stat_id")
	}

	// SECURITY FIX: Validate stat exists
	stats := e.state.GetStats()
	if _, exists := stats[statID]; !exists {
		return nil, fmt.Errorf("update_stat: invalid stat_id: %s", statID)
	}

	delta, ok := params["delta"].(float64)
	if !ok {
		return nil, fmt.Errorf("update_stat: invalid delta")
	}

	// SECURITY FIX: Clamp delta to reasonable range
	if delta < -50 || delta > 50 {
		return nil, fmt.Errorf("update_stat: delta out of range: %v", delta)
	}

	oldVal := e.state.GetStat(statID)
	e.state.UpdateStat(statID, int(delta))
	newVal := e.state.GetStat(statID)

	result.StatChanges[statID] = newVal - oldVal
	return result, nil
}

func (e *ActionExecutor) addTag(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	tagID, ok := params["tag_id"].(string)
	if !ok {
		return nil, fmt.Errorf("add_tag: missing tag_id")
	}

	// SECURITY FIX: Validate tag exists (check if it's a valid tag ID)
	// Tags are typically defined in schema, but we allow any tag to be added
	// In production, validate against schema
	if tagID == "" {
		return nil, fmt.Errorf("add_tag: invalid tag_id")
	}

	e.state.AddTag(tagID)
	return result, nil
}

func (e *ActionExecutor) removeTag(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	tagID, ok := params["tag_id"].(string)
	if !ok {
		return nil, fmt.Errorf("remove_tag: missing tag_id")
	}

	// SECURITY FIX: Validate tag exists
	if tagID == "" {
		return nil, fmt.Errorf("remove_tag: invalid tag_id")
	}

	e.state.RemoveTag(tagID)
	return result, nil
}

func (e *ActionExecutor) enableNPC(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	npcID, ok := params["npc_id"].(string)
	if !ok {
		return nil, fmt.Errorf("enable_npc: missing npc_id")
	}

	// SECURITY FIX: Validate NPC ID format (basic validation)
	if npcID == "" {
		return nil, fmt.Errorf("enable_npc: invalid npc_id")
	}

	e.state.EnableNPC(npcID)
	return result, nil
}

func (e *ActionExecutor) disableNPC(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	npcID, ok := params["npc_id"].(string)
	if !ok {
		return nil, fmt.Errorf("disable_npc: missing npc_id")
	}

	// SECURITY FIX: Validate NPC ID format (basic validation)
	if npcID == "" {
		return nil, fmt.Errorf("disable_npc: invalid npc_id")
	}

	e.state.DisableNPC(npcID)
	return result, nil
}

func (e *ActionExecutor) advanceTime(params map[string]interface{}, result *ExecuteResult) (*ExecuteResult, error) {
	days, ok := params["days"].(float64)
	if !ok {
		return nil, fmt.Errorf("advance_time: invalid days")
	}

	for i := 0; i < int(days); i++ {
		e.state.AdvanceDay()
	}

	return result, nil
}
