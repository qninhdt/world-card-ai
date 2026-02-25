package cards

import (
	"sort"
)

// WeightedDeque is a priority-based card deck
type WeightedDeque struct {
	cards    []Card
	capacity int
}

// NewWeightedDeque creates a new deck with given capacity
func NewWeightedDeque(capacity int) *WeightedDeque {
	return &WeightedDeque{
		cards:    make([]Card, 0, capacity),
		capacity: capacity,
	}
}

// Insert adds a card to the deck, maintaining priority order
func (d *WeightedDeque) Insert(card Card) {
	d.cards = append(d.cards, card)
	sort.Slice(d.cards, func(i, j int) bool {
		return d.cards[i].GetPriority() > d.cards[j].GetPriority()
	})

	// Evict lowest priority cards if over capacity
	for len(d.cards) > d.capacity {
		d.evictLowestPriority()
	}
}

// evictLowestPriority removes the lowest priority card
// Never evicts plot/event/tree/story cards
func (d *WeightedDeque) evictLowestPriority() {
	for i := len(d.cards) - 1; i >= 0; i-- {
		priority := d.cards[i].GetPriority()
		// Only evict common cards (priority 1)
		if priority == PriorityCommon {
			d.cards = append(d.cards[:i], d.cards[i+1:]...)
			return
		}
	}
}

// Draw removes and returns the last card (lowest priority)
func (d *WeightedDeque) Draw() Card {
	if len(d.cards) == 0 {
		return nil
	}
	card := d.cards[len(d.cards)-1]
	d.cards = d.cards[:len(d.cards)-1]
	return card
}

// DrawN draws n cards from the deck
func (d *WeightedDeque) DrawN(n int) []Card {
	result := make([]Card, 0, n)
	for i := 0; i < n && len(d.cards) > 0; i++ {
		result = append(result, d.Draw())
	}
	return result
}

// Peek returns the next card without removing it
func (d *WeightedDeque) Peek() Card {
	if len(d.cards) == 0 {
		return nil
	}
	return d.cards[len(d.cards)-1]
}

// Size returns the number of cards in the deck
func (d *WeightedDeque) Size() int {
	return len(d.cards)
}

// Clear removes all cards
func (d *WeightedDeque) Clear() {
	d.cards = make([]Card, 0, d.capacity)
}

// GetAll returns all cards in the deck
func (d *WeightedDeque) GetAll() []Card {
	result := make([]Card, len(d.cards))
	copy(result, d.cards)
	return result
}
