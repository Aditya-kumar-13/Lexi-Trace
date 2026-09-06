# Local semantic model

LexiTrace uses `BAAI/bge-small-en-v1.5` through Qdrant FastEmbed when semantic context is enabled.
FastEmbed executes the model through ONNX Runtime; no transcript is sent to a hosted inference API.
The model is downloaded once and cached in the configured local model directory.

- FastEmbed documentation: https://qdrant.github.io/fastembed/Getting%20Started/
- Model card: https://huggingface.co/BAAI/bge-small-en-v1.5
- Model license: MIT
- FastEmbed license: Apache-2.0

## Data flow

Before encoding, LexiTrace replaces the candidate word span with `[TERM]`. This reduces the chance
that the remembered spelling itself dominates context similarity. Only the resulting vector,
masked context, model name, observation reference, and evidence polarity are stored.

## Operational behavior

- Model loading is lazy, so health and deterministic endpoints do not wait for model download.
- If the model cannot load, sparse context and explicit blockers remain active.
- The inference trace reports encoder state, model name, sparse similarity, semantic similarity,
  prototype margin, and observation counts.
- Model cache files are excluded from Git and persisted in the Docker data volume.

## Known limitation

The current semantic similarity floor is a transparent policy value validated on the included
development journeys. It is not yet probability-calibrated on a large held-out corpus. That work is
part of the calibration milestone and must precede production accuracy claims.
