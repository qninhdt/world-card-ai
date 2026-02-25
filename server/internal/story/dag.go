package story

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/expr-lang/expr"
	"github.com/expr-lang/expr/vm"
	"github.com/qninhdt/world-card-ai-2/server/internal/agents"
)

// PlotNode represents a story beat in the DAG
type PlotNode struct {
	ID               string                   `json:"id"`
	PlotDescription  string                   `json:"plot_description"`
	Condition        string                   `json:"condition"`
	Calls            []agents.FunctionCall    `json:"calls"`
	IsEnding         bool                     `json:"is_ending"`
	IsFired          bool                     `json:"is_fired"`
	PredecessorIDs   []string                 `json:"predecessor_ids"`
	SuccessorIDs     []string                 `json:"successor_ids"`
	compiledProgram  *vm.Program              `json:"-"`
}

// MacroDAG wraps a directed acyclic graph for story progression
type MacroDAG struct {
	nodes map[string]*PlotNode
	mu    sync.RWMutex
}

// NewMacroDAG creates a new empty DAG
func NewMacroDAG() *MacroDAG {
	return &MacroDAG{
		nodes: make(map[string]*PlotNode),
	}
}

// AddNode adds a plot node to the DAG
func (dag *MacroDAG) AddNode(node *PlotNode) error {
	dag.mu.Lock()
	defer dag.mu.Unlock()

	if _, exists := dag.nodes[node.ID]; exists {
		return fmt.Errorf("node %s already exists", node.ID)
	}

	// Pre-compile condition expression
	if node.Condition != "" {
		program, err := expr.Compile(node.Condition)
		if err != nil {
			return fmt.Errorf("invalid condition for node %s: %w", node.ID, err)
		}
		node.compiledProgram = program
	}

	dag.nodes[node.ID] = node
	return nil
}

// AddEdge adds a directed edge from one node to another
func (dag *MacroDAG) AddEdge(fromID, toID string) error {
	dag.mu.Lock()
	defer dag.mu.Unlock()

	from, ok := dag.nodes[fromID]
	if !ok {
		return fmt.Errorf("source node %s not found", fromID)
	}

	to, ok := dag.nodes[toID]
	if !ok {
		return fmt.Errorf("target node %s not found", toID)
	}

	// Add edge
	from.SuccessorIDs = append(from.SuccessorIDs, toID)
	to.PredecessorIDs = append(to.PredecessorIDs, fromID)

	return nil
}

// GetNode returns a node by ID
func (dag *MacroDAG) GetNode(id string) *PlotNode {
	dag.mu.RLock()
	defer dag.mu.RUnlock()
	return dag.nodes[id]
}

// GetAllNodes returns all nodes
func (dag *MacroDAG) GetAllNodes() []*PlotNode {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	nodes := make([]*PlotNode, 0, len(dag.nodes))
	for _, node := range dag.nodes {
		nodes = append(nodes, node)
	}
	return nodes
}

// CheckCondition safely evaluates a node's condition against state
func (dag *MacroDAG) CheckCondition(nodeID string, state map[string]interface{}) (bool, error) {
	dag.mu.RLock()
	node, ok := dag.nodes[nodeID]
	dag.mu.RUnlock()

	if !ok {
		return false, fmt.Errorf("node %s not found", nodeID)
	}

	if node.Condition == "" {
		return true, nil // no condition = always true
	}

	if node.compiledProgram == nil {
		program, err := expr.Compile(node.Condition)
		if err != nil {
			return false, fmt.Errorf("invalid condition: %w", err)
		}
		node.compiledProgram = program
	}

	// SECURITY FIX: Add timeout to prevent DoS
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	// Create a channel to receive the result
	resultChan := make(chan interface{}, 1)
	errChan := make(chan error, 1)

	go func() {
		result, err := vm.Run(node.compiledProgram, state)
		if err != nil {
			errChan <- err
		} else {
			resultChan <- result
		}
	}()

	select {
	case <-ctx.Done():
		return false, fmt.Errorf("condition evaluation timeout")
	case err := <-errChan:
		return false, fmt.Errorf("condition evaluation error: %w", err)
	case result := <-resultChan:
		boolResult, ok := result.(bool)
		if !ok {
			return false, fmt.Errorf("condition did not evaluate to boolean")
		}
		return boolResult, nil
	}
}

// GetActivatableNodes returns nodes that are ready to fire
// (all predecessors fired AND condition met)
func (dag *MacroDAG) GetActivatableNodes(state map[string]interface{}) ([]*PlotNode, error) {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	var activatable []*PlotNode

	for _, node := range dag.nodes {
		if node.IsFired {
			continue // already fired
		}

		// Check if all predecessors are fired
		allPredecessorsFired := true
		if len(node.PredecessorIDs) == 0 {
			allPredecessorsFired = true // no predecessors = can fire
		} else {
			for _, predID := range node.PredecessorIDs {
				pred := dag.nodes[predID]
				if !pred.IsFired {
					allPredecessorsFired = false
					break
				}
			}
		}

		if !allPredecessorsFired {
			continue
		}

		// Check condition
		if node.Condition != "" {
			if node.compiledProgram == nil {
				program, err := expr.Compile(node.Condition)
				if err != nil {
					return nil, fmt.Errorf("invalid condition for node %s: %w", node.ID, err)
				}
				node.compiledProgram = program
			}

			result, err := vm.Run(node.compiledProgram, state)
			if err != nil {
				return nil, fmt.Errorf("condition evaluation error for node %s: %w", node.ID, err)
			}

			boolResult, ok := result.(bool)
			if !ok || !boolResult {
				continue
			}
		}

		activatable = append(activatable, node)
	}

	return activatable, nil
}

// FireNode marks a node as fired and returns it
func (dag *MacroDAG) FireNode(id string) (*PlotNode, error) {
	dag.mu.Lock()
	defer dag.mu.Unlock()

	node, ok := dag.nodes[id]
	if !ok {
		return nil, fmt.Errorf("node %s not found", id)
	}

	node.IsFired = true
	return node, nil
}

// CheckEnding checks if any ending node has fired
func (dag *MacroDAG) CheckEnding() bool {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	for _, node := range dag.nodes {
		if node.IsEnding && node.IsFired {
			return true
		}
	}
	return false
}

// PartialReset resets non-ending nodes (for resurrection)
func (dag *MacroDAG) PartialReset() {
	dag.mu.Lock()
	defer dag.mu.Unlock()

	for _, node := range dag.nodes {
		if !node.IsEnding {
			node.IsFired = false
		}
	}
}

// GetWriterContext returns a pruned DAG for AI context
// (only includes fired nodes and their immediate successors)
func (dag *MacroDAG) GetWriterContext() map[string]interface{} {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	firedNodes := make([]map[string]interface{}, 0)
	nextNodes := make([]map[string]interface{}, 0)

	for _, node := range dag.nodes {
		if node.IsFired {
			firedNodes = append(firedNodes, map[string]interface{}{
				"id":                 node.ID,
				"plot_description":   node.PlotDescription,
				"is_ending":          node.IsEnding,
			})

			// Add successors
			for _, succID := range node.SuccessorIDs {
				succ := dag.nodes[succID]
				if !succ.IsFired {
					nextNodes = append(nextNodes, map[string]interface{}{
						"id":                 succ.ID,
						"plot_description":   succ.PlotDescription,
						"condition":          succ.Condition,
					})
				}
			}
		}
	}

	return map[string]interface{}{
		"fired_nodes": firedNodes,
		"next_nodes":  nextNodes,
	}
}

// GetVisualGraph returns the full DAG for visualization
func (dag *MacroDAG) GetVisualGraph() map[string]interface{} {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	nodes := make([]map[string]interface{}, 0)
	edges := make([]map[string]interface{}, 0)

	for _, node := range dag.nodes {
		nodes = append(nodes, map[string]interface{}{
			"id":                 node.ID,
			"plot_description":   node.PlotDescription,
			"condition":          node.Condition,
			"is_ending":          node.IsEnding,
			"is_fired":           node.IsFired,
		})

		for _, succID := range node.SuccessorIDs {
			edges = append(edges, map[string]interface{}{
				"from": node.ID,
				"to":   succID,
			})
		}
	}

	return map[string]interface{}{
		"nodes": nodes,
		"edges": edges,
	}
}

// MarshalJSON implements json.Marshaler
func (dag *MacroDAG) MarshalJSON() ([]byte, error) {
	dag.mu.RLock()
	defer dag.mu.RUnlock()

	nodes := make([]*PlotNode, 0, len(dag.nodes))
	for _, node := range dag.nodes {
		nodes = append(nodes, node)
	}

	return json.Marshal(nodes)
}

// UnmarshalJSON implements json.Unmarshaler
func (dag *MacroDAG) UnmarshalJSON(data []byte) error {
	var nodes []*PlotNode
	if err := json.Unmarshal(data, &nodes); err != nil {
		return err
	}

	dag.mu.Lock()
	defer dag.mu.Unlock()

	dag.nodes = make(map[string]*PlotNode)
	for _, node := range nodes {
		// Pre-compile condition
		if node.Condition != "" {
			program, err := expr.Compile(node.Condition)
			if err != nil {
				return fmt.Errorf("invalid condition for node %s: %w", node.ID, err)
			}
			node.compiledProgram = program
		}
		dag.nodes[node.ID] = node
	}

	return nil
}
