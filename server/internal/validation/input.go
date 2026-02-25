package validation

import (
	"fmt"
	"regexp"
)

// ValidateGameID validates game ID format
func ValidateGameID(id string) error {
	if len(id) == 0 || len(id) > 64 {
		return fmt.Errorf("game ID must be 1-64 characters")
	}

	// Allow alphanumeric, hyphens, underscores
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_-]+$`, id)
	if !matched {
		return fmt.Errorf("game ID can only contain alphanumeric characters, hyphens, and underscores")
	}

	return nil
}

// ValidateCardID validates card ID format
func ValidateCardID(id string) error {
	if len(id) == 0 || len(id) > 128 {
		return fmt.Errorf("card ID must be 1-128 characters")
	}

	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_-]+$`, id)
	if !matched {
		return fmt.Errorf("card ID can only contain alphanumeric characters, hyphens, and underscores")
	}

	return nil
}

// ValidateDirection validates card resolution direction
func ValidateDirection(direction string) error {
	if direction != "left" && direction != "right" {
		return fmt.Errorf("direction must be 'left' or 'right'")
	}
	return nil
}

// ValidateDelta validates stat delta
func ValidateDelta(delta float64) error {
	if delta < -50 || delta > 50 {
		return fmt.Errorf("delta must be between -50 and 50")
	}
	return nil
}
