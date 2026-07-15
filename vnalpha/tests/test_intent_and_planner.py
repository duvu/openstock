"""Intent/planner tests with strict-schema contract overrides."""

from tests._intent_and_planner_cases import *  # noqa: F403
from tests._intent_and_planner_cases import (
    TestIntentClassifier as _IntentClassifierCases,
)
from tests._intent_and_planner_cases import (
    _fake_response,
    _make_classifier,
)
from vnalpha.assistant.intent import INTENT_CLASSIFICATION_SCHEMA


class TestIntentClassifier(_IntentClassifierCases):
    def test_llm_classification_uses_json_schema(self):
        responses = [_fake_response("scan_candidates", 0.95)]
        classifier = _make_classifier(responses)
        result = classifier.classify("Show strongest candidates")

        assert result.intent == "scan_candidates"
        assert (
            classifier._client.call_metadata[0]["response_schema"]
            == INTENT_CLASSIFICATION_SCHEMA
        )

    def test_llm_classification_retry_keeps_json_schema(self):
        responses = [
            ("not valid json", {}),
            _fake_response("show_lineage", 0.9, entities={"symbol": "FPT"}),
        ]
        classifier = _make_classifier(responses)
        result = classifier.classify("Show me lineage for FPT")

        assert result.intent == "show_lineage"
        assert len(classifier._client.call_metadata) == 2
        assert (
            classifier._client.call_metadata[0]["response_schema"]
            == INTENT_CLASSIFICATION_SCHEMA
        )
        assert (
            classifier._client.call_metadata[1]["response_schema"]
            == INTENT_CLASSIFICATION_SCHEMA
        )
        assert classifier._client.call_metadata[1]["model_profile"] == "default"
        assert (
            classifier._client.call_metadata[1]["route_metadata"][
                "schema_repair_retry"
            ]
            is True
        )
