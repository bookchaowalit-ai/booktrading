package database

import (
	"context"
	"errors"
	"os"
	"testing"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Runs only when BOOKTRADING_TEST_DATABASE_URL points at a throwaway
// database that already has the users table (migration 008). Rows use random
// IDs and are deleted afterwards.
func TestUserRepositoryAgainstPostgres(t *testing.T) {
	dsn := os.Getenv("BOOKTRADING_TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("BOOKTRADING_TEST_DATABASE_URL not set")
	}
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	t.Cleanup(pool.Close)
	repo := NewUserRepository(pool)

	u := User{ID: uuid.NewString(), Email: uuid.NewString() + "@example.test", Name: "T", Role: "trader", PasswordHash: "h1"}
	t.Cleanup(func() { _, _ = pool.Exec(ctx, `DELETE FROM users WHERE id = $1`, u.ID) })

	if err := repo.CreateUser(ctx, u); err != nil {
		t.Fatalf("CreateUser: %v", err)
	}
	dup := u
	dup.ID = uuid.NewString()
	if err := repo.CreateUser(ctx, dup); !errors.Is(err, ErrEmailTaken) {
		t.Fatalf("duplicate email err = %v, want ErrEmailTaken", err)
	}

	got, err := repo.GetUserByEmail(ctx, u.Email)
	if err != nil || *got != u {
		t.Fatalf("GetUserByEmail = %+v, %v", got, err)
	}
	if err := repo.UpdatePasswordHash(ctx, u.ID, "h2"); err != nil {
		t.Fatalf("UpdatePasswordHash: %v", err)
	}
	if got, err := repo.GetUserByID(ctx, u.ID); err != nil || got.PasswordHash != "h2" {
		t.Fatalf("GetUserByID = %+v, %v", got, err)
	}

	if _, err := repo.GetUserByEmail(ctx, "missing-"+u.Email); !errors.Is(err, ErrUserNotFound) {
		t.Fatalf("missing email err = %v", err)
	}
	if _, err := repo.GetUserByID(ctx, uuid.NewString()); !errors.Is(err, ErrUserNotFound) {
		t.Fatalf("missing id err = %v", err)
	}
	if err := repo.UpdatePasswordHash(ctx, uuid.NewString(), "x"); !errors.Is(err, ErrUserNotFound) {
		t.Fatalf("update missing err = %v", err)
	}
}
