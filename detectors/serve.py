# detectors/serve.py
# Thin FastAPI sidecar for SetFit detector models.
# The daemon calls this when it needs deep detection (grey/black state,
# every Nth turn, or on demand).
#
# This is a bridge. The TS daemon handles the hot path.
# Python handles the ML models.

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# TODO: import trained SetFit models once they exist
# from setfit import SetFitModel

app = FastAPI(title="keanu detectors", version="0.0.1")


class DetectRequest(BaseModel):
    text: str
    detectors: list[str] | None = None  # None = run all


class DetectorResult(BaseModel):
    name: str
    score: float  # 0-1
    label: str  # "detected" | "clean"
    confidence: float


class DetectResponse(BaseModel):
    results: list[DetectorResult]


# The 14 detectors from keanu's training data
DETECTOR_NAMES = [
    "sycophancy",
    "capture",
    "generalization",
    "zero_sum",
    "safety_theater",
    "inconsistency",
    "grievance",
    "stability",
    "false_urgency",
    "emotional_exploitation",
    "gaslighting",
    "manufactured_consensus",
    "info_withholding",
    "manipulation",
]

# Placeholder: will be replaced with trained SetFit models
# models = {name: SetFitModel.from_pretrained(f"models/{name}") for name in DETECTOR_NAMES}


@app.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest):
    """Run detectors on text. Returns scores for each detector."""
    targets = req.detectors or DETECTOR_NAMES
    results = []

    for name in targets:
        if name not in DETECTOR_NAMES:
            continue

        # TODO: replace with actual model inference
        # prediction = models[name].predict([req.text])
        # score = prediction[0]

        # Placeholder: return 0.0 for all detectors until models are trained
        results.append(
            DetectorResult(
                name=name,
                score=0.0,
                label="clean",
                confidence=0.0,
            )
        )

    return DetectResponse(results=results)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "detectors": len(DETECTOR_NAMES),
        "models_loaded": 0,  # TODO: count loaded models
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787)
