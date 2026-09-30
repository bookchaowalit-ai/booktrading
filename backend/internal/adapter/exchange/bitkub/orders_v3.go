package bitkub

// Bitkub API v3 order placement and lookup by client ID.
//
// Endpoints (Bitkub public REST API v3 docs):
//
//	POST /api/v3/market/place-bid     body {sym, amt, rat, typ, client_id}
//	POST /api/v3/market/place-ask     body {sym, amt, rat, typ, client_id}
//	POST /api/v3/market/cancel-order  body {sym, id, sd}
//	GET  /api/v3/market/my-open-orders?sym=
//	GET  /api/v3/market/my-order-history?sym=&lmt=
//	GET  /api/v3/market/order-info?sym=&id=&sd=
//
// Every response is {"error": <code>, "result": ...}; error 0 is success.
// Secure endpoints are signed with HMAC-SHA256 (hex) over
// timestamp + method + path [+ "?" + query] + body, sent in the
// X-BTK-APIKEY / X-BTK-TIMESTAMP / X-BTK-SIGN headers.
//
// Units: `amt` is THB for place-bid and the base asset for place-ask, and
// order-info's `filled` uses the same unit as the order's `amount`.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

// Errors returned by the v3 order functions. The exchange package maps them
// to its exchange-neutral sentinels.
var (
	// ErrOutcomeUnknown wraps a placement whose result is unknown: transport
	// errors, 5xx answers, unreadable bodies, and Bitkub error 90.
	ErrOutcomeUnknown = errors.New("bitkub: order outcome unknown")
	// ErrNotFound means no order carries the client ID, and no unattributed
	// fill happened since the order was submitted.
	ErrNotFound = errors.New("bitkub: order not found")
	// ErrAmbiguous means an order or fill in the window cannot be attributed
	// to a client ID, so the lookup cannot prove the order does not exist.
	ErrAmbiguous = errors.New("bitkub: order lookup is ambiguous")
)

// Bitkub error code 90: "Server error (please contact support)". The order
// may or may not have been created.
const codeServerError = 90

// historyPageSize is how many history rows one lookup reads.
const historyPageSize = 100

// clockSkew widens the lookup window around the submission time.
const clockSkew = 5 * time.Second

// V3Symbol converts "THB_BTC", "BTC_THB", "btc_thb" or "BTCTHB" to the v3
// form "btc_thb".
func V3Symbol(symbol string) string {
	s := strings.ToLower(strings.TrimSpace(symbol))
	if parts := strings.Split(s, "_"); len(parts) == 2 {
		if parts[0] == "thb" && parts[1] != "thb" {
			return parts[1] + "_thb"
		}
		return s
	}
	if strings.HasSuffix(s, "thb") && len(s) > 3 {
		return strings.TrimSuffix(s, "thb") + "_thb"
	}
	return s
}

// flexFloat accepts a JSON number or a numeric string.
type flexFloat float64

func (f *flexFloat) UnmarshalJSON(b []byte) error {
	s := strings.Trim(string(b), `"`)
	if s == "" || s == "null" {
		*f = 0
		return nil
	}
	v, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return err
	}
	*f = flexFloat(v)
	return nil
}

// flexString accepts a JSON string or number (Bitkub ids are either).
type flexString string

func (f *flexString) UnmarshalJSON(b []byte) error {
	*f = flexString(strings.Trim(string(b), `"`))
	return nil
}

// OrderState is the exchange-neutral state of one Bitkub order.
type OrderState struct {
	ID       string
	ClientID string
	Side     string // "buy" or "sell"
	// Status is FILLED, CANCELED, NEW or PARTIALLY_FILLED.
	Status string
	// ExecutedBase is the filled quantity in the base asset.
	ExecutedBase float64
}

type v3Envelope struct {
	Error  int             `json:"error"`
	Result json.RawMessage `json:"result"`
}

// v3Do sends one signed v3 request. query is for GET, body for POST. It
// returns the HTTP status, the raw body and a transport error.
func (c *Client) v3Do(ctx context.Context, method, path string, query url.Values, body any) (int, []byte, error) {
	var (
		payload []byte
		target  = c.BaseURL + path
		sigPath = path
	)
	if len(query) > 0 {
		q := query.Encode()
		target += "?" + q
		sigPath += "?" + q
	}
	if body != nil {
		var err error
		if payload, err = json.Marshal(body); err != nil {
			return 0, nil, err
		}
	}
	ts := strconv.FormatInt(time.Now().UnixMilli(), 10)
	sig := c.generateSignature(ts + method + sigPath + string(payload))

	req, err := http.NewRequestWithContext(ctx, method, target, bytes.NewReader(payload))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-BTK-APIKEY", c.APIKey)
	req.Header.Set("X-BTK-TIMESTAMP", ts)
	req.Header.Set("X-BTK-SIGN", sig)

	resp, err := c.client.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	return resp.StatusCode, raw, err
}

// v3Get performs a signed read and decodes a successful result into out.
func (c *Client) v3Get(ctx context.Context, path string, query url.Values, out any) error {
	status, raw, err := c.v3Do(ctx, http.MethodGet, path, query, nil)
	if err != nil {
		return fmt.Errorf("bitkub %s: %w", path, err)
	}
	var env v3Envelope
	if status != http.StatusOK || json.Unmarshal(raw, &env) != nil {
		return fmt.Errorf("bitkub %s: HTTP %d: %s", path, status, truncate(raw))
	}
	if env.Error != 0 {
		return fmt.Errorf("bitkub %s: error %d", path, env.Error)
	}
	if err := json.Unmarshal(env.Result, out); err != nil {
		return fmt.Errorf("bitkub %s: parse result: %w", path, err)
	}
	return nil
}

func truncate(b []byte) string {
	const max = 200
	if len(b) > max {
		return string(b[:max]) + "..."
	}
	return string(b)
}

// PlaceOrderV3 submits a bid ("buy") or ask ("sell") tagged with clientID.
// amt is THB for a buy and the base asset for a sell; rate 0 means a market
// order. An error wrapping ErrOutcomeUnknown means the order may exist and
// must be looked up with FindOrderByClientID before anything is re-sent.
func (c *Client) PlaceOrderV3(ctx context.Context, symbol, side string, amt, rate float64, clientID string) (*OrderState, error) {
	side = strings.ToLower(side)
	path := "/api/v3/market/place-bid"
	switch side {
	case "buy":
	case "sell":
		path = "/api/v3/market/place-ask"
	default:
		return nil, fmt.Errorf("bitkub: invalid side %q", side)
	}
	if amt <= 0 {
		return nil, fmt.Errorf("bitkub: invalid amount %v", amt)
	}
	typ := "limit"
	if rate <= 0 {
		typ, rate = "market", 0
	}
	body := map[string]any{"sym": V3Symbol(symbol), "amt": amt, "rat": rate, "typ": typ, "client_id": clientID}

	status, raw, err := c.v3Do(ctx, http.MethodPost, path, nil, body)
	if err != nil {
		return nil, fmt.Errorf("%w: request failed: %w", ErrOutcomeUnknown, err)
	}
	if status >= 500 {
		return nil, fmt.Errorf("%w: HTTP %d: %s", ErrOutcomeUnknown, status, truncate(raw))
	}
	var env v3Envelope
	if status != http.StatusOK {
		return nil, fmt.Errorf("bitkub order rejected: HTTP %d: %s", status, truncate(raw))
	}
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, fmt.Errorf("%w: unparsable response: %w", ErrOutcomeUnknown, err)
	}
	if env.Error == codeServerError {
		return nil, fmt.Errorf("%w: bitkub error %d", ErrOutcomeUnknown, env.Error)
	}
	if env.Error != 0 {
		return nil, fmt.Errorf("bitkub order rejected: error %d", env.Error)
	}
	var res struct {
		ID flexString `json:"id"`
		CI string     `json:"ci"`
	}
	if err := json.Unmarshal(env.Result, &res); err != nil || res.ID == "" {
		return nil, fmt.Errorf("%w: accepted without a readable order id", ErrOutcomeUnknown)
	}
	return &OrderState{ID: string(res.ID), ClientID: clientID, Side: side, Status: "NEW"}, nil
}

// OrderInfo returns the state of one order by id and side.
func (c *Client) OrderInfo(ctx context.Context, symbol, id, side string) (*OrderState, error) {
	q := url.Values{"sym": {V3Symbol(symbol)}, "id": {id}, "sd": {strings.ToLower(side)}}
	var r struct {
		Amount        flexFloat `json:"amount"`
		Rate          flexFloat `json:"rate"`
		Filled        flexFloat `json:"filled"`
		Status        string    `json:"status"`
		PartialFilled bool      `json:"partial_filled"`
		History       []struct {
			Amount flexFloat `json:"amount"`
			Rate   flexFloat `json:"rate"`
		} `json:"history"`
	}
	if err := c.v3Get(ctx, "/api/v3/market/order-info", q, &r); err != nil {
		return nil, err
	}
	st := &OrderState{ID: id, Side: strings.ToLower(side)}
	switch strings.ToLower(r.Status) {
	case "filled":
		st.Status = "FILLED"
	case "cancelled", "canceled":
		st.Status = "CANCELED"
	default: // "unfilled"
		st.Status = "NEW"
		if r.PartialFilled || r.Filled > 0 {
			st.Status = "PARTIALLY_FILLED"
		}
	}
	if st.Side == "sell" {
		st.ExecutedBase = float64(r.Filled)
	} else if r.Rate > 0 {
		// A bid's amount and filled are THB; convert at the limit rate.
		st.ExecutedBase = float64(r.Filled / r.Rate)
	} else {
		// Market bid: convert each fill at its own rate.
		for _, h := range r.History {
			if h.Rate > 0 {
				st.ExecutedBase += float64(h.Amount / h.Rate)
			}
		}
	}
	return st, nil
}

// CancelOrderV3 cancels an open order by id and side.
func (c *Client) CancelOrderV3(ctx context.Context, symbol, id, side string) error {
	body := map[string]any{"sym": V3Symbol(symbol), "id": id, "sd": strings.ToLower(side)}
	status, raw, err := c.v3Do(ctx, http.MethodPost, "/api/v3/market/cancel-order", nil, body)
	if err != nil {
		return fmt.Errorf("bitkub cancel-order: %w", err)
	}
	var env v3Envelope
	if status != http.StatusOK || json.Unmarshal(raw, &env) != nil {
		return fmt.Errorf("bitkub cancel-order: HTTP %d: %s", status, truncate(raw))
	}
	if env.Error != 0 {
		return fmt.Errorf("bitkub cancel-order: error %d", env.Error)
	}
	return nil
}

// FindOrderByClientID finds the order placed with clientID at or after
// since. It checks open orders first, then the trade history, and reads the
// order state with OrderInfo.
//
// Bitkub cannot query by client ID directly, so absence is only proved
// indirectly: it returns ErrNotFound when the order is not open and no fill
// on the symbol since `since` is unattributed. When an open order or fill in
// that window carries no client ID, or the history page is full of rows
// newer than `since`, it returns ErrAmbiguous and the caller must keep the
// order pending.
func (c *Client) FindOrderByClientID(ctx context.Context, symbol, clientID string, since time.Time) (*OrderState, error) {
	if clientID == "" {
		return nil, fmt.Errorf("bitkub: empty client id")
	}
	cutoff := since.Add(-clockSkew).UnixMilli()
	sym := url.Values{"sym": {V3Symbol(symbol)}}

	var open []struct {
		ID       flexString `json:"id"`
		Side     string     `json:"side"`
		ClientID *string    `json:"client_id"`
		TS       int64      `json:"ts"`
	}
	if err := c.v3Get(ctx, "/api/v3/market/my-open-orders", sym, &open); err != nil {
		return nil, err
	}
	ambiguous := false
	for _, o := range open {
		if o.ClientID != nil && *o.ClientID == clientID {
			return c.stateWithClientID(ctx, symbol, string(o.ID), o.Side, clientID)
		}
		if o.ClientID == nil && inWindow(o.TS, cutoff) {
			ambiguous = true
		}
	}

	var history []struct {
		OrderID  flexString `json:"order_id"`
		Side     string     `json:"side"`
		ClientID *string    `json:"client_id"`
		TS       int64      `json:"ts"`
	}
	hq := url.Values{"sym": sym["sym"], "lmt": {strconv.Itoa(historyPageSize)}}
	if err := c.v3Get(ctx, "/api/v3/market/my-order-history", hq, &history); err != nil {
		return nil, err
	}
	recent := 0
	for _, h := range history {
		if h.ClientID != nil && *h.ClientID == clientID {
			return c.stateWithClientID(ctx, symbol, string(h.OrderID), h.Side, clientID)
		}
		if inWindow(h.TS, cutoff) {
			recent++
			if h.ClientID == nil {
				ambiguous = true
			}
		}
	}
	if recent >= historyPageSize {
		ambiguous = true
	}
	if ambiguous {
		return nil, fmt.Errorf("%w: client id %s", ErrAmbiguous, clientID)
	}
	return nil, ErrNotFound
}

func (c *Client) stateWithClientID(ctx context.Context, symbol, id, side, clientID string) (*OrderState, error) {
	st, err := c.OrderInfo(ctx, symbol, id, side)
	if err != nil {
		return nil, err
	}
	st.ClientID = clientID
	return st, nil
}

// inWindow reports whether ts is at or after cutoff (ms). A missing
// timestamp counts as inside the window so it can never hide an order.
func inWindow(ts, cutoff int64) bool {
	return ts == 0 || toMillis(ts) >= cutoff
}

// toMillis accepts a timestamp in seconds or milliseconds.
func toMillis(ts int64) int64 {
	if ts > 0 && ts < 1_000_000_000_000 {
		return ts * 1000
	}
	return ts
}
