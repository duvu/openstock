# 04. Pattern engine

## Purpose

The Pattern Engine is the core of `vnalpha`.

It converts validated OHLCV time series into structured pattern instances that can be scored, tracked, backtested, explained, and reviewed.

The engine must not rely on subjective chart reading. Every pattern must be represented as data.

## Core flow

```text
canonical OHLCV
→ feature store
→ swing/pivot detection
→ pattern candidate detection
→ fuzzy scoring
→ risk flags
→ pattern_instance
```

## Pattern definition

A pattern is a structured sequence of price, volume, volatility, and relative-strength behavior.

Each pattern definition should include:

```text
pattern type
formation conditions
trigger conditions
invalidation conditions
feature requirements
score formula
risk flags
outcome labels
```

## Pattern instance

Every detected pattern should be stored as a `PatternInstance`.

Example:

```json
{
  "symbol": "FPT",
  "pattern_type": "ACCUMULATION_BREAKOUT",
  "start_date": "2026-05-10",
  "end_date": "2026-07-01",
  "trigger_date": "2026-07-02",
  "status": "CONFIRMED",
  "score": 86,
  "invalidation_price": 124500,
  "features": {
    "base_days": 38,
    "base_range_pct": 0.087,
    "volume_ratio": 1.92,
    "close_strength": 0.84,
    "rs_20d": 0.064,
    "rs_line_slope": 0.031
  },
  "risk_flags": [
    "PRICE_EXTENDED_FROM_MA20",
    "WEAK_SECTOR_CONFIRMATION"
  ]
}
```

## Pattern statuses

```text
WATCHING      = pattern is forming but not triggered
READY         = setup is close to trigger
CONFIRMED     = trigger happened
FAILED        = trigger failed after confirmation
INVALIDATED   = setup broke before confirmation
EXPIRED       = setup is stale
```

## Initial patterns

MVP should start with three patterns:

1. Accumulation Base
2. Accumulation Breakout
3. Failed Breakout

Then add:

4. Volatility Contraction Pattern
5. Healthy Pullback to MA20
6. Distribution pattern
7. Relative Strength Leader

## 1. Accumulation Base

### Intent

Find stocks consolidating constructively before a potential breakout.

### Candidate conditions

```text
lookback window: 30 to 60 sessions
base_range_pct < 10% to 15%
close_position > 0.5
MA20 flat or rising
MA50 not strongly declining
volume drying up
RS line not declining
liquidity above threshold
```

### Features

```text
base_days
base_high
base_low
base_range_pct
close_position
volume_dry_up_ratio
ma20_slope
ma50_slope
rs_20d
rs_60d
rs_line_slope
support_stability
```

### Score components

```text
base_tightness_score:       30
volume_dry_up_score:        20
ma_structure_score:         15
relative_strength_score:    20
support_stability_score:    15
```

### Invalidation

```text
close below base_low
sharp high-volume breakdown
RS line breaks down
market regime shifts to severe downtrend
```

## 2. Accumulation Breakout

### Intent

Find stocks breaking above an accumulation base with volume confirmation.

### Trigger conditions

```text
close > previous base_high
volume_today > 1.5 * volume_ma20
close_strength > 0.75
rs_20d > 0
market regime not severe downtrend
price not excessively extended from MA20
```

### Features

```text
breakout_level
volume_ratio
close_strength
price_change_1d
distance_to_ma20
rs_20d
sector_rs
market_regime
upper_shadow_pct
```

### Risk flags

```text
PRICE_EXTENDED_FROM_MA20
UPPER_SHADOW_TOO_LONG
LOW_VOLUME_CONFIRMATION
WEAK_MARKET_REGIME
WEAK_SECTOR_CONFIRMATION
LOW_LIQUIDITY
```

### Invalidation

```text
close back below breakout level
close below MA20
failed breakout within 1 to 5 sessions
large bearish reversal on high volume
```

## 3. Failed Breakout

### Intent

Detect breakouts that are failing. This is critical for reducing false positives and improving future scoring.

### Conditions

```text
A breakout was detected on day T.
Within T+1 to T+5:
- close returns below breakout level; or
- price closes back inside the base; or
- volume selling pressure increases; or
- RS line declines sharply.
```

### Features

```text
days_after_breakout
breakout_level
close_vs_breakout_level
sell_volume_ratio
rs_line_change
max_gain_after_breakout
max_drawdown_after_breakout
```

### Output

```text
pattern_type = FAILED_BREAKOUT
status = FAILED
```

## 4. Volatility Contraction Pattern

### Intent

Find stocks where price pullbacks become progressively smaller while volume dries up.

### Conditions

```text
at least 3 swing pullbacks
pullback depth decreases across swings
volume decreases across pullbacks
price remains near resistance
RS line remains stable or rising
```

Example:

```text
Pullback 1: -14%
Pullback 2: -9%
Pullback 3: -5%
```

This pattern requires a swing/pivot engine.

## 5. Healthy Pullback to MA20

### Intent

Find stocks already in an uptrend that are pulling back constructively.

### Conditions

```text
price above MA50
MA20 rising
price pulls back near MA20
volume declines during pullback
RS line remains strong
bullish recovery candle appears
```

## Swing/Pivot engine

Pattern detection should not rely only on rolling-window indicators. It also needs a pivot layer.

Pivot detection methods:

```text
local high/local low
percentage ZigZag
ATR-based pivot
```

MVP recommendation:

```text
Use percentage ZigZag or ATR-based pivot.
```

Example rule:

```text
Create a new pivot when price reverses more than 5% or more than 1.5 ATR from the previous pivot.
```

## Fuzzy scoring

Do not classify patterns only as true/false. Use scores.

Example:

```text
Pattern Score =
  30% structure_score
+ 25% volume_score
+ 20% relative_strength_score
+ 15% market_regime_score
+ 10% liquidity_score
```

Rating:

```text
85-100 = HIGH_QUALITY_SETUP
70-84  = WATCHLIST
55-69  = EARLY_CANDIDATE
<55    = IGNORE
```

## Detector interface

Recommended Python interface:

```python
from abc import ABC, abstractmethod

class PatternDetector(ABC):
    pattern_name: str

    @abstractmethod
    def detect(self, df, context) -> list[dict]:
        """
        df: canonical OHLCV + features for one symbol
        context: index data, sector data, market regime, config
        returns: list of PatternInstance-like dictionaries
        """
        raise NotImplementedError
```

## Pattern Engine plugin structure

```text
patterns/
├── base.py
├── accumulation_base.py
├── accumulation_breakout.py
├── failed_breakout.py
├── vcp.py
├── healthy_pullback.py
└── distribution.py
```

## Key implementation rule

The pattern engine should output evidence, not just a label.

Bad output:

```text
FPT is breakout.
```

Good output:

```text
FPT detected as ACCUMULATION_BREAKOUT because:
- base_range_pct = 0.087
- volume_ratio = 1.92
- close_strength = 0.84
- rs_20d = 0.064
- market_regime = UPTREND
- score = 86
```
