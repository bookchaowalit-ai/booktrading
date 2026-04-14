package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceDiaryRepository implements FinanceDiaryRepository with PostgreSQL
type PostgresFinanceDiaryRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceDiaryRepository creates a new PostgreSQL finance diary repository
func NewPostgresFinanceDiaryRepository(pool *pgxpool.Pool) repository.FinanceDiaryRepository {
	return &PostgresFinanceDiaryRepository{pool: pool}
}

func (r *PostgresFinanceDiaryRepository) Create(ctx context.Context, entry *model.FinanceDiaryEntry) error {
	if entry.ID == "" {
		entry.ID = uuid.New().String()
	}
	now := time.Now()
	entry.CreatedAt = now
	entry.UpdatedAt = now

	query := `
		INSERT INTO finance_diary_entries (
			id, user_id, date, title, content, mood, financial_mood,
			spending_reflection, savings_wins, lessons_learned, tomorrow_goals,
			gratitude, total_spent, total_earned, tags, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
	`
	_, err := r.pool.Exec(ctx, query,
		entry.ID, entry.UserID, entry.Date, entry.Title, entry.Content, entry.Mood,
		entry.FinancialMood, entry.SpendingReflection, entry.SavingsWins,
		entry.LessonsLearned, entry.TomorrowGoals, entry.Gratitude,
		entry.TotalSpent, entry.TotalEarned, entry.Tags, entry.CreatedAt, entry.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceDiaryRepository) GetByID(ctx context.Context, id string) (*model.FinanceDiaryEntry, error) {
	query := `
		SELECT id, user_id, date, title, content, mood, financial_mood,
			spending_reflection, savings_wins, lessons_learned, tomorrow_goals,
			gratitude, total_spent, total_earned, tags, created_at, updated_at
		FROM finance_diary_entries WHERE id = $1
	`
	entry := &model.FinanceDiaryEntry{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&entry.ID, &entry.UserID, &entry.Date, &entry.Title, &entry.Content, &entry.Mood,
		&entry.FinancialMood, &entry.SpendingReflection, &entry.SavingsWins,
		&entry.LessonsLearned, &entry.TomorrowGoals, &entry.Gratitude,
		&entry.TotalSpent, &entry.TotalEarned, &entry.Tags, &entry.CreatedAt, &entry.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return entry, nil
}

func (r *PostgresFinanceDiaryRepository) GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceDiaryEntry, error) {
	query := `
		SELECT id, user_id, date, title, content, mood, financial_mood,
			spending_reflection, savings_wins, lessons_learned, tomorrow_goals,
			gratitude, total_spent, total_earned, tags, created_at, updated_at
		FROM finance_diary_entries WHERE user_id = $1
		ORDER BY date DESC
		LIMIT $2 OFFSET $3
	`
	rows, err := r.pool.Query(ctx, query, userID, limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanDiaryEntries(rows)
}

func (r *PostgresFinanceDiaryRepository) GetByDate(ctx context.Context, userID string, date time.Time) (*model.FinanceDiaryEntry, error) {
	// Get entry for the specific date (matching day)
	startOfDay := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, date.Location())
	endOfDay := startOfDay.Add(24 * time.Hour)

	query := `
		SELECT id, user_id, date, title, content, mood, financial_mood,
			spending_reflection, savings_wins, lessons_learned, tomorrow_goals,
			gratitude, total_spent, total_earned, tags, created_at, updated_at
		FROM finance_diary_entries WHERE user_id = $1 AND date >= $2 AND date < $3
		ORDER BY date DESC LIMIT 1
	`
	entry := &model.FinanceDiaryEntry{}
	err := r.pool.QueryRow(ctx, query, userID, startOfDay, endOfDay).Scan(
		&entry.ID, &entry.UserID, &entry.Date, &entry.Title, &entry.Content, &entry.Mood,
		&entry.FinancialMood, &entry.SpendingReflection, &entry.SavingsWins,
		&entry.LessonsLearned, &entry.TomorrowGoals, &entry.Gratitude,
		&entry.TotalSpent, &entry.TotalEarned, &entry.Tags, &entry.CreatedAt, &entry.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return entry, nil
}

func (r *PostgresFinanceDiaryRepository) GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.FinanceDiaryEntry, error) {
	query := `
		SELECT id, user_id, date, title, content, mood, financial_mood,
			spending_reflection, savings_wins, lessons_learned, tomorrow_goals,
			gratitude, total_spent, total_earned, tags, created_at, updated_at
		FROM finance_diary_entries WHERE user_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanDiaryEntries(rows)
}

func (r *PostgresFinanceDiaryRepository) Update(ctx context.Context, entry *model.FinanceDiaryEntry) error {
	entry.UpdatedAt = time.Now()
	query := `
		UPDATE finance_diary_entries SET
			date = $2, title = $3, content = $4, mood = $5, financial_mood = $6,
			spending_reflection = $7, savings_wins = $8, lessons_learned = $9,
			tomorrow_goals = $10, gratitude = $11, total_spent = $12,
			total_earned = $13, tags = $14, updated_at = $15
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		entry.ID, entry.Date, entry.Title, entry.Content, entry.Mood, entry.FinancialMood,
		entry.SpendingReflection, entry.SavingsWins, entry.LessonsLearned,
		entry.TomorrowGoals, entry.Gratitude, entry.TotalSpent, entry.TotalEarned,
		entry.Tags, entry.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceDiaryRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_diary_entries WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

func (r *PostgresFinanceDiaryRepository) scanDiaryEntries(rows pgx.Rows) ([]*model.FinanceDiaryEntry, error) {
	var entries []*model.FinanceDiaryEntry
	for rows.Next() {
		entry := &model.FinanceDiaryEntry{}
		err := rows.Scan(
			&entry.ID, &entry.UserID, &entry.Date, &entry.Title, &entry.Content, &entry.Mood,
			&entry.FinancialMood, &entry.SpendingReflection, &entry.SavingsWins,
			&entry.LessonsLearned, &entry.TomorrowGoals, &entry.Gratitude,
			&entry.TotalSpent, &entry.TotalEarned, &entry.Tags, &entry.CreatedAt, &entry.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		entries = append(entries, entry)
	}
	return entries, rows.Err()
}
