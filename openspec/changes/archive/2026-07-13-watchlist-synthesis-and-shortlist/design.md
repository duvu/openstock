# Design: Watchlist Synthesis and Shortlist

## Architecture

```text
daily_watchlist + candidate_score + setup_analysis + regime/sector context
  -> WatchlistSynthesizer
  -> ShortlistBuilder
  -> artifact/repository persistence
  -> command rendering
  -> assistant synthesis
  -> TUI panel/output stream
```

## Proposed modules

```text
vnalpha/research_intelligence/watchlist_synthesis.py
vnalpha/research_intelligence/shortlist.py
vnalpha/research_intelligence/shortlist_repo.py
vnalpha/commands/handlers/watchlist_summary.py
vnalpha/commands/handlers/shortlist.py
```

## Watchlist synthesis groups

MVP grouping dimensions:

```text
candidate class distribution
setup type distribution
sector clusters
high relative strength names
near confirmation names
extended names
risk-flagged names
low-data-quality names
```

## Shortlist scoring

Shortlist scoring should be deterministic and explainable.

Potential components:

```text
candidate_score
setup_quality
relative_strength_quality
sector_alignment
market_regime_fit
risk_penalty
extendedness_penalty
data_quality_penalty
```

## Commands

```text
/watchlist-summary [--date YYYY-MM-DD]
/shortlist [--date YYYY-MM-DD] [--limit N] [--setup SETUP] [--sector SECTOR]
```

## Assistant tools and intents

Tools:

```text
watchlist.summarize_deep
shortlist.generate
shortlist.get_candidate
```

Intents:

```text
summarize_watchlist_deep
generate_shortlist
explain_shortlist_candidate
```

## Output language

Use research agenda language:

```text
monitor
review
needs confirmation
risk to check
reason restrained
```

Do not use execution language:

```text
buy
sell
enter
exit
allocate
order
```
