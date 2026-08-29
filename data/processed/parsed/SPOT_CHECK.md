# Parse spot-check notes (Phase 1.2)

Fee/load tables are serialized as stable `Field | Value` rows from IndMoney
`fund_overview.info` (or DOM key-parameter tables). Manual override flagged
when expense ratio or exit load could not be extracted.

## kotak_large_cap_direct_growth
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.67%
- exit_load: 1.0% — Exit Load of 1% if redeemed in 0-1 Years
- min_sip: ₹100
- riskometer: Very High Risk
- benchmark: Nifty 100 TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.67%
Benchmark | Nifty 100 TR INR — This is an index against which the fund's performance is measured.
AUM | ₹11028 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
Lock In | No Lock-in
TurnOver | 40.28% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_midcap_direct_growth
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.39%
- exit_load: 1.0% — Exit Load of 1% if redeemed in 0-1 Years
- min_sip: ₹100
- riskometer: Very High Risk
- benchmark: Nifty Midcap 150 TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.39%
Benchmark | Nifty Midcap 150 TR INR — This is an index against which the fund's performance is measured.
AUM | ₹69283 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
Lock In | No Lock-in
TurnOver | 24.31% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_arbitrage_direct_growth
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 2.3734%
- exit_load: 0.2% — Exit Load of 0.25% if redeemed in 0-30 Days
- min_sip: ₹100
- riskometer: Low Risk
- benchmark: NIFTY 50 Arbitrage TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 2.3734%
Benchmark | NIFTY 50 Arbitrage TR INR — This is an index against which the fund's performance is measured.
AUM | ₹74399 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 0.2% — Exit Load of 0.25% if redeemed in 0-30 Days
Lock In | No Lock-in
TurnOver | 2200.36% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_savings_direct_growth
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.37%
- exit_load: 0%
- min_sip: ₹100
- riskometer: Moderate Risk
- benchmark: NIFTY Ultra Short Duration Debt TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.37%
Benchmark | NIFTY Ultra Short Duration Debt TR INR — This is an index against which the fund's performance is measured.
AUM | ₹15708 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 0%
Lock In | No Lock-in
TurnOver | 182.03% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_gold_growth_direct
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.66%
- exit_load: 1.0% — Exit Load of 1% if redeemed in 0-15 Days
- min_sip: ₹100
- riskometer: High Risk
- benchmark: Domestic Price of Physical Gold TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.66%
Benchmark | Domestic Price of Physical Gold TR INR — This is an index against which the fund's performance is measured.
AUM | ₹6532 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-15 Days
Lock In | No Lock-in
TurnOver | 0.07% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_flexicap_direct_growth
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.61%
- exit_load: 1.0% — Exit Load of 1% if redeemed in 0-1 Years
- min_sip: ₹100
- riskometer: Very High Risk
- benchmark: Nifty 500 TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.61%
Benchmark | Nifty 500 TR INR — This is an index against which the fund's performance is measured.
AUM | ₹56119 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹100/₹100
Exit Load | 1.0% — Exit Load of 1% if redeemed in 0-1 Years
Lock In | No Lock-in
TurnOver | 9.4% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```

## kotak_liquid_growth_direct
- Status: success
- Parse source: next_data
- Fee/load tables OK: True
- Manual override needed: False
- expense_ratio: 0.19%
- exit_load: 0.0% — Exit Load of 0.007% if redeemed in 0-1 Days, 0.0065% if redeemed in 1-2 Days, 0.006% if redeemed in 2-3 Days, 0.0055% if redeemed in 3-4 Days, 0.005% if redeemed in 4-5 Days, 0.0045% if redeemed in 5-6 Days
- min_sip: --
- riskometer: Moderate Risk
- benchmark: Nifty Liquid Index TR INR
- Fee/load serialized sample:
```
Field | Value
Expense ratio | 0.19%
Benchmark | Nifty Liquid Index TR INR — This is an index against which the fund's performance is measured.
AUM | ₹51309 Cr
Inception Date | 1 January, 2013
Min Lumpsum/SIP | ₹1,000/--
Exit Load | 0.0% — Exit Load of 0.007% if redeemed in 0-1 Days, 0.0065% if redeemed in 1-2 Days, 0.006% if redeemed in 2-3 Days, 0.0055% if redeemed in 3-4 Days, 0.005% if redeemed in 4-5 Days, 0.0045% if redeemed in 5-6 Days
Lock In | No Lock-in
TurnOver | 483.48% — Turnover ratio reflects the proportion of stocks that have changed in the portfolio in the last 1 year
```
