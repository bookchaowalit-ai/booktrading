package exchange

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"

	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
	"trading-bot-system/backend/internal/config"
)

// fakeBitkubServer answers place-bid with a 502 after "accepting" the order,
// then reports it as open and filled. No signature check here; the bitkub
// package tests cover signing.
func fakeBitkubServer(t *testing.T, filled bool) (*ExchangeManager, *[]string) {
	t.Helper()
	var calls []string
	var clientID string
	placedAt := time.Now().UnixMilli()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls = append(calls, r.URL.Path)
		switch r.URL.Path {
		case "/api/v3/market/place-bid":
			b := make([]byte, 512)
			n, _ := r.Body.Read(b)
			if i := strings.Index(string(b[:n]), `"client_id":"`); i >= 0 {
				rest := string(b[i+len(`"client_id":"`) : n])
				clientID = rest[:strings.Index(rest, `"`)]
			}
			w.WriteHeader(http.StatusBadGateway)
		case "/api/v3/market/my-open-orders":
			w.Write([]byte(`{"error":0,"result":[{"id":"55","side":"buy","client_id":"` + clientID + `","ts":` + strconv.FormatInt(placedAt, 10) + `}]}`))
		case "/api/v3/market/my-order-history":
			w.Write([]byte(`{"error":0,"result":[]}`))
		case "/api/v3/market/order-info":
			status, got := "unfilled", "0"
			if filled {
				status, got = "filled", "1000"
			}
			w.Write([]byte(`{"error":0,"result":{"amount":1000,"rate":1000000,"filled":` + got + `,"status":"` + status + `"}}`))
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(srv.Close)
	c := bitkub.NewClient("dummy-key", "dummy-secret", false)
	c.BaseURL = srv.URL
	return &ExchangeManager{currentProvider: config.ExchangeBitkub, bitkubClient: c}, &calls
}

func TestBitkubUnknownOrderIsReconciledByClientID(t *testing.T) {
	m, calls := fakeBitkubServer(t, true)
	ctx := context.Background()
	since := time.Now()
	_, err := m.PlaceOrderWithClientID(ctx, "THB_BTC", "BUY", 0.001, 1_000_000, "grid-bk-1")
	if !IsOrderStateUnknown(err) {
		t.Fatalf("502 must be an unknown outcome, got %v", err)
	}
	r, err := m.LookupOrderByClientIDSince(ctx, "THB_BTC", "grid-bk-1", since)
	if err != nil || r.Status != "FILLED" || r.ExecutedQty != 0.001 || r.OrderID != 55 {
		t.Fatalf("lookup = %+v, %v", r, err)
	}
	for _, p := range *calls {
		if p == "/api/v3/market/place-bid" {
			continue
		}
		if strings.Contains(p, "place-") {
			t.Fatalf("lookup must never place an order: %v", *calls)
		}
	}
	if _, err := m.LookupOrderByClientIDSince(ctx, "THB_BTC", "grid-bk-2", since); !errors.Is(err, ErrOrderNotFound) {
		t.Fatalf("err = %v, want ErrOrderNotFound", err)
	}
}

func TestBitkubLookupNeedsSubmissionTime(t *testing.T) {
	m, _ := fakeBitkubServer(t, false)
	if _, err := m.LookupOrderByClientID(context.Background(), "THB_BTC", "grid-bk-3"); err == nil || errors.Is(err, ErrOrderNotFound) {
		t.Fatalf("a lookup without a window must not prove absence, got %v", err)
	}
}

func TestBitkubBuyNeedsPrice(t *testing.T) {
	m, calls := fakeBitkubServer(t, false)
	if _, err := m.PlaceOrderWithClientID(context.Background(), "THB_BTC", "BUY", 1, 0, "grid-bk-4"); err == nil || IsOrderStateUnknown(err) {
		t.Fatalf("market buy without a price must be rejected locally, got %v", err)
	}
	if len(*calls) != 0 {
		t.Fatalf("nothing may be sent: %v", *calls)
	}
}
