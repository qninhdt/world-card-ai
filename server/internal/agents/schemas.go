package agents

// FunctionCall represents an AI-generated function call
type FunctionCall struct {
	Name   string                 `json:"name"`
	Params map[string]interface{} `json:"params"`
}

// StatDef defines a game stat
type StatDef struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// EntityDef is a base entity definition
type EntityDef struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// PlayerCharacterDef defines the player character
type PlayerCharacterDef struct {
	EntityDef
	Description string `json:"description"`
}

// NPCDef defines a non-player character
type NPCDef struct {
	EntityDef
	Description string `json:"description"`
	Appearance  string `json:"appearance"`
}

// RelationshipDef defines a relationship between entities
type RelationshipDef struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Description string `json:"description"`
}

// TagDef defines a player tag
type TagDef struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	IsTemp      bool   `json:"is_temp"`
}

// SeasonDef defines a season
type SeasonDef struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// PlotNodeDef defines a story plot node
type PlotNodeDef struct {
	ID               string          `json:"id"`
	PlotDescription  string          `json:"plot_description"`
	Condition        string          `json:"condition"`
	Calls            []FunctionCall  `json:"calls"`
	IsEnding         bool            `json:"is_ending"`
	PredecessorIDs   []string        `json:"predecessor_ids"`
	SuccessorIDs     []string        `json:"successor_ids"`
}

// WorldGenSchema is the complete world generation output
type WorldGenSchema struct {
	Name          string                 `json:"name"`
	Era           string                 `json:"era"`
	Description   string                 `json:"description"`
	Stats         []StatDef              `json:"stats"`
	Tags          []TagDef               `json:"tags"`
	Seasons       []SeasonDef            `json:"seasons"`
	PlayerChar    PlayerCharacterDef     `json:"player_character"`
	NPCs          []NPCDef               `json:"npcs"`
	Relationships []RelationshipDef      `json:"relationships"`
	PlotNodes     []PlotNodeDef          `json:"plot_nodes"`
	InitialStats  map[string]int         `json:"initial_stats"`
	InitialTags   []string               `json:"initial_tags"`
}
