package exchange

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"time"
)

// Order outcome errors. An order submission can end in three ways: accepted
// (a response was parsed), definitively rejected (the exchange answered with
// a client error), or unknown (the request may have reached the matching
// engine but no usable answer came back). Unknown must never be retried
// blindly: the caller has to look the order up by its client order ID first.
var (
	// ErrOrderStateUnknown wraps submissions whose outcome is not known:
	// transport errors and timeouts, 5xx answers, unreadable bodies.
	ErrOrderStateUnknown = errors.New("order state unknown")
	// ErrOrderNotFound is returned by a lookup when the exchange has no order
	// with that client order ID.
	ErrOrderNotFound = errors.New("order not found")
	// ErrReconcileUnsupported is returned when the current exchange cannot
	// look an order up by client order ID.
	ErrReconcileUnsupported = errors.New("order lookup by client order ID not supported")
)

// Binance "Order does not exist." error code.
const binanceCodeOrderNotFound = -2013

// clientOrderIDPattern is Binance's accepted newClientOrderId format.
var clientOrderIDPattern = regexp.MustCompile(`^[.A-Z:/a-z0-9_-]{1,36}$`)

// ValidClientOrderID reports whether id can be sent as a client order ID.
func ValidClientOrderID(id string) bool {
	return clientOrderIDPattern.MatchString(id)
}

// IsOrderStateUnknown reports whether err means the order may or may not
// have been accepted. Transport failures count as unknown because the
// request can fail after the exchange received it.
func IsOrderStateUnknown(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, ErrOrderStateUnknown) || errors.Is(err, context.DeadlineExceeded) {
		return true
	}
	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}
	var urlErr *url.Error
	return errors.As(err, &urlErr)
}

// OrderReport is the exchange-neutral state of one order.
type OrderReport struct {
	ClientOrderID string
	OrderID       int64
	// Status is the exchange status: NEW, PARTIALLY_FILLED, FILLED,
	// CANCELED, EXPIRED, REJECTED, ...
	Status      string
	ExecutedQty float64
}

func reportFromOrder(o *Order) *OrderReport {
	qty, _ := strconv.ParseFloat(o.ExecutedQty, 64)
	return &OrderReport{ClientOrderID: o.ClientOrderID, OrderID: o.OrderID, Status: o.Status, ExecutedQty: qty}
}

// classifyOrderResponse turns a Binance-style order submission response into
// an order or a classified error.
func classifyOrderResponse(resp *http.Response, doErr error) (*Order, error) {
	if doErr != nil {
		return nil, fmt.Errorf("%w: request failed: %w", ErrOrderStateUnknown, doErr)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("%w: failed to read response: %w", ErrOrderStateUnknown, err)
	}
	// Binance: 5xx means the request was sent but the execution status is
	// unknown; it could have succeeded.
	if resp.StatusCode >= 500 {
		return nil, fmt.Errorf("%w: HTTP %d: %s", ErrOrderStateUnknown, resp.StatusCode, string(body))
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("order rejected: HTTP %d: %s", resp.StatusCode, string(body))
	}
	var apiErr struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &apiErr); err == nil && apiErr.Code != 0 {
		return nil, fmt.Errorf("order rejected (code %d): %s", apiErr.Code, apiErr.Msg)
	}
	var order Order
	if err := json.Unmarshal(body, &order); err != nil {
		// HTTP 200 with an unparsable body: the order was most likely accepted.
		return nil, fmt.Errorf("%w: failed to parse order response: %w", ErrOrderStateUnknown, err)
	}
	return &order, nil
}

// classifyLookupResponse turns a Binance-style order query response into an
// order, ErrOrderNotFound, or a plain error.
func classifyLookupResponse(resp *http.Response, doErr error) (*Order, error) {
	if doErr != nil {
		return nil, fmt.Errorf("order lookup failed: %w", doErr)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read order lookup response: %w", err)
	}
	var apiErr struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if resp.StatusCode != http.StatusOK {
		if json.Unmarshal(body, &apiErr) == nil && apiErr.Code == binanceCodeOrderNotFound {
			return nil, ErrOrderNotFound
		}
		return nil, fmt.Errorf("order lookup returned HTTP %d: %s", resp.StatusCode, string(body))
	}
	var order Order
	if err := json.Unmarshal(body, &order); err != nil {
		return nil, fmt.Errorf("failed to parse order lookup response: %w", err)
	}
	return &order, nil
}

// Binance "Unknown order sent." error code, returned by a cancel of an order
// that is not open (already final or never placed).
const binanceCodeUnknownOrder = -2011

// signedGet builds a signed GET request for a Binance-style endpoint.
func signedGet(ctx context.Context, baseURL, path, apiKey, query string, sign func(string) string) (*http.Request, error) {
	return signedRequest(ctx, http.MethodGet, baseURL, path, apiKey, query, sign)
}

// signedRequest builds a signed request for a Binance-style endpoint, with
// every parameter in the query string.
func signedRequest(ctx context.Context, method, baseURL, path, apiKey, query string, sign func(string) string) (*http.Request, error) {
	query += "&timestamp=" + strconv.FormatInt(time.Now().UnixMilli(), 10)
	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", baseURL, path, query, sign(query))
	req, err := http.NewRequestWithContext(ctx, method, reqURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-MBX-APIKEY", apiKey)
	req.Header.Set("Accept", "application/json")
	return req, nil
}

// cancelByClientID cancels a Binance-style order by client order ID. It
// returns ErrOrderNotFound when the order is not open any more (already
// final, or never placed); the caller learns the final state by lookup.
func cancelByClientID(ctx context.Context, client *http.Client, baseURL, path, apiKey, symbol, clientOrderID string, sign func(string) string) error {
	if !ValidClientOrderID(clientOrderID) {
		return fmt.Errorf("invalid client order ID %q", clientOrderID)
	}
	req, err := signedRequest(ctx, http.MethodDelete, baseURL, path, apiKey,
		fmt.Sprintf("symbol=%s&origClientOrderId=%s", symbol, clientOrderID), sign)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("cancel failed: %w", err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read cancel response: %w", err)
	}
	if resp.StatusCode == http.StatusOK {
		return nil
	}
	var apiErr struct {
		Code int `json:"code"`
	}
	if json.Unmarshal(body, &apiErr) == nil && (apiErr.Code == binanceCodeUnknownOrder || apiErr.Code == binanceCodeOrderNotFound) {
		return ErrOrderNotFound
	}
	return fmt.Errorf("cancel returned HTTP %d: %s", resp.StatusCode, string(body))
}
