package database

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

// User is an account row in the users table (migration 008).
type User struct {
	ID           string
	Email        string
	Name         string
	Role         string
	PasswordHash string
}

// ErrUserNotFound is returned when no user matches.
var ErrUserNotFound = errors.New("user not found")

// ErrEmailTaken is returned by CreateUser when the email is already registered.
var ErrEmailTaken = errors.New("email already registered")

// UserRepository stores accounts in PostgreSQL so they survive restarts.
type UserRepository struct {
	pool *pgxpool.Pool
}

// NewUserRepository creates a users repository on pool.
func NewUserRepository(pool *pgxpool.Pool) *UserRepository {
	return &UserRepository{pool: pool}
}

const userColumns = `id, email, name, role, password_hash`

func scanUser(row pgx.Row) (*User, error) {
	var u User
	if err := row.Scan(&u.ID, &u.Email, &u.Name, &u.Role, &u.PasswordHash); err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return nil, ErrUserNotFound
		}
		return nil, err
	}
	return &u, nil
}

// GetUserByEmail returns the user with exactly this email (callers normalise
// case), or ErrUserNotFound.
func (r *UserRepository) GetUserByEmail(ctx context.Context, email string) (*User, error) {
	u, err := scanUser(r.pool.QueryRow(ctx, `SELECT `+userColumns+` FROM users WHERE email = $1`, email))
	if err != nil && !errors.Is(err, ErrUserNotFound) {
		return nil, fmt.Errorf("get user by email: %w", err)
	}
	return u, err
}

// GetUserByID returns the user with this ID, or ErrUserNotFound.
func (r *UserRepository) GetUserByID(ctx context.Context, id string) (*User, error) {
	u, err := scanUser(r.pool.QueryRow(ctx, `SELECT `+userColumns+` FROM users WHERE id = $1`, id))
	if err != nil && !errors.Is(err, ErrUserNotFound) {
		return nil, fmt.Errorf("get user by id: %w", err)
	}
	return u, err
}

// CreateUser inserts u. A duplicate email (or ID) returns ErrEmailTaken.
func (r *UserRepository) CreateUser(ctx context.Context, u User) error {
	_, err := r.pool.Exec(ctx,
		`INSERT INTO users (id, email, name, role, password_hash) VALUES ($1, $2, $3, $4, $5)`,
		u.ID, u.Email, u.Name, u.Role, u.PasswordHash)
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "23505" { // unique_violation
		return ErrEmailTaken
	}
	if err != nil {
		return fmt.Errorf("create user: %w", err)
	}
	return nil
}

// UpdatePasswordHash replaces the password hash of user id.
func (r *UserRepository) UpdatePasswordHash(ctx context.Context, id, hash string) error {
	tag, err := r.pool.Exec(ctx,
		`UPDATE users SET password_hash = $2, updated_at = NOW() WHERE id = $1`, id, hash)
	if err != nil {
		return fmt.Errorf("update password: %w", err)
	}
	if tag.RowsAffected() == 0 {
		return ErrUserNotFound
	}
	return nil
}
