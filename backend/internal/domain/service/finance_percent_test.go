package service

import (
	"encoding/json"
	"math"
	"testing"
)

// A zero budget/target or an empty expense month used to yield NaN/Inf
// percentages, which break JSON encoding of the whole dashboard response.
func TestBoundedPercentHandlesZeroWhole(t *testing.T) {
	cases := []struct{ part, whole, want float64 }{
		{50, 200, 25},
		{300, 200, 100},
		{0, 0, 0},
		{10, 0, 0},
		{-5, 100, 0},
		{math.NaN(), 100, 0},
		{10, math.NaN(), 0},
	}
	for _, c := range cases {
		got := boundedPercent(c.part, c.whole)
		if got != c.want {
			t.Errorf("boundedPercent(%v, %v) = %v, want %v", c.part, c.whole, got, c.want)
		}
		if _, err := json.Marshal(got); err != nil {
			t.Errorf("boundedPercent(%v, %v) not JSON-encodable: %v", c.part, c.whole, err)
		}
	}
}

// Goals due within 30 days used to divide by int(days/30) == 0.
func TestGoalOnTrackWithinFirstMonth(t *testing.T) {
	if !goalOnTrack(1000, 1000, 0, 10) {
		t.Error("reached goal due in 10 days reported off track")
	}
	if !goalOnTrack(1000, 900, 400, 10) {
		t.Error("100 missing, ~133 contributed in 10 days: want on track")
	}
	if goalOnTrack(1000, 0, 100, 10) {
		t.Error("1000 missing, ~33 contributed in 10 days: want off track")
	}
	if goalOnTrack(1000, 0, 100, 0) {
		t.Error("overdue unmet goal reported on track")
	}
	// 45 days used to count as one month (integer division).
	if !goalOnTrack(1000, 0, 700, 45) {
		t.Error("700/month over 1.5 months covers 1000")
	}
}
