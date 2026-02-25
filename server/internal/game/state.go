package game

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
)

// NPC represents a non-player character
type NPC struct {
	ID              string `json:"id"`
	Name            string `json:"name"`
	Appearance      string `json:"appearance"`
	Enabled         bool   `json:"enabled"`
	AppearanceCount int    `json:"appearance_count"`
}

// PlayerCharacter represents the player character
type PlayerCharacter struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// GlobalBlackboard is the single source of truth for game state
type GlobalBlackboard struct {
	// World metadata
	WorldName string `json:"world_name"`
	Era       string `json:"era"`
	YearStart int    `json:"year_start"`

	// Characters
	PlayerChar PlayerCharacter `json:"player_character"`
	NPCs       map[string]NPC  `json:"npcs"` // keyed by NPC ID

	// Game state
	Stats  map[string]int `json:"stats"`  // keyed by stat ID, values 0-100
	Tags   map[string]bool `json:"tags"`  // keyed by tag ID
	Events map[string]Event `json:"events"` // keyed by event ID

	// Time tracking
	Day              int `json:"day"`               // 1-28
	Season           int `json:"season"`            // 0-3
	Year             int `json:"year_in_game"`
	StartDay         int `json:"start_day"`         // for elapsed time calculation
	StartSeason      int `json:"start_season"`      // for elapsed time calculation
	StartYear        int `json:"start_year"`        // for elapsed time calculation
	Turn             int `json:"turn"`              // actions this week (0-6)

	// Plot state
	PendingPlotNodeID string `json:"pending_plot_node_id"`

	// Death/resurrection state
	IsAlive              bool     `json:"is_alive"`
	CurrentLife          int      `json:"current_life"`
	DeathCause           string   `json:"death_cause"`
	DeathTurn            int      `json:"death_turn"`
	Karma                []string `json:"karma"`                    // tags from previous lives
	LifeNumber           int      `json:"life_number"`              // current life count
	ResurrectionMechanic string   `json:"resurrection_mechanic"`
	ResurrectionFlavor   string   `json:"resurrection_flavor"`
	PreviousLifeTags     []string `json:"previous_life_tags"`       // tags from last life
	IsFirstDayAfterDeath bool     `json:"is_first_day_after_death"` // flag for first day after resurrection

	// Structural cards
	WelcomeCard      interface{}            `json:"welcome_card"`
	RebornCard       interface{}            `json:"reborn_card"`
	SeasonCard       interface{}            `json:"season_card"`
	DeathCard        interface{}            `json:"death_card"`
	PendingDeathCards map[string]interface{} `json:"pending_death_cards"`

	// Definitions
	Seasons       []map[string]interface{} `json:"seasons"`       // season definitions
	TagDefs       []map[string]interface{} `json:"tag_defs"`      // tag definitions
	Relationships []map[string]interface{} `json:"relationships"` // relationship definitions

	// Timestamps
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// NewGlobalBlackboard creates a new game state from a world schema
func NewGlobalBlackboard(schema *agents.WorldGenSchema) *GlobalBlackboard {
	state := &GlobalBlackboard{
		WorldName:  schema.Name,
		Era:        schema.Era,
		YearStart:  0,
		PlayerChar: PlayerCharacter{
			ID:          schema.PlayerChar.ID,
			Name:        schema.PlayerChar.Name,
			Description: schema.PlayerChar.Description,
		},
		NPCs:                 make(map[string]NPC),
		Stats:                make(map[string]int),
		Tags:                 make(map[string]bool),
		Events:               make(map[string]Event),
		Day:                  1,
		Season:               0,
		Year:                 0,
		StartDay:             1,
		StartSeason:          0,
		StartYear:            0,
		Turn:                 0,
		IsAlive:              true,
		CurrentLife:          1,
		LifeNumber:           1,
		Karma:                make([]string, 0),
		PreviousLifeTags:     make([]string, 0),
		IsFirstDayAfterDeath: false,
		PendingDeathCards:    make(map[string]interface{}),
		Seasons:              make([]map[string]interface{}, 0),
		TagDefs:              make([]map[string]interface{}, 0),
		Relationships:        make([]map[string]interface{}, 0),
		CreatedAt:            time.Now(),
		UpdatedAt:            time.Now(),
	}

	// Initialize seasons
	for _, season := range schema.Seasons {
		state.Seasons = append(state.Seasons, map[string]interface{}{
			"id":          season.ID,
			"name":        season.Name,
			"description": season.Description,
		})
	}

	// Initialize tag definitions
	for _, tag := range schema.Tags {
		state.TagDefs = append(state.TagDefs, map[string]interface{}{
			"id":          tag.ID,
			"name":        tag.Name,
			"description": tag.Description,
			"is_temp":     tag.IsTemp,
		})
	}

	// Initialize relationships
	for _, rel := range schema.Relationships {
		state.Relationships = append(state.Relationships, map[string]interface{}{
			"from":        rel.From,
			"to":          rel.To,
			"description": rel.Description,
		})
	}

	// Initialize NPCs
	for _, npc := range schema.NPCs {
		state.NPCs[npc.ID] = NPC{
			ID:         npc.ID,
			Name:       npc.Name,
			Appearance: npc.Appearance,
			Enabled:    true,
		}
	}

	// Initialize stats
	for _, stat := range schema.Stats {
		if val, ok := schema.InitialStats[stat.ID]; ok {
			state.Stats[stat.ID] = val
		} else {
			state.Stats[stat.ID] = 50 // default
		}
	}

	// Initialize tags
	for _, tagID := range schema.InitialTags {
		state.Tags[tagID] = true
	}

	return state
}

// GetStat returns a stat value, clamped to 0-100
func (s *GlobalBlackboard) GetStat(id string) int {
	val, ok := s.Stats[id]
	if !ok {
		return 50
	}
	if val < 0 {
		return 0
	}
	if val > 100 {
		return 100
	}
	return val
}

// SetStat sets a stat value, clamped to 0-100
func (s *GlobalBlackboard) SetStat(id string, value int) {
	if value < 0 {
		value = 0
	}
	if value > 100 {
		value = 100
	}
	s.Stats[id] = value
	s.UpdatedAt = time.Now()
}

// UpdateStat updates a stat by delta, clamped to 0-100
func (s *GlobalBlackboard) UpdateStat(id string, delta int) {
	current := s.GetStat(id)
	s.SetStat(id, current+delta)
}

// HasTag checks if a tag is active
func (s *GlobalBlackboard) HasTag(id string) bool {
	return s.Tags[id]
}

// AddTag adds a tag
func (s *GlobalBlackboard) AddTag(id string) {
	s.Tags[id] = true
	s.UpdatedAt = time.Now()
}

// RemoveTag removes a tag
func (s *GlobalBlackboard) RemoveTag(id string) {
	delete(s.Tags, id)
	s.UpdatedAt = time.Now()
}

// GetNPC returns an NPC by ID
func (s *GlobalBlackboard) GetNPC(id string) *NPC {
	npc, ok := s.NPCs[id]
	if !ok {
		return nil
	}
	return &npc
}

// EnableNPC enables an NPC
func (s *GlobalBlackboard) EnableNPC(id string) {
	if npc, ok := s.NPCs[id]; ok {
		npc.Enabled = true
		s.NPCs[id] = npc
		s.UpdatedAt = time.Now()
	}
}

// DisableNPC disables an NPC
func (s *GlobalBlackboard) DisableNPC(id string) {
	if npc, ok := s.NPCs[id]; ok {
		npc.Enabled = false
		s.NPCs[id] = npc
		s.UpdatedAt = time.Now()
	}
}

// AddEvent adds an event
func (s *GlobalBlackboard) AddEvent(event Event) {
	s.Events[event.GetID()] = event
	s.UpdatedAt = time.Now()
}

// RemoveEvent removes an event
func (s *GlobalBlackboard) RemoveEvent(id string) {
	delete(s.Events, id)
	s.UpdatedAt = time.Now()
}

// GetEvent returns an event by ID
func (s *GlobalBlackboard) GetEvent(id string) Event {
	return s.Events[id]
}

// AdvanceDay advances the calendar by one day
func (s *GlobalBlackboard) AdvanceDay() {
	s.Day++
	s.Turn++
	if s.Day > 28 {
		s.Day = 1
		s.Turn = 0
		s.Season++
		if s.Season > 3 {
			s.Season = 0
			s.Year++
		}
	}
	s.UpdatedAt = time.Now()
}

// GetElapsedDays returns total days elapsed since start
func (s *GlobalBlackboard) GetElapsedDays() int {
	currentAbs := (s.Year * 112) + (s.Season * 28) + s.Day
	startAbs := (s.StartYear * 112) + (s.StartSeason * 28) + s.StartDay
	return currentAbs - startAbs
}

// GetStats returns a copy of stats map
func (s *GlobalBlackboard) GetStats() map[string]int {
	result := make(map[string]int)
	for k, v := range s.Stats {
		result[k] = v
	}
	return result
}

// GetTags returns a copy of tags map
func (s *GlobalBlackboard) GetTags() map[string]bool {
	result := make(map[string]bool)
	for k, v := range s.Tags {
		result[k] = v
	}
	return result
}

// GetNPCIDs returns all NPC IDs
func (s *GlobalBlackboard) GetNPCIDs() []string {
	result := make([]string, 0, len(s.NPCs))
	for id := range s.NPCs {
		result = append(result, id)
	}
	return result
}

// ClearEvents clears all events
func (s *GlobalBlackboard) ClearEvents() {
	s.Events = make(map[string]Event)
	s.UpdatedAt = time.Now()
}

// SetIsAlive sets the alive state
func (s *GlobalBlackboard) SetIsAlive(alive bool) {
	s.IsAlive = alive
	s.UpdatedAt = time.Now()
}

// SetDeathCause sets the death cause
func (s *GlobalBlackboard) SetDeathCause(cause string) {
	s.DeathCause = cause
	s.UpdatedAt = time.Now()
}

// SetDeathTurn sets the death turn
func (s *GlobalBlackboard) SetDeathTurn(turn int) {
	s.DeathTurn = turn
	s.UpdatedAt = time.Now()
}

// SetSeason sets the season
func (s *GlobalBlackboard) SetSeason(season int) {
	s.Season = season
	s.UpdatedAt = time.Now()
}

// SetYear sets the year
func (s *GlobalBlackboard) SetYear(year int) {
	s.Year = year
	s.UpdatedAt = time.Now()
}

// SetDay sets the day
func (s *GlobalBlackboard) SetDay(day int) {
	s.Day = day
	s.UpdatedAt = time.Now()
}

// SetTags sets the tags map
func (s *GlobalBlackboard) SetTags(tags map[string]bool) {
	s.Tags = tags
	s.UpdatedAt = time.Now()
}

// SetCurrentLife sets the current life
func (s *GlobalBlackboard) SetCurrentLife(life int) {
	s.CurrentLife = life
	s.UpdatedAt = time.Now()
}

// WeekInSeason returns current week within the season (1-4)
func (s *GlobalBlackboard) WeekInSeason() int {
	return ((s.Day - 1) / 7) + 1
}

// DateDisplay returns formatted date string (e.g. "Day 5, Spring, Year 1")
func (s *GlobalBlackboard) DateDisplay() string {
	seasonNames := []string{"Spring", "Summer", "Autumn", "Winter"}
	seasonName := "Unknown"
	if s.Season >= 0 && s.Season < len(seasonNames) {
		seasonName = seasonNames[s.Season]
	}
	return fmt.Sprintf("Day %d, %s, Year %d", s.Day, seasonName, s.Year)
}

// ElapsedDisplay returns formatted elapsed time (e.g. "1y 2s 5d")
func (s *GlobalBlackboard) ElapsedDisplay() string {
	elapsed := s.GetElapsedDays()
	years := elapsed / 112
	rem := elapsed % 112
	seasons := rem / 28
	days := rem % 28

	var parts []string
	if years > 0 {
		parts = append(parts, fmt.Sprintf("%dy", years))
	}
	if seasons > 0 {
		parts = append(parts, fmt.Sprintf("%ds", seasons))
	}
	parts = append(parts, fmt.Sprintf("%dd", days))

	return strings.Join(parts, " ")
}

// GetEnabledNPCs returns list of enabled NPCs
func (s *GlobalBlackboard) GetEnabledNPCs() []NPC {
	var result []NPC
	for _, npc := range s.NPCs {
		if npc.Enabled {
			result = append(result, npc)
		}
	}
	return result
}

// GetEnabledNPCNames returns list of enabled NPC names
func (s *GlobalBlackboard) GetEnabledNPCNames() []string {
	var result []string
	for _, npc := range s.GetEnabledNPCs() {
		result = append(result, npc.Name)
	}
	return result
}

// AdvanceToNextSeason skips remaining days and starts Day 1 of next season
func (s *GlobalBlackboard) AdvanceToNextSeason() {
	s.Day = 1
	s.Season = (s.Season + 1) % 4
	if s.Season == 0 {
		s.Year++
	}
	s.UpdatedAt = time.Now()
}
func (s *GlobalBlackboard) MarshalJSON() ([]byte, error) {
	type Alias GlobalBlackboard
	return json.Marshal(&struct {
		*Alias
		Events map[string]json.RawMessage `json:"events"`
	}{
		Alias: (*Alias)(s),
		Events: func() map[string]json.RawMessage {
			result := make(map[string]json.RawMessage)
			for k, v := range s.Events {
				if data, err := json.Marshal(v); err == nil {
					result[k] = data
				}
			}
			return result
		}(),
	})
}

// UnmarshalJSON implements json.Unmarshaler
func (s *GlobalBlackboard) UnmarshalJSON(data []byte) error {
	type Alias GlobalBlackboard
	aux := &struct {
		*Alias
		Events map[string]json.RawMessage `json:"events"`
	}{
		Alias: (*Alias)(s),
	}

	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	s.Events = make(map[string]Event)
	for k, v := range aux.Events {
		if event, err := UnmarshalEvent(v); err == nil {
			s.Events[k] = event
		}
	}

	return nil
}
