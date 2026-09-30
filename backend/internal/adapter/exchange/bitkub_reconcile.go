package exchange

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
)

// placeBitkubWithClientID places a Bitkub v3 order tagged with clientOrderID.
// quantity is always in the base asset; a buy is converted to THB at price
// because Bitkub's place-bid takes a THB amount. price 0 (market) is only
// allowed for sells, since a market buy has no price to convert with.
func placeBitkubWithClientID(ctx context.Context, c *bitkub.Client, symbol, side string, quantity, price float64, clientOrderID string) (*OrderReport, error) {
	if quantity <= 0 || price < 0 {
		return nil, fmt.Errorf("invalid Bitkub order: quantity %v price %v", quantity, price)
	}
	amt := quantity
	switch strings.ToUpper(side) {
	case "BUY":
		if price == 0 {
			return nil, fmt.Errorf("Bitkub buy needs a price to convert %v base units to THB", quantity)
		}
		amt = quantity * price
	case "SELL":
	default:
		return nil, fmt.Errorf("invalid side %q", side)
	}
	st, err := c.PlaceOrderV3(ctx, symbol, side, amt, price, clientOrderID)
	if err != nil {
		if errors.Is(err, bitkub.ErrOutcomeUnknown) {
			return nil, fmt.Errorf("%w: %w", ErrOrderStateUnknown, err)
		}
		return nil, err
	}
	return bitkubReport(st, clientOrderID), nil
}

// lookupBitkubByClientID maps bitkub.FindOrderByClientID onto the
// exchange-neutral contract: bitkub.ErrNotFound becomes ErrOrderNotFound,
// and an ambiguous answer stays an error so the order is kept pending.
func lookupBitkubByClientID(ctx context.Context, c *bitkub.Client, symbol, clientOrderID string, since time.Time) (*OrderReport, error) {
	if since.IsZero() {
		return nil, fmt.Errorf("Bitkub lookup of %s needs the submission time", clientOrderID)
	}
	st, err := c.FindOrderByClientID(ctx, symbol, clientOrderID, since)
	if errors.Is(err, bitkub.ErrNotFound) {
		return nil, ErrOrderNotFound
	}
	if err != nil {
		return nil, err
	}
	return bitkubReport(st, clientOrderID), nil
}

// cancelBitkubByClientID cancels the open Bitkub order with clientOrderID.
func cancelBitkubByClientID(ctx context.Context, c *bitkub.Client, symbol, clientOrderID string, since time.Time) error {
	st, err := c.FindOrderByClientID(ctx, symbol, clientOrderID, since)
	if errors.Is(err, bitkub.ErrNotFound) {
		return ErrOrderNotFound
	}
	if err != nil {
		return err
	}
	return c.CancelOrderV3(ctx, symbol, st.ID, st.Side)
}

func bitkubReport(st *bitkub.OrderState, clientOrderID string) *OrderReport {
	id, _ := strconv.ParseInt(st.ID, 10, 64)
	return &OrderReport{ClientOrderID: clientOrderID, OrderID: id, Status: st.Status, ExecutedQty: st.ExecutedBase}
}
