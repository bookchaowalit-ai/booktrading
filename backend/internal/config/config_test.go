package config

import (
	"os"
	"testing"
)

func TestLoadConfig_NoDefaults(t *testing.T) {
	// Clear any env vars that might affect the test
	os.Unsetenv("DATABASE_PASSWORD")
	os.Unsetenv("REDIS_PASSWORD")
	os.Unsetenv("ENCRYPTION_KEY")

	cfg := LoadConfig()

	// DB password should NOT have a default
	if cfg.Database.Password != "" {
		t.Errorf("expected empty DB password when not set, got %q", cfg.Database.Password)
	}

	// Redis password should NOT have a default
	if cfg.Redis.Password != "" {
		t.Errorf("expected empty Redis password when not set, got %q", cfg.Redis.Password)
	}
}

func TestValidate_MissingPasswords(t *testing.T) {
	cfg := &Config{
		Database: DatabaseConfig{
			Password: "",
		},
		Redis: RedisConfig{
			Password: "",
		},
	}

	err := cfg.Validate()
	if err == nil {
		t.Fatal("expected validation error when passwords are empty")
	}
}

func TestValidate_WithPasswords(t *testing.T) {
	cfg := &Config{
		Database: DatabaseConfig{
			Password: "secure_db_password_123",
		},
		Redis: RedisConfig{
			Password: "secure_redis_password_456",
		},
	}

	err := cfg.Validate()
	if err != nil {
		t.Errorf("expected no error with valid passwords, got: %v", err)
	}
}

func TestGetEnv(t *testing.T) {
	os.Setenv("TEST_ENV_VAR", "hello")
	defer os.Unsetenv("TEST_ENV_VAR")

	if got := getEnv("TEST_ENV_VAR", "default"); got != "hello" {
		t.Errorf("getEnv(TEST_ENV_VAR) = %q, want %q", got, "hello")
	}

	if got := getEnv("NONEXISTENT", "default"); got != "default" {
		t.Errorf("getEnv(NONEXISTENT) = %q, want %q", got, "default")
	}
}
