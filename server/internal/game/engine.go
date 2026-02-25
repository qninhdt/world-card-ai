package game

import (
	"container/list"
	"fmt"
	"sync"
	"time"

	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
	"github.com/qninhdt/world-card-ai-2/server/internal/cards"
	"github.com/qninhdt/world-card-ai-2/server/internal/death"
	"github.com/qninhdt/world-card-ai-2/server/internal/story"
)

// GameEngine orchestrates the entire game loop
type GameEngine struct {
	ID               string
	state            *GlobalBlackboard
	dag              *story.MacroDAG
	deck             *cards.WeightedDeque
	deathLoop        *death.DeathLoop
	jobQueue         *JobQueue
	drawnCards       []cards.Card
	immediateDeque   *list.List // cards shown before deck
	awaitingResurrection bool
	firstWeekStarted bool
	mu               sync.RWMutex
}

// NewGameEngine creates a new game from a world schema
func NewGameEngine(id string, schema *agents.WorldGenSchema) (*GameEngine, error) {
	state := NewGlobalBlackboard(schema)
	dag := story.NewMacroDAG()

	// Build DAG from schema
	for _, nodeDef := range schema.PlotNodes {
		node := &story.PlotNode{
			ID:              nodeDef.ID,
			PlotDescription: nodeDef.PlotDescription,
			Condition:       nodeDef.Condition,
			Calls:           nodeDef.Calls,
			IsEnding:        nodeDef.IsEnding,
			IsFired:         false,
		}
		if err := dag.AddNode(node); err != nil {
			return nil, err
		}
	}

	// Add edges
	for _, nodeDef := range schema.PlotNodes {
		for _, succID := range nodeDef.SuccessorIDs {
			if err := dag.AddEdge(nodeDef.ID, succID); err != nil {
				return nil, err
			}
		}
	}

	engine := &GameEngine{
		ID:             id,
		state:          state,
		dag:            dag,
		deck:           cards.NewWeightedDeque(7),
		deathLoop:      death.NewDeathLoop(state),
		jobQueue:       NewJobQueue(),
		drawnCards:     make([]cards.Card, 0),
		immediateDeque: list.New(),
	}

	return engine, nil
}

// LoadGameEngine loads an existing game
func LoadGameEngine(id string, state *GlobalBlackboard, dag *story.MacroDAG) *GameEngine {
	return &GameEngine{
		ID:             id,
		state:          state,
		dag:            dag,
		deck:           cards.NewWeightedDeque(7),
		deathLoop:      death.NewDeathLoop(state),
		jobQueue:       NewJobQueue(),
		drawnCards:     make([]cards.Card, 0),
		immediateDeque: list.New(),
	}
}

// GetState returns the current game state
func (e *GameEngine) GetState() *GlobalBlackboard {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.state
}

// GetDAG returns the story DAG
func (e *GameEngine) GetDAG() *story.MacroDAG {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.dag
}

// DrawCard draws a single card (from immediate deque first, then deck)
func (e *GameEngine) DrawCard() cards.Card {
	e.mu.Lock()
	defer e.mu.Unlock()

	if e.immediateDeque.Len() > 0 {
		elem := e.immediateDeque.Front()
		e.immediateDeque.Remove(elem)
		return elem.Value.(cards.Card)
	}

	return e.deck.Draw()
}

// DrawCards draws cards for the week
func (e *GameEngine) DrawCards(count int) ([]cards.Card, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.drawnCards = e.deck.DrawN(count)
	return e.drawnCards, nil
}

// IsWeekOver returns true if the deck is empty and no immediate cards
func (e *GameEngine) IsWeekOver() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.deck.Size() == 0 && e.immediateDeque.Len() == 0
}

// ResolveCard executes a card choice
func (e *GameEngine) ResolveCard(cardID string, direction string) (*cards.ExecuteResult, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Find the card
	var targetCard cards.Card
	var cardIndex int = -1
	for i, card := range e.drawnCards {
		if card.GetID() == cardID {
			targetCard = card
			cardIndex = i
			break
		}
	}

	if targetCard == nil {
		return nil, fmt.Errorf("card not found: %s", cardID)
	}

	result := &cards.ExecuteResult{
		StatChanges: make(map[string]int),
		TreeCards:   make([]cards.Card, 0),
		Direction:   direction,
	}

	// Execute choice
	if choiceCard, ok := targetCard.(*cards.ChoiceCard); ok {
		var choice *cards.Choice
		if direction == "left" {
			choice = choiceCard.LeftChoice
		} else if direction == "right" {
			choice = choiceCard.RightChoice
		} else {
			return nil, fmt.Errorf("invalid direction: %s", direction)
		}

		if choice == nil {
			return nil, fmt.Errorf("choice not found for direction: %s", direction)
		}

		// Execute function calls
		executor := cards.NewActionExecutor(e.state)
		for _, call := range choice.Calls {
			callMap := map[string]interface{}{
				"name":   call.Name,
				"params": call.Params,
			}
			res, err := executor.Execute(callMap)
			if err != nil {
				return nil, err
			}
			for stat, delta := range res.StatChanges {
				result.StatChanges[stat] += delta
			}
			result.TreeCards = append(result.TreeCards, res.TreeCards...)
		}

		// Add tree cards
		result.TreeCards = append(result.TreeCards, choice.TreeCards...)
	} else if infoCard, ok := targetCard.(*cards.InfoCard); ok {
		// Info cards don't have choices, just add next cards
		result.TreeCards = append(result.TreeCards, infoCard.NextCards...)
	}

	// SECURITY FIX: Remove card from drawn cards to prevent re-resolution
	e.drawnCards = append(e.drawnCards[:cardIndex], e.drawnCards[cardIndex+1:]...)

	e.state.UpdatedAt = time.Now()
	return result, nil
}

// AdvanceWeek advances the game by one week
func (e *GameEngine) AdvanceWeek() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Advance 7 days
	for i := 0; i < 7; i++ {
		e.state.AdvanceDay()
	}

	// Check plot conditions
	if err := e.checkPlotConditions(); err != nil {
		return err
	}

	// Check events
	e.checkEvents()

	// Check death
	if deathInfo, isDead := e.deathLoop.CheckDeath(); isDead {
		e.state.IsAlive = false
		e.state.DeathCause = deathInfo.CauseStat
		e.state.DeathTurn = deathInfo.Turn
		return nil
	}

	e.state.UpdatedAt = time.Now()
	return nil
}

// checkPlotConditions evaluates DAG conditions and marks pending node
func (e *GameEngine) checkPlotConditions() error {
	conditionState := e.buildConditionState()

	activatable, err := e.dag.GetActivatableNodes(conditionState)
	if err != nil {
		return err
	}

	if len(activatable) > 0 {
		// Fire the first activatable node
		node := activatable[0]
		if _, err := e.dag.FireNode(node.ID); err != nil {
			return err
		}

		// Execute node calls
		executor := cards.NewActionExecutor(e.state)
		for _, call := range node.Calls {
			callMap := map[string]interface{}{
				"name":   call.Name,
				"params": call.Params,
			}
			if _, err := executor.Execute(callMap); err != nil {
				return err
			}
		}

		e.state.PendingPlotNodeID = node.ID
	}

	return nil
}

// checkEvents checks and removes expired events
func (e *GameEngine) checkEvents() {
	toRemove := make([]string, 0)

	for eventID, event := range e.state.Events {
		switch ev := event.(type) {
		case *TimedEvent:
			if ev.IsExpired(e.state.Day, e.state.Season, e.state.Year) {
				toRemove = append(toRemove, eventID)
			}
		case *ConditionEvent:
			conditionState := e.buildConditionState()
			if result, err := e.dag.CheckCondition(eventID, conditionState); err == nil && result {
				toRemove = append(toRemove, eventID)
			}
		case *PhaseEvent:
			if ev.IsFinished() {
				toRemove = append(toRemove, eventID)
			}
		case *ProgressEvent:
			if ev.IsFinished() {
				toRemove = append(toRemove, eventID)
			}
		}
	}

	for _, eventID := range toRemove {
		e.state.RemoveEvent(eventID)
	}
}

// GetAllEventsForDisplay returns all ongoing events formatted for UI display
func (e *GameEngine) GetAllEventsForDisplay() []map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	var eventsDisplay []map[string]interface{}
	for _, event := range e.state.Events {
		display := map[string]interface{}{
			"type":        event.GetType(),
			"name":        event.GetName(),
			"icon":        event.GetIcon(),
			"description": event.GetDescription(),
			"progress":    event.ProgressDisplay(),
		}
		eventsDisplay = append(eventsDisplay, display)
	}
	return eventsDisplay
}

// GetGenerationContext builds context for Writer batch
func (e *GameEngine) GetGenerationContext() map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	return map[string]interface{}{
		"is_season_start":         e.state.Day == 1,
		"is_first_day_after_death": e.state.IsFirstDayAfterDeath,
		"snapshot":                e.buildSnapshot(),
		"dag_context":             e.dag.GetWriterContext(),
		"ongoing_events":          e.GetAllEventsForDisplay(),
		"available_tags":          e.buildAvailableTags(),
		"season": map[string]interface{}{
			"name":        e.getCurrentSeasonName(),
			"description": e.getCurrentSeasonDescription(),
			"week":        e.state.WeekInSeason(),
		},
	}
}

// buildSnapshot returns compressed state for AI context
func (e *GameEngine) buildSnapshot() map[string]interface{} {
	npcList := make([]map[string]interface{}, 0)
	for _, npc := range e.state.NPCs {
		npcList = append(npcList, map[string]interface{}{
			"id":          npc.ID,
			"name":        npc.Name,
			"enabled":     npc.Enabled,
			"appearances": npc.AppearanceCount,
		})
	}

	relationshipList := make([]map[string]interface{}, 0)
	// Add relationships from state
	for _, rel := range e.state.Relationships {
		relationshipList = append(relationshipList, map[string]interface{}{
			"a":            rel["from"],
			"b":            rel["to"],
			"relationship": rel["description"],
		})
	}

	tagList := make([]string, 0)
	for tag := range e.state.Tags {
		tagList = append(tagList, tag)
	}

	return map[string]interface{}{
		"world":        e.state.WorldName,
		"era":          e.state.Era,
		"day":          e.state.Day,
		"season":       e.state.Season,
		"year":         e.state.Year,
		"elapsed_days": e.state.GetElapsedDays(),
		"week":         e.state.WeekInSeason(),
		"life":         e.state.LifeNumber,
		"stats":        e.state.Stats,
		"tags":         tagList,
		"karma":        e.state.Karma,
		"player": map[string]interface{}{
			"name": e.state.PlayerChar.Name,
		},
		"npcs":          npcList,
		"relationships": relationshipList,
	}
}

// buildAvailableTags returns list of available tags
func (e *GameEngine) buildAvailableTags() []map[string]interface{} {
	var tags []map[string]interface{}
	for _, tagDef := range e.state.TagDefs {
		tags = append(tags, map[string]interface{}{
			"id":          tagDef["id"],
			"name":        tagDef["name"],
			"description": tagDef["description"],
		})
	}
	return tags
}

// getCurrentSeasonName returns the current season name
func (e *GameEngine) getCurrentSeasonName() string {
	seasonNames := []string{"Spring", "Summer", "Autumn", "Winter"}
	if e.state.Season >= 0 && e.state.Season < len(seasonNames) {
		return seasonNames[e.state.Season]
	}
	return "Unknown"
}

// getCurrentSeasonDescription returns the current season description
func (e *GameEngine) getCurrentSeasonDescription() string {
	if e.state.Season >= 0 && e.state.Season < len(e.state.Seasons) {
		season := e.state.Seasons[e.state.Season]
		if desc, ok := season["description"].(string); ok {
			return desc
		}
	}
	return ""
}

// GetWeekDeckSize returns how many cards to generate for a week deck
func (e *GameEngine) GetWeekDeckSize() int {
	return 7
}

// GetCommonCount returns how many common cards to generate
func (e *GameEngine) GetCommonCount() int {
	jobCount := e.jobQueue.Count()
	if 7-jobCount < 1 {
		return 1
	}
	return 7 - jobCount
}

// AddCardsFromDefs validates and inserts cards from Writer output
func (e *GameEngine) AddCardsFromDefs(cardDefs []map[string]interface{}) int {
	e.mu.Lock()
	defer e.mu.Unlock()

	count := 0
	for _, cardDef := range cardDefs {
		card := e.convertToCard(cardDef)
		if card != nil {
			e.deck.Insert(card)
			count++
		}
	}
	return count
}

// convertToCard converts a card definition map to a Card object
func (e *GameEngine) convertToCard(cardDef map[string]interface{}) cards.Card {
	id, _ := cardDef["id"].(string)
	if id == "" {
		return nil
	}

	title, _ := cardDef["title"].(string)
	description, _ := cardDef["description"].(string)
	character, _ := cardDef["character"].(string)
	source, _ := cardDef["source"].(string)
	priority := cards.PriorityCommon
	if p, ok := cardDef["priority"].(float64); ok {
		priority = int(p)
	}

	// Check if it's a choice card or info card
	if _, hasLeftChoice := cardDef["left_choice"]; hasLeftChoice {
		return &cards.ChoiceCard{
			ID:          id,
			Title:       title,
			Description: description,
			Character:   character,
			Source:      source,
			Priority:    priority,
			LeftChoice:  e.parseChoice(cardDef["left_choice"]),
			RightChoice: e.parseChoice(cardDef["right_choice"]),
		}
	}

	// Default to info card
	return &cards.InfoCard{
		ID:          id,
		Title:       title,
		Description: description,
		Character:   character,
		Source:      source,
		Priority:    priority,
	}
}

// parseChoice converts a choice definition to a Choice object
func (e *GameEngine) parseChoice(choiceDef interface{}) *cards.Choice {
	if choiceDef == nil {
		return nil
	}

	choiceMap, ok := choiceDef.(map[string]interface{})
	if !ok {
		return nil
	}

	label, _ := choiceMap["label"].(string)
	var calls []cards.FunctionCall

	if callsRaw, ok := choiceMap["calls"].([]interface{}); ok {
		for _, callRaw := range callsRaw {
			if callMap, ok := callRaw.(map[string]interface{}); ok {
				name, _ := callMap["name"].(string)
				params, _ := callMap["params"].(map[string]interface{})
				calls = append(calls, cards.FunctionCall{
					Name:   name,
					Params: params,
				})
			}
		}
	}

	return &cards.Choice{
		Label: label,
		Calls: calls,
	}
}

// OnWeekEnd handles week end lifecycle
func (e *GameEngine) OnWeekEnd() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Run season's on_week_end_calls
	if e.state.Season >= 0 && e.state.Season < len(e.state.Seasons) {
		season := e.state.Seasons[e.state.Season]
		if calls, ok := season["on_week_end_calls"].([]interface{}); ok {
			executor := cards.NewActionExecutor(e.state)
			for _, callRaw := range calls {
				if callMap, ok := callRaw.(map[string]interface{}); ok {
					executor.Execute(callMap)
				}
			}
		}
	}

	// Fire pending plot node
	if e.state.PendingPlotNodeID != "" {
		nodeID := e.state.PendingPlotNodeID
		node, err := e.dag.FireNode(nodeID)
		if err == nil && node != nil {
			executor := cards.NewActionExecutor(e.state)
			for _, call := range node.Calls {
				callMap := map[string]interface{}{
					"name":   call.Name,
					"params": call.Params,
				}
				executor.Execute(callMap)
			}

			e.jobQueue.Enqueue(&CardGenJob{
				JobType: "plot",
				Context: map[string]interface{}{
					"node_id":          node.ID,
					"plot_description": node.PlotDescription,
					"is_ending":        node.IsEnding,
				},
			})
		}
		e.state.PendingPlotNodeID = ""
	}

	// Check for finished events
	e.checkEvents()

	return nil
}

// OnSeasonEnd handles season end lifecycle
func (e *GameEngine) OnSeasonEnd() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Run previous season's on_season_end_calls
	prevSeason := (e.state.Season - 1 + 4) % 4
	if prevSeason >= 0 && prevSeason < len(e.state.Seasons) {
		season := e.state.Seasons[prevSeason]
		if calls, ok := season["on_season_end_calls"].([]interface{}); ok {
			executor := cards.NewActionExecutor(e.state)
			for _, callRaw := range calls {
				if callMap, ok := callRaw.(map[string]interface{}); ok {
					executor.Execute(callMap)
				}
			}
		}
	}

	return nil
}

// FirePendingPlot fires the pending plot node at week end
func (e *GameEngine) FirePendingPlot() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	nodeID := e.state.PendingPlotNodeID
	if nodeID == "" {
		return nil
	}

	node, err := e.dag.FireNode(nodeID)
	if err != nil {
		return err
	}

	if node == nil {
		e.state.PendingPlotNodeID = ""
		return nil
	}

	// Execute plot node function calls
	executor := cards.NewActionExecutor(e.state)
	for _, call := range node.Calls {
		callMap := map[string]interface{}{
			"name":   call.Name,
			"params": call.Params,
		}
		if _, err := executor.Execute(callMap); err != nil {
			return err
		}
	}

	// Queue Writer job for the plot card
	e.jobQueue.Enqueue(&CardGenJob{
		JobType: "plot",
		Context: map[string]interface{}{
			"node_id":          node.ID,
			"plot_description": node.PlotDescription,
			"is_ending":        node.IsEnding,
		},
	})

	e.state.PendingPlotNodeID = ""
	return nil
}

// CheckEnding checks if an ending condition is met
func (e *GameEngine) CheckEnding() *story.PlotNode {
	e.mu.RLock()
	defer e.mu.RUnlock()

	// Check DAG for ending nodes that have been fired
	for _, node := range e.dag.GetAllNodes() {
		if node.IsEnding && node.IsFired {
			return node
		}
	}
	return nil
}

// HandleDeath shows pre-generated death card
func (e *GameEngine) HandleDeath(deathInfo *death.DeathInfo) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	boundary := "min"
	// Check if stat hit max (100) or min (0)
	if deathInfo.Stats[deathInfo.CauseStat] >= 100 {
		boundary = "max"
	}

	key := fmt.Sprintf("death_%s_%s", deathInfo.CauseStat, boundary)
	deathCardRaw, exists := e.state.PendingDeathCards[key]

	var deathCard cards.Card

	if !exists {
		// Fallback: create a simple death card
		statName := deathInfo.CauseStat
		var desc string
		if boundary == "min" {
			desc = fmt.Sprintf("Your %s has fallen to nothing. The world fades to black...", statName)
		} else {
			desc = fmt.Sprintf("Your %s has spiraled beyond control. Everything collapses...", statName)
		}
		deathCard = &cards.InfoCard{
			ID:          fmt.Sprintf("death_%s", deathInfo.CauseStat),
			Title:       "☠ Death",
			Description: desc,
			Character:   "narrator",
			Source:      "info",
			Priority:    5,
		}
	} else {
		// Convert stored death card to Card object
		if deathCardMap, ok := deathCardRaw.(map[string]interface{}); ok {
			deathCard = e.convertToCard(deathCardMap)
		}
		if deathCard == nil {
			// Fallback if conversion fails
			deathCard = &cards.InfoCard{
				ID:          fmt.Sprintf("death_%s", deathInfo.CauseStat),
				Title:       "☠ Death",
				Description: "You have died.",
				Character:   "narrator",
				Source:      "info",
				Priority:    5,
			}
		}
	}

	// Add to immediate deque
	e.immediateDeque.PushBack(deathCard)
	e.awaitingResurrection = true

	return nil
}

// CompleteResurrection resurrects and prepares for fresh start
func (e *GameEngine) CompleteResurrection() error {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.awaitingResurrection = false

	// Resurrect
	e.deathLoop.Resurrect(make(map[string]bool))

	// Advance to next season
	e.state.AdvanceToNextSeason()
	e.state.IsFirstDayAfterDeath = true

	return nil
}

// IsAwaitingResurrection returns true if waiting for death card flip
func (e *GameEngine) IsAwaitingResurrection() bool {
	e.mu.RLock()
	defer e.mu.RUnlock()
	return e.awaitingResurrection
}

// AdvanceDayWithBoundaries advances one day and returns crossed boundaries
func (e *GameEngine) AdvanceDayWithBoundaries() map[string]bool {
	e.mu.Lock()
	defer e.mu.Unlock()

	oldSeason := e.state.Season
	oldYear := e.state.Year

	e.state.AdvanceDay()

	crossed := map[string]bool{
		"week_end":   false,
		"season_end": false,
	}

	// Check week boundary (every 7 days)
	if e.state.Turn == 0 {
		crossed["week_end"] = true
	}

	// Check season boundary (every 28 days)
	if oldSeason != e.state.Season || oldYear != e.state.Year {
		crossed["season_end"] = true
	}

	return crossed
}

// InsertTreeCards inserts tree cards into the immediate deque with high priority
func (e *GameEngine) InsertTreeCards(treeCards []cards.Card) {
	e.mu.Lock()
	defer e.mu.Unlock()

	for _, card := range treeCards {
		e.immediateDeque.PushBack(card)
	}
}

// CheckDeath checks if the player is dead
func (e *GameEngine) CheckDeath() (*death.DeathInfo, bool) {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.deathLoop.CheckDeath()
}

// Resurrect resurrects the player for a new life
func (e *GameEngine) Resurrect(tempTags map[string]bool) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.deathLoop.Resurrect(tempTags)
	e.dag.PartialReset()
	e.deck.Clear()
	e.drawnCards = make([]cards.Card, 0)

	e.state.UpdatedAt = time.Now()
	return nil
}

// buildConditionState builds the state map for condition evaluation
func (e *GameEngine) buildConditionState() map[string]interface{} {
	return map[string]interface{}{
		"stats":        e.state.Stats,
		"tags":         e.state.Tags,
		"day":          e.state.Day,
		"season":       e.state.Season,
		"year":         e.state.Year,
		"elapsed_days": e.state.GetElapsedDays(),
		"is_alive":     e.state.IsAlive,
		"current_life": e.state.CurrentLife,
	}
}

// GetGameInfo returns basic game information
func (e *GameEngine) GetGameInfo() map[string]interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()

	return map[string]interface{}{
		"id":            e.ID,
		"world_name":    e.state.WorldName,
		"era":           e.state.Era,
		"day":           e.state.Day,
		"season":        e.state.Season,
		"year":          e.state.Year,
		"is_alive":      e.state.IsAlive,
		"current_life":  e.state.CurrentLife,
		"created_at":    e.state.CreatedAt,
		"updated_at":    e.state.UpdatedAt,
	}
}
