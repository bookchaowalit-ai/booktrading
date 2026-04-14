package logger

import (
	"context"
	"log/slog"
	"os"
	"strings"
)

// Log is the global structured logger (alias for convenience)
var Log *slog.Logger

func init() {
	// Read LOG_LEVEL from env (debug, info, warn, error)
	level := slog.LevelInfo
	switch strings.ToLower(os.Getenv("LOG_LEVEL")) {
	case "debug":
		level = slog.LevelDebug
	case "warn":
		level = slog.LevelWarn
	case "error":
		level = slog.LevelError
	}

	// Read LOG_FORMAT from env (json or text)
	format := strings.ToLower(os.Getenv("LOG_FORMAT"))

	opts := &slog.HandlerOptions{Level: level}

	var handler slog.Handler
	if format == "json" {
		handler = slog.NewJSONHandler(os.Stdout, opts)
	} else {
		handler = slog.NewTextHandler(os.Stdout, opts)
	}

	Log = slog.New(handler)
	slog.SetDefault(Log)
}

// With returns a logger with the given key-value pairs
func With(attrs ...any) *slog.Logger {
	return Log.With(attrs...)
}

// FromContext extracts a logger from context, or returns the default
func FromContext(ctx context.Context) *slog.Logger {
	if logger, ok := ctx.Value("logger").(*slog.Logger); ok {
		return logger
	}
	return Log
}

// WithContext returns a context with the given logger
func WithContext(ctx context.Context, logger *slog.Logger) context.Context {
	return context.WithValue(ctx, "logger", logger)
}

// Debug logs at DEBUG level
func Debug(msg string, args ...any) {
	Log.Debug(msg, args...)
}

// Info logs at INFO level
func Info(msg string, args ...any) {
	Log.Info(msg, args...)
}

// Warn logs at WARN level
func Warn(msg string, args ...any) {
	Log.Warn(msg, args...)
}

// Error logs at ERROR level
func Error(msg string, args ...any) {
	Log.Error(msg, args...)
}

// Fatal logs at ERROR level and exits with status 1
func Fatal(msg string, args ...any) {
	Log.Error(msg, args...)
	os.Exit(1)
}
