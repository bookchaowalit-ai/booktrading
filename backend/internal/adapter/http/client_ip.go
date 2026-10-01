package http

import (
	"net"
	"net/http"
	"net/netip"
	"os"
	"strings"
	"sync"
)

// clientIPFromRequest returns the IP used for rate limiting, login lockout and
// audit logs.
//
// Forwarding headers are honored only when the direct peer (RemoteAddr) is a
// trusted proxy, so a client that reaches the backend directly cannot choose
// its own bucket by sending X-Real-IP or X-Forwarded-For. Trusted proxies come
// from TRUSTED_PROXIES (comma-separated IPs/CIDRs, or "*" to trust every
// peer); when unset, loopback and private-network peers are trusted, which
// covers the Caddy and Next.js containers on the Docker network.
//
// X-Forwarded-For is walked from the right and the first untrusted hop wins,
// so entries a client prepends are ignored (Caddy replaces the header for
// untrusted clients and Next.js appends its peer). X-Real-IP, which the
// Caddyfile sets to {remote_host}, is the fallback when XFF is absent.
func clientIPFromRequest(r *http.Request) string {
	remote := r.RemoteAddr
	if host, _, err := net.SplitHostPort(remote); err == nil {
		remote = host
	}

	proxies := loadTrustedProxies()
	if !proxies.contains(remote) {
		return remote
	}

	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		hops := strings.Split(xff, ",")
		for i := len(hops) - 1; i >= 0; i-- {
			hop := strings.TrimSpace(hops[i])
			if hop == "" {
				continue
			}
			if i == 0 || !proxies.contains(hop) {
				return hop
			}
		}
	}

	if xri := strings.TrimSpace(r.Header.Get("X-Real-IP")); xri != "" {
		return xri
	}
	return remote
}

type trustedProxies struct {
	all      bool
	prefixes []netip.Prefix
}

var defaultTrustedProxies = []string{
	"127.0.0.0/8", "::1/128",
	"10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",
}

var (
	trustedProxiesMu    sync.Mutex
	trustedProxiesRaw   = "\x00" // sentinel: never a real env value
	trustedProxiesCache trustedProxies
)

// loadTrustedProxies parses TRUSTED_PROXIES, caching by raw value so tests
// (and a changed environment) pick up new settings without a restart.
func loadTrustedProxies() trustedProxies {
	raw := os.Getenv("TRUSTED_PROXIES")
	trustedProxiesMu.Lock()
	defer trustedProxiesMu.Unlock()
	if raw == trustedProxiesRaw {
		return trustedProxiesCache
	}
	trustedProxiesRaw = raw
	trustedProxiesCache = parseTrustedProxies(raw)
	return trustedProxiesCache
}

func parseTrustedProxies(raw string) trustedProxies {
	entries := defaultTrustedProxies
	if strings.TrimSpace(raw) != "" {
		entries = strings.Split(raw, ",")
	}
	var tp trustedProxies
	for _, e := range entries {
		e = strings.TrimSpace(e)
		switch {
		case e == "":
			continue
		case e == "*":
			tp.all = true
		case strings.Contains(e, "/"):
			if p, err := netip.ParsePrefix(e); err == nil {
				tp.prefixes = append(tp.prefixes, p.Masked())
			}
		default:
			if a, err := netip.ParseAddr(e); err == nil {
				tp.prefixes = append(tp.prefixes, netip.PrefixFrom(a, a.BitLen()))
			}
		}
	}
	return tp
}

func (tp trustedProxies) contains(ip string) bool {
	if tp.all {
		return true
	}
	a, err := netip.ParseAddr(ip)
	if err != nil {
		return false
	}
	a = a.Unmap()
	for _, p := range tp.prefixes {
		if p.Contains(a) {
			return true
		}
	}
	return false
}
