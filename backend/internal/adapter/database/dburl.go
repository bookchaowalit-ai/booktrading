package database

import (
	"fmt"
	"net/url"
	"strings"
)

// BuildDatabaseURL constructs a PostgreSQL connection URL.
// The password is included but the returned URL should never be logged.
func BuildDatabaseURL(host, port, user, password, dbName, sslMode string) string {
	return fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=%s",
		url.QueryEscape(user),
		url.QueryEscape(password),
		url.QueryEscape(host),
		url.QueryEscape(port),
		url.QueryEscape(dbName),
		url.QueryEscape(sslMode),
	)
}

// MaskDatabaseURL returns a copy of the database URL with the password masked.
// Safe for logging.
func MaskDatabaseURL(databaseURL string) string {
	// Find the password portion in postgres://user:password@host...
	if idx := strings.Index(databaseURL, "://"); idx != -1 {
		rest := databaseURL[idx+3:]
		if atIdx := strings.Index(rest, "@"); atIdx != -1 {
			userPass := rest[:atIdx]
			if colonIdx := strings.Index(userPass, ":"); colonIdx != -1 {
				masked := userPass[:colonIdx+1] + "****"
				return databaseURL[:idx+3] + masked + rest[atIdx:]
			}
		}
	}
	return "<masked>"
}
