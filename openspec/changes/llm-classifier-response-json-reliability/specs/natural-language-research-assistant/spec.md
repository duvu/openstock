## MODIFIED Requirements

### Requirement: Assistant shall classify supported research intents

The assistant SHALL classify user prompts into one of the supported intent families:

```text
scan_candidates
filter_candidates
compare_symbols
explain_symbol
review_quality
show_lineage
summarize_watchlist
create_research_note
show_history
unsupported_or_unsafe
```

The classifier SHALL return:

```text
intent
confidence
entities
needs_clarification
clarification_question
safety_flags
```

Classifier responses SHALL be parsed through a shared JSON parser utility that attempts all supported extraction strategies (markdown fence strip, embedded JSON extraction, strict json.loads).  
If the parser still cannot produce a valid payload, it SHALL return a clear invalid-response error and this classification path SHALL retry once with stronger model profile settings.  
If the second attempt also fails to parse, the assistant SHALL surface a classifier failure and SHALL NOT continue to planner or synthesis.

#### Scenario: Classify explain intent

- **GIVEN** the prompt `Why is FPT in the watchlist today?`
- **WHEN** the classifier runs
- **THEN** it SHALL classify the prompt as `explain_symbol`
- **AND** it SHALL extract symbol `FPT`

#### Scenario: Classify compare intent

- **GIVEN** the prompt `Compare FPT, VNM, and MWG`
- **WHEN** the classifier runs
- **THEN** it SHALL classify the prompt as `compare_symbols`
- **AND** it SHALL extract symbols `FPT`, `VNM`, and `MWG`

#### Scenario: Classify unsafe intent

- **GIVEN** the prompt `Buy FPT for me now`
- **WHEN** safety precheck or classifier runs
- **THEN** it SHALL classify the prompt as `unsupported_or_unsafe`
- **AND** the assistant SHALL refuse the request

#### Scenario: Recover parser from malformed but recoverable classifier JSON

- **GIVEN** the first classifier response is not clean JSON but contains a JSON object in text
- **WHEN** the parser runs
- **THEN** it SHALL extract and parse the JSON object and continue classification if valid

#### Scenario: Retry when classifier JSON is invalid

- **GIVEN** the first classifier response is not parseable as JSON
- **WHEN** classifier parse fails
- **THEN** the assistant SHALL retry classification once with stronger profile settings
- **AND** if the second response still fails to parse
- **THEN** it SHALL return an explicit invalid-response classifier error
- **AND** no plan SHALL be executed for that turn
