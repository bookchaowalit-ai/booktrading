package bitkub

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

// All tests use a local httptest server with dummy keys; nothing reaches
// Bitkub.

const testSecret = "dummy-secret"

// fakeBitkub serves the v3 endpoints from in-memory state and checks every
// request signature.
type fakeBitkub struct {
	mu        sync.Mutex
	t         *testing.T
	placeCode int    // HTTP status for place-*; 0 means 200
	placeBody string // raw body for place-*; "" means success
	open      string // JSON array for my-open-orders
	history   string // JSON array for my-order-history
	info      map[string]string
	placed    []map[string]any
	paths     []string
	cancelled []map[string]any
}

func (f *fakeBitkub) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	body, _ := io.ReadAll(r.Body)
	target := r.URL.Path
	if r.URL.RawQuery != "" {
		target += "?" + r.URL.RawQuery
	}
	mac := hmac.New(sha256.New, []byte(testSecret))
	mac.Write([]byte(r.Header.Get("X-BTK-TIMESTAMP") + r.Method + target + string(body)))
	if r.Header.Get("X-BTK-SIGN") != hex.EncodeToString(mac.Sum(nil)) || r.Header.Get("X-BTK-APIKEY") != "dummy-key" {
		f.t.Errorf("bad signature or key for %s %s", r.Method, target)
		w.Write([]byte(`{"error":6}`))
		return
	}
	f.paths = append(f.paths, r.Method+" "+r.URL.Path)
	switch r.URL.Path {
	case "/api/v3/market/place-bid", "/api/v3/market/place-ask":
		var m map[string]any
		_ = json.Unmarshal(body, &m)
		f.placed = append(f.placed, m)
		if f.placeCode != 0 {
			w.WriteHeader(f.placeCode)
		}
		if f.placeBody != "" {
			w.Write([]byte(f.placeBody))
			return
		}
		w.Write([]byte(`{"error":0,"result":{"id":"101","hash":"h","typ":"limit","ci":"` + m["client_id"].(string) + `"}}`))
	case "/api/v3/market/my-open-orders":
		w.Write([]byte(`{"error":0,"result":` + orDefault(f.open) + `}`))
	case "/api/v3/market/my-order-history":
		w.Write([]byte(`{"error":0,"result":` + orDefault(f.history) + `}`))
	case "/api/v3/market/order-info":
		q := r.URL.Query()
		res, ok := f.info[q.Get("id")+"/"+q.Get("sd")]
		if !ok {
			w.Write([]byte(`{"error":24}`))
			return
		}
		w.Write([]byte(`{"error":0,"result":` + res + `}`))
	case "/api/v3/market/cancel-order":
		var m map[string]any
		_ = json.Unmarshal(body, &m)
		f.cancelled = append(f.cancelled, m)
		w.Write([]byte(`{"error":0}`))
	default:
		w.WriteHeader(http.StatusNotFound)
	}
}

func orDefault(s string) string {
	if s == "" {
		return "[]"
	}
	return s
}

func newFake(t *testing.T) (*fakeBitkub, *Client) {
	t.Helper()
	f := &fakeBitkub{t: t, info: map[string]string{}}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	c := NewClient("dummy-key", testSecret, false)
	c.BaseURL = srv.URL
	return f, c
}

func TestV3Symbol(t *testing.T) {
	for in, want := range map[string]string{
		"THB_BTC": "btc_thb",
		"BTC_THB": "btc_thb",
		"btc_thb": "btc_thb",
		"BTCTHB":  "btc_thb",
		" eththb": "eth_thb",
	} {
		if got := V3Symbol(in); got != want {
			t.Errorf("V3Symbol(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestPlaceOrderV3SendsDocumentedBody(t *testing.T) {
	f, c := newFake(t)
	st, err := c.PlaceOrderV3(context.Background(), "THB_BTC", "BUY", 1000, 2_000_000, "grid-a-1")
	if err != nil {
		t.Fatal(err)
	}
	if st.ID != "101" || st.Status != "NEW" || st.Side != "buy" {
		t.Fatalf("state = %+v", st)
	}
	got := f.placed[0]
	if f.paths[0] != "POST /api/v3/market/place-bid" || got["sym"] != "btc_thb" || got["amt"] != 1000.0 ||
		got["rat"] != 2_000_000.0 || got["typ"] != "limit" || got["client_id"] != "grid-a-1" {
		t.Fatalf("placed %v at %v", got, f.paths)
	}

	if _, err := c.PlaceOrderV3(context.Background(), "btc_thb", "sell", 0.001, 0, "grid-a-2"); err != nil {
		t.Fatal(err)
	}
	if f.paths[1] != "POST /api/v3/market/place-ask" || f.placed[1]["typ"] != "market" {
		t.Fatalf("sell placed %v at %v", f.placed[1], f.paths)
	}
}

func TestPlaceOrderV3ClassifiesOutcomes(t *testing.T) {
	cases := []struct {
		name    string
		code    int
		body    string
		unknown bool
	}{
		{"5xx", http.StatusBadGateway, `bad gateway`, true},
		{"server error 90", 0, `{"error":90}`, true},
		{"unparsable 200", 0, `<html>`, true},
		{"accepted without id", 0, `{"error":0,"result":{}}`, true},
		{"insufficient balance", 0, `{"error":18}`, false},
		{"4xx", http.StatusBadRequest, `{"error":10}`, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			f, c := newFake(t)
			f.placeCode, f.placeBody = tc.code, tc.body
			_, err := c.PlaceOrderV3(context.Background(), "btc_thb", "buy", 100, 1, "grid-b-1")
			if err == nil {
				t.Fatal("want an error")
			}
			if errors.Is(err, ErrOutcomeUnknown) != tc.unknown {
				t.Fatalf("unknown = %v, want %v (%v)", !tc.unknown, tc.unknown, err)
			}
		})
	}
}

func TestPlaceOrderV3TransportErrorIsUnknown(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	srv.Close()
	c := NewClient("dummy-key", testSecret, false)
	c.BaseURL = srv.URL
	_, err := c.PlaceOrderV3(context.Background(), "btc_thb", "buy", 100, 1, "grid-c-1")
	if !errors.Is(err, ErrOutcomeUnknown) {
		t.Fatalf("err = %v, want ErrOutcomeUnknown", err)
	}
}

func TestFindOrderByClientID(t *testing.T) {
	since := time.Now()
	ts := since.UnixMilli()
	ms := func(d time.Duration) string { return strings.TrimSpace(jsonNum(ts + d.Milliseconds())) }

	t.Run("open order, partially filled bid", func(t *testing.T) {
		f, c := newFake(t)
		f.open = `[{"id":"7","side":"buy","client_id":"other","ts":` + ms(time.Second) + `},{"id":"8","side":"buy","client_id":"grid-d-1","ts":` + ms(time.Second) + `}]`
		f.info["8/buy"] = `{"amount":1000,"rate":2000000,"filled":500,"status":"unfilled","partial_filled":true}`
		st, err := c.FindOrderByClientID(context.Background(), "THB_BTC", "grid-d-1", since)
		if err != nil {
			t.Fatal(err)
		}
		if st.ID != "8" || st.Status != "PARTIALLY_FILLED" || st.ExecutedBase != 0.00025 {
			t.Fatalf("state = %+v", st)
		}
	})

	t.Run("filled ask found in history", func(t *testing.T) {
		f, c := newFake(t)
		f.history = `[{"order_id":"9","side":"sell","client_id":"grid-d-2","ts":` + ms(2*time.Second) + `}]`
		f.info["9/sell"] = `{"amount":"0.001","rate":"2000000","filled":"0.001","status":"filled"}`
		st, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-2", since)
		if err != nil {
			t.Fatal(err)
		}
		if st.Status != "FILLED" || st.ExecutedBase != 0.001 {
			t.Fatalf("state = %+v", st)
		}
	})

	t.Run("cancelled bid", func(t *testing.T) {
		f, c := newFake(t)
		f.history = `[{"order_id":"10","side":"buy","client_id":"grid-d-3","ts":` + ms(time.Second) + `}]`
		f.info["10/buy"] = `{"amount":1000,"rate":2000000,"filled":0,"status":"cancelled"}`
		st, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-3", since)
		if err != nil || st.Status != "CANCELED" || st.ExecutedBase != 0 {
			t.Fatalf("state = %+v, %v", st, err)
		}
	})

	t.Run("absent with only older fills", func(t *testing.T) {
		f, c := newFake(t)
		f.history = `[{"order_id":"1","side":"buy","ts":` + ms(-time.Hour) + `}]`
		_, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-4", since)
		if !errors.Is(err, ErrNotFound) {
			t.Fatalf("err = %v, want ErrNotFound", err)
		}
	})

	ambiguous := map[string]func(f *fakeBitkub){
		"recent fill without client id": func(f *fakeBitkub) {
			f.history = `[{"order_id":"2","side":"buy","ts":` + ms(time.Second) + `}]`
		},
		"recent open order without client id": func(f *fakeBitkub) {
			f.open = `[{"id":"3","side":"buy","ts":` + ms(time.Second) + `}]`
		},
		"row without timestamp": func(f *fakeBitkub) {
			f.history = `[{"order_id":"4","side":"sell"}]`
		},
	}
	for name, setup := range ambiguous {
		t.Run(name, func(t *testing.T) {
			f, c := newFake(t)
			setup(f)
			_, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-5", since)
			if !errors.Is(err, ErrAmbiguous) {
				t.Fatalf("err = %v, want ErrAmbiguous", err)
			}
		})
	}

	t.Run("full history page is ambiguous", func(t *testing.T) {
		f, c := newFake(t)
		rows := make([]string, historyPageSize)
		for i := range rows {
			rows[i] = `{"order_id":"5","side":"buy","client_id":"other","ts":` + ms(time.Second) + `}`
		}
		f.history = "[" + strings.Join(rows, ",") + "]"
		_, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-6", since)
		if !errors.Is(err, ErrAmbiguous) {
			t.Fatalf("err = %v, want ErrAmbiguous", err)
		}
	})

	t.Run("seconds timestamps", func(t *testing.T) {
		f, c := newFake(t)
		f.history = `[{"order_id":"6","side":"buy","ts":` + jsonNum(since.Unix()-3600) + `}]`
		if _, err := c.FindOrderByClientID(context.Background(), "btc_thb", "grid-d-7", since); !errors.Is(err, ErrNotFound) {
			t.Fatalf("err = %v, want ErrNotFound", err)
		}
	})
}

func TestCancelOrderV3(t *testing.T) {
	f, c := newFake(t)
	if err := c.CancelOrderV3(context.Background(), "THB_BTC", "8", "BUY"); err != nil {
		t.Fatal(err)
	}
	got := f.cancelled[0]
	if got["sym"] != "btc_thb" || got["id"] != "8" || got["sd"] != "buy" {
		t.Fatalf("cancel body = %v", got)
	}
}

func jsonNum(v int64) string {
	b, _ := json.Marshal(v)
	return string(b)
}
