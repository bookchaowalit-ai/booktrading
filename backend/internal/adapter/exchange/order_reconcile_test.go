package exchange

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"trading-bot-system/backend/internal/config"
)

// All tests use local httptest servers with dummy keys; nothing reaches a
// real exchange.

func newTestTHAdapter(t *testing.T, h http.HandlerFunc) *BinanceTHAdapter {
	t.Helper()
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	a := NewBinanceTHAdapter("test-key", "test-secret")
	a.baseURL = srv.URL
	a.httpClient = &http.Client{Timeout: 200 * time.Millisecond}
	return a
}

func TestTHPlaceOrderSendsClientOrderID(t *testing.T) {
	var got string
	a := newTestTHAdapter(t, func(w http.ResponseWriter, r *http.Request) {
		got = r.URL.Query().Get("newClientOrderId")
		w.Write([]byte(`{"symbol":"BTCTHB","orderId":7,"clientOrderId":"grid-abc-1","status":"FILLED","executedQty":"0.5"}`))
	})
	o, err := a.PlaceOrderWithClientID(context.Background(), "BTCTHB", "BUY", "LIMIT", 0.5, 100, "GTC", "grid-abc-1")
	if err != nil {
		t.Fatal(err)
	}
	if got != "grid-abc-1" {
		t.Fatalf("newClientOrderId = %q", got)
	}
	if r := reportFromOrder(o); r.Status != "FILLED" || r.ExecutedQty != 0.5 || r.ClientOrderID != "grid-abc-1" {
		t.Fatalf("report = %+v", r)
	}
}

func TestTHPlaceOrderClassifiesOutcomes(t *testing.T) {
	cases := []struct {
		name    string
		handler http.HandlerFunc
		unknown bool
	}{
		{"timeout", func(w http.ResponseWriter, r *http.Request) { time.Sleep(500 * time.Millisecond) }, true},
		{"5xx", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusServiceUnavailable) }, true},
		{"unparsable 200", func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(`{not json`)) }, true},
		{"4xx reject", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"code":-2010,"msg":"insufficient balance"}`))
		}, false},
		{"api error in 200", func(w http.ResponseWriter, r *http.Request) {
			w.Write([]byte(`{"code":-1013,"msg":"filter failure"}`))
		}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			a := newTestTHAdapter(t, tc.handler)
			_, err := a.PlaceOrderWithClientID(context.Background(), "BTCTHB", "BUY", "MARKET", 1, 0, "", "grid-x-1")
			if err == nil {
				t.Fatal("expected an error")
			}
			if IsOrderStateUnknown(err) != tc.unknown {
				t.Fatalf("IsOrderStateUnknown = %v, want %v (err: %v)", !tc.unknown, tc.unknown, err)
			}
		})
	}
}

func TestTHGetOrderByClientID(t *testing.T) {
	a := newTestTHAdapter(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Query().Get("signature") == "" {
			t.Errorf("lookup must be a signed GET, got %s %s", r.Method, r.URL)
		}
		switch r.URL.Query().Get("origClientOrderId") {
		case "grid-known-1":
			w.Write([]byte(`{"clientOrderId":"grid-known-1","status":"PARTIALLY_FILLED","executedQty":"0.25"}`))
		case "grid-missing-1":
			w.WriteHeader(http.StatusBadRequest)
			w.Write([]byte(`{"code":-2013,"msg":"Order does not exist."}`))
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
	})
	ctx := context.Background()

	o, err := a.GetOrderByClientID(ctx, "BTCTHB", "grid-known-1")
	if err != nil {
		t.Fatal(err)
	}
	if r := reportFromOrder(o); r.Status != "PARTIALLY_FILLED" || r.ExecutedQty != 0.25 {
		t.Fatalf("report = %+v", r)
	}

	if _, err := a.GetOrderByClientID(ctx, "BTCTHB", "grid-missing-1"); !errors.Is(err, ErrOrderNotFound) {
		t.Fatalf("missing order: err = %v, want ErrOrderNotFound", err)
	}
	if _, err := a.GetOrderByClientID(ctx, "BTCTHB", "grid-broken-1"); err == nil || errors.Is(err, ErrOrderNotFound) {
		t.Fatalf("a server error must not look like not-found: %v", err)
	}
	if _, err := a.GetOrderByClientID(ctx, "BTCTHB", "bad id&x=1"); err == nil {
		t.Fatal("an invalid client order ID must be refused before any request")
	}
}

func TestExecutorTagsOrdersAndLooksThemUp(t *testing.T) {
	var placedID string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		q := r.URL.Query()
		switch r.Method {
		case http.MethodPost:
			placedID = q.Get("newClientOrderId")
			w.WriteHeader(http.StatusBadGateway)
		case http.MethodGet:
			if q.Get("origClientOrderId") != placedID {
				w.WriteHeader(http.StatusBadRequest)
				w.Write([]byte(`{"code":-2013,"msg":"Order does not exist."}`))
				return
			}
			w.Write([]byte(`{"clientOrderId":"` + placedID + `","status":"FILLED","executedQty":"1"}`))
		}
	}))
	defer srv.Close()

	m := &ExchangeManager{currentProvider: config.ExchangeBinance, binanceExecutor: NewBinanceOrderExecutorWithBaseURL("k", "s", srv.URL)}
	ctx := context.Background()
	_, err := m.PlaceOrderWithClientID(ctx, "BTCUSDT", "BUY", 1, 0, "grid-run-1")
	if !IsOrderStateUnknown(err) {
		t.Fatalf("502 must be an unknown outcome, got %v", err)
	}
	if placedID != "grid-run-1" {
		t.Fatalf("newClientOrderId = %q", placedID)
	}
	r, err := m.LookupOrderByClientID(ctx, "BTCUSDT", "grid-run-1")
	if err != nil || r.Status != "FILLED" || r.ExecutedQty != 1 {
		t.Fatalf("lookup = %+v, %v", r, err)
	}
	if _, err := m.LookupOrderByClientID(ctx, "BTCUSDT", "grid-run-2"); !errors.Is(err, ErrOrderNotFound) {
		t.Fatalf("err = %v, want ErrOrderNotFound", err)
	}
}

func TestUnsupportedExchangeCannotReconcile(t *testing.T) {
	m := &ExchangeManager{currentProvider: config.ExchangeBitkub}
	if _, err := m.LookupOrderByClientID(context.Background(), "THB_BTC", "grid-a-1"); !errors.Is(err, ErrReconcileUnsupported) {
		t.Fatalf("err = %v, want ErrReconcileUnsupported", err)
	}
	if _, err := m.PlaceOrderWithClientID(context.Background(), "THB_BTC", "BUY", 1, 1, "grid-a-1"); !errors.Is(err, ErrReconcileUnsupported) {
		t.Fatalf("err = %v, want ErrReconcileUnsupported", err)
	}
}

func TestIsOrderStateUnknownPlainErrors(t *testing.T) {
	if IsOrderStateUnknown(nil) || IsOrderStateUnknown(errors.New("rejected")) {
		t.Fatal("nil and plain errors are definitive")
	}
	if !strings.Contains(ErrOrderStateUnknown.Error(), "unknown") {
		t.Fatal("sentinel text changed")
	}
}
