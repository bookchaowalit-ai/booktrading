package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/logger"
)

// AuditLog represents an audit log entry
type AuditLog struct {
	ID         string         `json:"id"`
	UserID     *string        `json:"user_id,omitempty"`
	Action     string         `json:"action"`
	Resource   *string        `json:"resource,omitempty"`
	ResourceID *string        `json:"resource_id,omitempty"`
	Details    map[string]any `json:"details,omitempty"`
	IPAddress  *string        `json:"ip_address,omitempty"`
	UserAgent  *string        `json:"user_agent,omitempty"`
	StatusCode *int           `json:"status_code,omitempty"`
	CreatedAt  time.Time      `json:"created_at"`
}

// auditEntry is an internal representation for queue items
type auditEntry struct {
	UserID     *string
	Action     string
	Resource   *string
	ResourceID *string
	Details    map[string]any
	IPAddress  *string
	UserAgent  *string
	StatusCode *int
}

// AuditService handles audit logging with async batch writes
type AuditService struct {
	pool  *pgxpool.Pool
	queue chan auditEntry
}

// NewAuditService creates a new AuditService with an async write queue
func NewAuditService(pool *pgxpool.Pool, queueSize int) *AuditService {
	s := &AuditService{
		pool:  pool,
		queue: make(chan auditEntry, queueSize),
	}
	go s.drainQueue()
	return s
}

// Log adds an audit log entry to the async queue
func (s *AuditService) Log(ctx context.Context, userID, action, resource, resourceID string, details map[string]any, ip, userAgent string, statusCode int) {
	entry := auditEntry{
		Action:     action,
		Details:    details,
		StatusCode: &statusCode,
	}

	if userID != "" {
		entry.UserID = &userID
	}
	if resource != "" {
		entry.Resource = &resource
	}
	if resourceID != "" {
		entry.ResourceID = &resourceID
	}
	if ip != "" {
		entry.IPAddress = &ip
	}
	if userAgent != "" {
		entry.UserAgent = &userAgent
	}

	select {
	case s.queue <- entry:
	default:
		logger.Warn("Audit log queue is full, dropping entry", "action", action)
	}
}

// GetLogs retrieves audit logs for a given user and action
func (s *AuditService) GetLogs(ctx context.Context, userID, action string, limit int) ([]AuditLog, error) {
	query := `
		SELECT id, user_id, action, resource, resource_id, details, ip_address, user_agent, status_code, created_at
		FROM audit_logs
		WHERE ($1 = '' OR user_id = $1)
		  AND ($2 = '' OR action = $2)
		ORDER BY created_at DESC
		LIMIT $3
	`

	rows, err := s.pool.Query(ctx, query, userID, action, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query audit logs: %w", err)
	}
	defer rows.Close()

	var logs []AuditLog
	for rows.Next() {
		var log AuditLog
		var detailsJSON []byte
		err := rows.Scan(
			&log.ID,
			&log.UserID,
			&log.Action,
			&log.Resource,
			&log.ResourceID,
			&detailsJSON,
			&log.IPAddress,
			&log.UserAgent,
			&log.StatusCode,
			&log.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan audit log: %w", err)
		}

		if detailsJSON != nil {
			if err := json.Unmarshal(detailsJSON, &log.Details); err != nil {
				logger.Warn("Failed to unmarshal audit log details", "error", err)
			}
		}

		logs = append(logs, log)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating audit log rows: %w", err)
	}

	return logs, nil
}

// drainQueue continuously reads from the queue and batch-inserts into PostgreSQL
func (s *AuditService) drainQueue() {
	const batchSize = 50
	const flushInterval = 2 * time.Second

	batch := make([]auditEntry, 0, batchSize)
	ticker := time.NewTicker(flushInterval)
	defer ticker.Stop()

	for {
		select {
		case entry := <-s.queue:
			batch = append(batch, entry)
			if len(batch) >= batchSize {
				s.flushBatch(batch)
				batch = batch[:0]
			}
		case <-ticker.C:
			if len(batch) > 0 {
				s.flushBatch(batch)
				batch = batch[:0]
			}
		}
	}
}

// flushBatch inserts a batch of audit entries into PostgreSQL
func (s *AuditService) flushBatch(entries []auditEntry) {
	if len(entries) == 0 {
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	batch := &pgx.Batch{}
	for _, entry := range entries {
		var detailsJSON []byte
		if entry.Details != nil {
			var err error
			detailsJSON, err = json.Marshal(entry.Details)
			if err != nil {
				logger.Warn("Failed to marshal audit details", "error", err)
				detailsJSON = []byte("{}")
			}
		}

		batch.Queue(
			`INSERT INTO audit_logs (user_id, action, resource, resource_id, details, ip_address, user_agent, status_code)
			 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
			entry.UserID, entry.Action, entry.Resource, entry.ResourceID, detailsJSON, entry.IPAddress, entry.UserAgent, entry.StatusCode,
		)
	}

	br := s.pool.SendBatch(ctx, batch)
	defer br.Close()

	for i := 0; i < len(entries); i++ {
		if _, err := br.Exec(); err != nil {
			logger.Error("Failed to insert audit log", "error", err)
		}
	}

	logger.Info("Audit logs flushed", "count", len(entries))
}
