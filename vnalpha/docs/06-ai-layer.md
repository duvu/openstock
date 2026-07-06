# 06. AI layer

## Purpose

The AI layer turns deterministic research outputs into explanations, critiques, reports, and journal entries.

AI should improve analyst productivity. It should not become the source of truth for signal generation.

## Boundary

AI may do:

```text
explain detected patterns
criticize risk
summarize daily market context
compare current patterns with historical outcomes
write journal notes
help query research data
suggest parameters to test
```

AI must not do:

```text
generate unverified buy/sell signals
override risk gates
place orders
invent data
claim certainty
recommend trades as investment advice
```

## Position in architecture

```text
pattern_instance + feature_json + risk_json + outcome history
→ AI explanation service
→ dashboard/report/journal
```

AI consumes structured data produced by the deterministic engine.

AI should not scrape charts visually in MVP.

## AI services

### 1. Signal Explanation Service

Input:

```json
{
  "symbol": "FPT",
  "pattern_type": "ACCUMULATION_BREAKOUT",
  "score": 86,
  "status": "CONFIRMED",
  "features": {
    "base_days": 38,
    "base_range_pct": 0.087,
    "volume_ratio": 1.92,
    "close_strength": 0.84,
    "rs_20d": 0.064,
    "distance_to_ma20": 0.078
  },
  "market_regime": "UPTREND",
  "risk_flags": [
    "PRICE_EXTENDED_FROM_MA20",
    "WEAK_SECTOR_CONFIRMATION"
  ]
}
```

Output:

```text
FPT is detected as an accumulation breakout. The base lasted 38 sessions and had a narrow 8.7% range, which indicates constructive consolidation. Breakout volume reached 1.92x the 20-session average and the candle closed near the high, supporting demand confirmation. RS 20d is +6.4% versus VN-Index, so the stock is outperforming the market. Main risks are extension from MA20 and weak sector confirmation.
```

### 2. Risk Critic Service

Purpose:

- identify why a setup may fail;
- check whether the pattern is too extended;
- detect weak volume confirmation;
- check market-regime risk;
- check sector non-confirmation;
- flag low liquidity or data-quality issues.

Prompt stance:

```text
Act as a skeptical risk reviewer. Use only provided features and metadata. Do not invent missing facts. If evidence is insufficient, say so.
```

### 3. Daily Market Report Service

Inputs:

```text
market regime
number of accumulation bases
number of confirmed breakouts
number of failed breakouts
breadth indicators
top patterns
risk summary
```

Output sections:

```text
Market regime
Breadth
Pattern activity
Top watchlist candidates
Failed breakout warning
Risk summary
Next-session focus
```

### 4. Pattern Review Service

Purpose:

Compare current pattern candidates with historical outcome data.

Example questions:

```text
How did similar setups perform historically?
Which features are common among failed breakouts?
Does this pattern work better in uptrend or sideway regime?
```

### 5. Trading Journal Service

Purpose:

Generate structured journal notes.

Sections:

```text
Setup thesis
Evidence
Risk
Invalidation
Expected scenarios
Post-outcome lesson
```

## AI output requirements

AI outputs should be:

- grounded in feature values;
- concise;
- explicit about uncertainty;
- separated from deterministic scores;
- stored with model metadata.

Every AI generation should store:

```text
model_name
prompt_version
input_hash
generated_at
pattern_id
output_text
```

## Prompt templates

### Explain pattern

```text
You are an equity research assistant. Explain the detected pattern using only the structured inputs below.

Rules:
- Do not give investment advice.
- Do not claim the stock will rise.
- Explain why the system detected the pattern.
- Mention key risks and invalidation.
- If a field is missing, state that evidence is unavailable.

Input:
{pattern_json}
```

### Risk critique

```text
You are a skeptical risk reviewer for a rule-based pattern detection system.

Task:
Identify reasons this setup could fail.

Rules:
- Use only the provided data.
- Prefer concrete feature values.
- Do not recommend buying or selling.
- Separate data-quality risk, market risk, setup risk, and execution risk.

Input:
{pattern_json}
```

### Daily report

```text
You are writing an end-of-day market research brief for a Vietnamese equity watchlist system.

Use only the provided system outputs.

Sections:
1. Market regime
2. Breadth and participation
3. Pattern activity
4. Top confirmed setups
5. Failed breakout warnings
6. Risk summary
7. Watchlist focus

Input:
{daily_summary_json}
```

## Guardrails

### Hard guardrails

The AI layer must not:

- place orders;
- generate broker API payloads;
- override signal scores;
- override risk flags;
- fabricate price/volume data;
- provide certainty language such as “will rise” or “guaranteed”.

### Soft guardrails

AI should use language such as:

```text
The system detected...
The evidence suggests...
The setup has these risk flags...
This should remain on watchlist until...
```

Avoid:

```text
Buy now
This stock will increase
Guaranteed breakout
Risk-free opportunity
```

## LLM gateway

MVP can use a direct LLM API or a LiteLLM-compatible gateway.

Recommended interface:

```python
class AIClient:
    def generate(self, template_name: str, payload: dict) -> str:
        raise NotImplementedError
```

## Caching

AI outputs should be cached by:

```text
pattern_id
prompt_version
input_hash
model_name
```

This prevents repeated generation for the same deterministic input.

## Observability

Track:

```text
prompt_version
model
latency
token usage
cost
failure rate
manual override/edit rate
```

## MVP deliverables

- `ai/explain_pattern.py`
- `ai/risk_critic.py`
- `ai/daily_report.py`
- prompt templates
- AI output table
- prompt versioning
- Streamlit display of explanation + risk critique
