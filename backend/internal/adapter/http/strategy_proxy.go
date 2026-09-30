package http

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"trading-bot-system/backend/internal/logger"
)

// StrategyProxyPrefix is the browser-facing path prefix proxied to the
// Python strategy service.
const StrategyProxyPrefix = "/strategy-api"

// DefaultStrategyProxyTimeout bounds one proxied request. Keep it below the
// backend's SERVER_WRITE_TIMEOUT (30s by default).
const DefaultStrategyProxyTimeout = 25 * time.Second

// DefaultStrategyProxyMaxBody caps proxied request bodies.
const DefaultStrategyProxyMaxBody int64 = 1 << 20

// strategyAllowedSections lists the `/api/<section>` groups of the strategy
// service the frontend is allowed to reach. Anything else (for example the
// `/api/v1/world` lake import) is not reachable through the proxy.
var strategyAllowedSections = map[string]bool{
	"airdrop-tracker": true,
	"arb-paper":       true,
	"backtest":        true,
	"brain":           true,
	"command-center":  true,
	"evidence":        true,
	"grid":            true,
	"health":          true,
	"indicators":      true,
	"journal":         true,
	"market-intel":    true,
	"paper":           true,
	"poly-paper":      true,
	"real-grid":       true,
	"report":          true,
	"research":        true,
	"risk":            true,
	"signal-tracker":  true,
	"signals":         true,
	"strategy":        true,
}

// StrategyProxy forwards authenticated browser calls under /strategy-api/* to
// the strategy service. The caller's session token is validated here and
// never forwarded; the upstream receives the server-side service token
// (AUTH_TOKEN) instead, so the browser never needs that secret.
type StrategyProxy struct {
	upstream     *url.URL
	serviceToken string
	validate     func(token string) (string, bool)
	timeout      time.Duration
	maxBody      int64
	proxy        *httputil.ReverseProxy
}

// StrategyProxyConfig configures NewStrategyProxy.
type StrategyProxyConfig struct {
	// UpstreamURL is the strategy service base URL, e.g. http://strategy:8000.
	UpstreamURL string
	// ServiceToken is sent upstream as `Authorization: Bearer <token>`.
	ServiceToken string
	// Validate checks a user session token (AuthHandler.ValidateToken).
	Validate func(token string) (string, bool)
	// Timeout bounds one proxied request (default DefaultStrategyProxyTimeout).
	Timeout time.Duration
	// MaxBody caps the request body (default DefaultStrategyProxyMaxBody).
	MaxBody int64
	// Transport overrides the upstream transport (tests).
	Transport http.RoundTripper
}

// NewStrategyProxy builds the proxy. The upstream must be an absolute
// http(s) URL without a path, query or credentials.
func NewStrategyProxy(cfg StrategyProxyConfig) (*StrategyProxy, error) {
	if cfg.Validate == nil {
		return nil, errors.New("strategy proxy: session validator is required")
	}
	u, err := url.Parse(strings.TrimRight(cfg.UpstreamURL, "/"))
	if err != nil {
		return nil, fmt.Errorf("strategy proxy: invalid upstream URL: %w", err)
	}
	if (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" || u.User != nil ||
		(u.Path != "" && u.Path != "/") || u.RawQuery != "" || u.Fragment != "" {
		return nil, errors.New("strategy proxy: upstream must be an absolute http(s) URL without path, query or credentials")
	}
	u.Path = ""

	p := &StrategyProxy{
		upstream:     u,
		serviceToken: cfg.ServiceToken,
		validate:     cfg.Validate,
		timeout:      cfg.Timeout,
		maxBody:      cfg.MaxBody,
	}
	if p.timeout <= 0 {
		p.timeout = DefaultStrategyProxyTimeout
	}
	if p.maxBody <= 0 {
		p.maxBody = DefaultStrategyProxyMaxBody
	}

	transport := cfg.Transport
	if transport == nil {
		transport = &http.Transport{
			Proxy: nil, // internal service call: never route through an egress proxy
			DialContext: (&net.Dialer{
				Timeout:   5 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			MaxIdleConns:          32,
			IdleConnTimeout:       90 * time.Second,
			ResponseHeaderTimeout: p.timeout,
		}
	}

	p.proxy = &httputil.ReverseProxy{
		Rewrite:        p.rewrite,
		Transport:      transport,
		ModifyResponse: stripUpstreamResponseHeaders,
		ErrorHandler:   proxyErrorHandler,
	}
	return p, nil
}

// upstreamPathKey carries the validated upstream path from ServeHTTP to rewrite.
type upstreamPathKey struct{}

func (p *StrategyProxy) rewrite(pr *httputil.ProxyRequest) {
	upstreamPath, _ := pr.In.Context().Value(upstreamPathKey{}).(string)
	pr.Out.URL.Scheme = p.upstream.Scheme
	pr.Out.URL.Host = p.upstream.Host
	pr.Out.URL.Path = upstreamPath
	pr.Out.URL.RawPath = ""
	pr.Out.URL.RawQuery = pr.In.URL.RawQuery
	pr.Out.Host = p.upstream.Host

	// Never forward browser credentials; the upstream only trusts the
	// service token. Rewrite already drops Forwarded / X-Forwarded-*.
	pr.Out.Header.Del("Authorization")
	pr.Out.Header.Del("Cookie")
	pr.Out.Header.Del("Proxy-Authorization")
	if p.serviceToken != "" {
		pr.Out.Header.Set("Authorization", "Bearer "+p.serviceToken)
	}
}

// ServeHTTP validates the path and session, then forwards the request.
func (p *StrategyProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	upstreamPath, public, status := strategyUpstreamPath(r)
	if status != 0 {
		writeProxyError(w, status, http.StatusText(status))
		return
	}

	switch r.Method {
	case http.MethodGet, http.MethodHead, http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete:
	default:
		writeProxyError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}
	if public && r.Method != http.MethodGet && r.Method != http.MethodHead {
		public = false
	}

	if !public {
		token := extractBearerToken(r)
		if token == "" {
			writeProxyError(w, http.StatusUnauthorized, "Unauthorized")
			return
		}
		if _, ok := p.validate(token); !ok {
			writeProxyError(w, http.StatusUnauthorized, "Invalid or expired token")
			return
		}
	}

	if r.ContentLength > p.maxBody {
		writeProxyError(w, http.StatusRequestEntityTooLarge, "Request body too large")
		return
	}
	if r.Body != nil {
		r.Body = http.MaxBytesReader(w, r.Body, p.maxBody)
	}

	ctx, cancel := context.WithTimeout(r.Context(), p.timeout)
	defer cancel()
	ctx = context.WithValue(ctx, upstreamPathKey{}, upstreamPath)
	p.proxy.ServeHTTP(w, r.WithContext(ctx))
}

// strategyUpstreamPath maps /strategy-api/api/<section>/... to the upstream
// path. It returns a non-zero status for anything outside the allow-list or
// any path that could escape it (dot segments, encoded separators, empty
// segments). public is true for the unauthenticated health probe.
func strategyUpstreamPath(r *http.Request) (upstreamPath string, public bool, status int) {
	escaped := r.URL.EscapedPath()
	if !strings.HasPrefix(escaped, StrategyProxyPrefix+"/") {
		return "", false, http.StatusNotFound
	}
	rest := strings.TrimPrefix(escaped, StrategyProxyPrefix)

	lower := strings.ToLower(rest)
	for _, bad := range []string{"%2e", "%2f", "%5c", "%00", "\\"} {
		if strings.Contains(lower, bad) {
			return "", false, http.StatusBadRequest
		}
	}

	segments := strings.Split(strings.TrimPrefix(rest, "/"), "/")
	for i, seg := range segments {
		if seg == "." || seg == ".." {
			return "", false, http.StatusBadRequest
		}
		// Allow a single trailing slash, reject empty inner segments ("//").
		if seg == "" && i != len(segments)-1 {
			return "", false, http.StatusBadRequest
		}
	}
	if len(segments) < 2 || segments[0] != "api" || !strategyAllowedSections[segments[1]] {
		return "", false, http.StatusNotFound
	}

	decoded, err := url.PathUnescape(rest)
	if err != nil {
		return "", false, http.StatusBadRequest
	}
	public = decoded == "/api/health"
	return decoded, public, 0
}

// stripUpstreamResponseHeaders drops upstream CORS and cookie headers; the
// backend router owns CORS for the browser-facing origin.
func stripUpstreamResponseHeaders(resp *http.Response) error {
	for name := range resp.Header {
		if strings.HasPrefix(http.CanonicalHeaderKey(name), "Access-Control-") {
			resp.Header.Del(name)
		}
	}
	resp.Header.Del("Set-Cookie")
	return nil
}

func proxyErrorHandler(w http.ResponseWriter, r *http.Request, err error) {
	var maxErr *http.MaxBytesError
	switch {
	case errors.As(err, &maxErr):
		writeProxyError(w, http.StatusRequestEntityTooLarge, "Request body too large")
	case errors.Is(err, context.DeadlineExceeded):
		logger.Warn("strategy proxy timeout", "path", r.URL.Path)
		writeProxyError(w, http.StatusGatewayTimeout, "Strategy service timed out")
	case errors.Is(err, context.Canceled):
		// Client went away; nothing useful to write.
	default:
		logger.Warn("strategy proxy upstream error", "path", r.URL.Path, "error", err)
		writeProxyError(w, http.StatusBadGateway, "Strategy service unavailable")
	}
}

func writeProxyError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}
