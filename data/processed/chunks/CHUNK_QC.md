# Chunk QC notes (Phase 1.3)

Strategy: overview parent + per-row facet children; FAQ one-shot; holdings whole-table;
prose sections with scheme/doc/section prefixes. Hard max 512 tokens.

## kotak_large_cap_direct_growth
- chunks: 22
- max_token_estimate: 113
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
```
- exit_load mid-cell intact: True

## kotak_midcap_direct_growth
- chunks: 19
- max_token_estimate: 315
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
```
- exit_load mid-cell intact: True

## kotak_arbitrage_direct_growth
- chunks: 23
- max_token_estimate: 125
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 0.2% — Exit Load of 0.25% if redeemed in 0-30 Days
```
- exit_load mid-cell intact: True

## kotak_savings_direct_growth
- chunks: 20
- max_token_estimate: 102
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 0%
```
- exit_load mid-cell intact: True

## kotak_gold_growth_direct
- chunks: 20
- max_token_estimate: 98
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-15 Days
```
- exit_load mid-cell intact: True

## kotak_flexicap_direct_growth
- chunks: 23
- max_token_estimate: 109
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
```
- exit_load mid-cell intact: True

## kotak_liquid_growth_direct
- chunks: 21
- max_token_estimate: 170
- facets_present: expense_ratio, exit_load, min_sip, riskometer, benchmark
- facets_absent: (none)
- exit_load row sample:
```
Field | Value
Exit Load | 0.0% — Exit Load of 0.007% if redeemed in 0-1 Days, 0.0065% if redeemed in 1-2 Days, 0.006% if redeemed in 2-3 Days, 0.0055% if redeemed in 3-4 Days, 0.005% if redeemed in 4-5 Days, 0.0045% if redeemed in 5-6 Days
```
- exit_load mid-cell intact: True
