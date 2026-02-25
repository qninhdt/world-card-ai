package cards

// Priority levels for card deck
const (
	PriorityFilter = iota
	PriorityCommon
	PriorityEvent
	PriorityPlot
	PriorityTree
	PriorityStory
)

// Card is the base interface for all cards
type Card interface {
	GetID() string
	GetTitle() string
	GetDescription() string
	GetCharacter() string
	GetSource() string
	GetPriority() int
	IsChoiceCard() bool
}

// FunctionCall represents an AI-generated function call
type FunctionCall struct {
	Name   string                 `json:"name"`
	Params map[string]interface{} `json:"params"`
}

// ChoiceCard represents a card with left/right choices
type ChoiceCard struct {
	ID          string         `json:"id"`
	Title       string         `json:"title"`
	Description string         `json:"description"`
	Character   string         `json:"character"`
	Source      string         `json:"source"`
	Priority    int            `json:"priority"`
	LeftChoice  *Choice        `json:"left_choice"`
	RightChoice *Choice        `json:"right_choice"`
	TreeCards   []Card         `json:"tree_cards,omitempty"`
}

// Choice represents a single choice option
type Choice struct {
	Label        string         `json:"label"`
	Calls        []FunctionCall `json:"calls"`
	TreeCards    []Card         `json:"tree_cards,omitempty"`
}

// InfoCard represents a read-only information card
type InfoCard struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Character   string `json:"character"`
	Source      string `json:"source"`
	Priority    int    `json:"priority"`
	NextCards   []Card `json:"next_cards,omitempty"`
}

// Implement Card interface for ChoiceCard
func (c *ChoiceCard) GetID() string          { return c.ID }
func (c *ChoiceCard) GetTitle() string       { return c.Title }
func (c *ChoiceCard) GetDescription() string { return c.Description }
func (c *ChoiceCard) GetCharacter() string   { return c.Character }
func (c *ChoiceCard) GetSource() string      { return c.Source }
func (c *ChoiceCard) GetPriority() int       { return c.Priority }
func (c *ChoiceCard) IsChoiceCard() bool     { return true }

// Implement Card interface for InfoCard
func (c *InfoCard) GetID() string          { return c.ID }
func (c *InfoCard) GetTitle() string       { return c.Title }
func (c *InfoCard) GetDescription() string { return c.Description }
func (c *InfoCard) GetCharacter() string   { return c.Character }
func (c *InfoCard) GetSource() string      { return c.Source }
func (c *InfoCard) GetPriority() int       { return c.Priority }
func (c *InfoCard) IsChoiceCard() bool     { return false }
