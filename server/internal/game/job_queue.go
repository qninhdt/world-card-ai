package game

import "container/list"

// CardGenJob represents a single card generation job for the Writer
type CardGenJob struct {
	JobType string                 `json:"job_type"` // "plot" | "event_start" | "event_phase" | "chain" | "info"
	Context map[string]interface{} `json:"context"`  // Extra context: plot description, event def, chain tag, etc.
}

// JobQueue accumulates card generation jobs between Writer calls
type JobQueue struct {
	pending *list.List // *CardGenJob
}

// NewJobQueue creates a new job queue
func NewJobQueue() *JobQueue {
	return &JobQueue{
		pending: list.New(),
	}
}

// Enqueue adds a job to the queue
func (jq *JobQueue) Enqueue(job *CardGenJob) {
	jq.pending.PushBack(job)
}

// Drain pops all pending jobs and returns them
func (jq *JobQueue) Drain() []*CardGenJob {
	var jobs []*CardGenJob
	for elem := jq.pending.Front(); elem != nil; elem = elem.Next() {
		jobs = append(jobs, elem.Value.(*CardGenJob))
	}
	jq.pending.Init()
	return jobs
}

// HasJobs returns true if there are pending jobs
func (jq *JobQueue) HasJobs() bool {
	return jq.pending.Len() > 0
}

// Count returns the number of pending jobs
func (jq *JobQueue) Count() int {
	return jq.pending.Len()
}

// HasHighPriority returns true if there's a job that should force early generation
func (jq *JobQueue) HasHighPriority() bool {
	for elem := jq.pending.Front(); elem != nil; elem = elem.Next() {
		job := elem.Value.(*CardGenJob)
		if job.JobType == "event_start" || job.JobType == "plot" {
			return true
		}
	}
	return false
}
