package death

// DeathInfo contains information about a death event
type DeathInfo struct {
	CauseStat string            `json:"cause_stat"`
	Turn      int               `json:"turn"`
	LifeNumber int              `json:"life_number"`
	Tags      map[string]bool   `json:"tags"`
	Stats     map[string]int    `json:"stats"`
}

// GameState is an interface for game state operations
type GameState interface {
	GetElapsedDays() int
	GetStats() map[string]int
	GetTags() map[string]bool
	GetNPCIDs() []string
	DisableNPC(id string)
	ClearEvents()
	SetIsAlive(alive bool)
	SetDeathCause(cause string)
	SetDeathTurn(turn int)
	SetSeason(season int)
	SetYear(year int)
	SetDay(day int)
	SetTags(tags map[string]bool)
	SetCurrentLife(life int)
}

// DeathLoop handles death detection and resurrection
type DeathLoop struct {
	state GameState
}

// NewDeathLoop creates a new death loop
func NewDeathLoop(state GameState) *DeathLoop {
	return &DeathLoop{state: state}
}

// CheckDeath detects when any stat hits 0 or 100
func (dl *DeathLoop) CheckDeath() (*DeathInfo, bool) {
	stats := dl.state.GetStats()
	for statID, value := range stats {
		if value <= 0 || value >= 100 {
			deathInfo := &DeathInfo{
				CauseStat:  statID,
				Turn:       dl.state.GetElapsedDays(),
				LifeNumber: 1, // Will be set by caller
				Tags:       make(map[string]bool),
				Stats:      make(map[string]int),
			}

			// Copy current state
			for k, v := range dl.state.GetTags() {
				deathInfo.Tags[k] = v
			}
			for k, v := range stats {
				deathInfo.Stats[k] = v
			}

			dl.state.SetIsAlive(false)
			dl.state.SetDeathCause(statID)
			dl.state.SetDeathTurn(dl.state.GetElapsedDays())

			return deathInfo, true
		}
	}

	return nil, false
}

// Resurrect resets world for new life
func (dl *DeathLoop) Resurrect(tempTags map[string]bool) {
	// Keep non-temp tags as "karma" (up to 10)
	karmaTags := make(map[string]bool)
	count := 0
	for tagID, active := range dl.state.GetTags() {
		if active && !tempTags[tagID] && count < 10 {
			karmaTags[tagID] = true
			count++
		}
	}

	// Reset stats to 50
	stats := dl.state.GetStats()
	for statID := range stats {
		stats[statID] = 50
	}

	// Clear NPC appearances
	for _, npcID := range dl.state.GetNPCIDs() {
		dl.state.DisableNPC(npcID)
	}

	// Clear events
	dl.state.ClearEvents()

	// Advance to next season
	season := 0 // Will be set by caller
	year := 0   // Will be set by caller
	season++
	if season > 3 {
		season = 0
		year++
	}

	dl.state.SetSeason(season)
	dl.state.SetYear(year)
	dl.state.SetDay(1)

	// Reset tags to karma only
	dl.state.SetTags(karmaTags)

	// Update life counter
	dl.state.SetCurrentLife(1) // Will be incremented by caller
	dl.state.SetIsAlive(true)
	dl.state.SetDeathCause("")
	dl.state.SetDeathTurn(0)
}
