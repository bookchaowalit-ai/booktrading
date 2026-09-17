# Selective Alpha Research

This module is the first decision layer for a future multi-platform trading
system. Its initial market group is `prediction_binary`, covering a normalized
YES/NO contract such as World Markets or Polymarket. Fomo and other venues stay
outside this contract until their read-only data and settlement semantics are
verified.

## Operating rule

The system does not try to trade every quote. It evaluates a bounded,
falsifiable thesis:

```text
evidence → fair value → maximum entry → target → invalidation → risk budget
```

For `prediction_binary`, `fair_value` and `price` always refer to the selected
side (`YES` for `buy_yes`, `NO` for `buy_no`). The evaluator never infers a
fair value from a future settlement.

The result is one of:

- `WAIT`: data, thesis, or risk controls are not safe enough.
- `WATCH`: the thesis is coherent, but the current price or fillability is not
  inside the entry gate.
- `TRADE_PAPER`: all gates pass, but this is still only a paper decision.

Every result is recorded, including `WAIT` and `WATCH`. That prevents a later
review from counting only attractive historical examples and gives us a
denominator for missed or rejected opportunities.

## Data and safety boundary

### Cost and risk contract

Observations now require an explicit finite, nonnegative `cost_per_unit`
before a paper entry. This is a conservative total reserve per selected-side
unit for fees and slippage through the planned exit or settlement. Missing
costs produce `WAIT/cost_unknown`; zero is allowed only as an explicit
scenario assumption. These are supplied estimates, not verified venue rates.

Net edge = selected-side fair value − ask price − cost reserve.
Negative edge remains negative in the decision journal.
Worst-case risk = units × (ask price + cost reserve). Both the thesis loss
ceiling and capital ceiling must cover that amount, as must the portfolio
risk limits. Invalidation is a thesis condition, not a guaranteed stop fill.
Prices must represent executable asks for the selected side.

The evaluator checks future evidence/thesis/quotes directly and adds elapsed
time since observation to quote age. Historical inputs without the new cost
field still load, but cannot produce paper entries. Existing synthetic fixture
P&L labels remain supplied outcomes; the runner does not calculate fills or
settlement P&L from those labels.

### First research thesis: delayed repricing after an official event

Status: proposed hypothesis; no measured alpha or live candidate yet.
Owner/consumer: BookTrading research, for selective paper decisions.
Scope: one family of binary contracts whose written resolution rule maps
unambiguously to a scheduled public release.

Hypothesis: a verified official release may change the selected outcome's
estimated probability before the executable market quote reflects it.
Reject contracts with ambiguous rules, disputed definitions or unavailable
quotes. Do not assign probability 1 merely because a headline looks decisive.

Required evidence before evaluation:

- Exact venue contract ID, selected side and saved resolution-rule version.
- Official primary release URL and immutable landing/Bronze checksum.
- Release publication time AND local availability time; use the later time
  for evidence availability, before the decision quote.
- A versioned rule mapping the release to the contract and a justified
  conservative probability estimate, including resolution uncertainty.
- Selected-side ask, depth, quote timestamp and explicit venue cost estimate.

Entry requires positive net edge above the frozen threshold, full-cost risk
within budget and fresh depth for all requested units. A correction to the
release, rule mismatch, expired quote or missing evidence invalidates the
candidate. Exit target and invalidation must be fixed before recording it.

Next implementation is a reviewed source-to-contract mapping and lake snapshot
consumer. No official release feed or probability estimator is connected yet.
Prospective evaluation must save every eligible candidate before its result is
known, freeze policy/cost assumptions, and reconcile actual paper fills and
outcomes. Merely splitting synthetic or retrospectively selected cases by date
does not establish out-of-sample performance.

- `AlphaEvidence` stores a short source reference, timestamp, optional URL, and
  optional SHA-256 reference; it does not store raw payloads, cookies, tokens,
  wallet material, or credentials.
- Provider adapters remain read-only producers. Raw responses belong in the
  lake landing/Bronze boundary; the alpha journal is a normalized downstream
  decision projection.
- `RiskBudget` is explicitly paper-only. There is no live order client,
  credential field, or execution switch in this module.
- A missing quote age, missing available size, missing invalidation, stale quote,
  or exceeded exposure limit fails closed to `WAIT` under the default CLI.

## Replay and forward gate

The JSONL replay is versioned and bounded. Cases must be chronological. A
settlement can affect open paper exposure only at or after its timestamp; it is
never used to decide an earlier quote. The `--forward-start` cut separates
historical/training observations from later forward observations.

Run the included offline example:

```bash
cd strategy
python3 scripts/alpha_research.py \
  tests/fixtures/alpha/prediction_binary_cases.jsonl \
  --forward-start 2026-09-13T00:00:00Z
```

The output contains separate train/forward decisions, P&L, win rate, drawdown,
reason counts, pending exposure, and a forward-evidence gate. A passing gate
means only that enough paper observations exist for a human review; it never
promotes the system to live execution.

## Promotion criteria

Before connecting any future execution adapter, require all of the following
outside this module:

1. A documented provider permission and read-only data contract.
2. A materially larger, timestamped forward sample across more than one market
   regime, with fees, slippage, spread, partial fills, and settlement disputes
   represented.
3. Reconciliation between source evidence, journal decisions, paper ledger, and
   eventual settlement results.
4. Independent security, operational, and capital-protection review.
5. An explicit human approval and a separate execution implementation. This
   research package cannot grant that approval by itself.

The included fixture is a test harness, not proof of alpha.
