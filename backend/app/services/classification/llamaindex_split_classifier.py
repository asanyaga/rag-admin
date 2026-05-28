from app.cdm.models import ParsedDocument
from app.services.classification.port import ClassificationResult


class LlamaIndexSplitClassifier:
    def __init__(self, classifier_config: dict) -> None:
        self.classifier_config = classifier_config

    async def classify(
        self, doc: ParsedDocument, labels: list[str]
    ) -> ClassificationResult:
        raise NotImplementedError(
            "LlamaIndexSplitClassifier is not yet implemented. "
            "Select classifier_type='llm' to use the LLM-based classifier."
        )
