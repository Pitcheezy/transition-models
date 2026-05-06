# transition-models

Comparing transition probability models for SmartPitch MDP.

## Models

| | Model A (SmartPitch MLP) | Model B (Otremba 2022 MLP) | Model C (MIT Sloan 2025 Transformer) |
|---|---|---|---|
| **Input** | TBD | 77-dim feature vector | 87-dim × 400 sequence |
| **Output** | TBD | 4-dim (S/B/F/InPlay) | 24-dim (full state) |
| **Architecture** | Existing MLP (wrapper) | 2-layer, 128 units | 12-layer Encoder, sub-token masking |
| **Reference** | Internal | Otremba 2022 | MIT Sloan 2025 |

## Quick Start

```bash
# Install dependencies
uv sync

# Run sanity check
uv run python scripts/00_sanity_check.py

# Run tests
uv run pytest
```

## Project Structure

```
src/models/       Model definitions
src/data/         Datasets & feature engineering
src/training/     Training loops
src/evaluation/   Metrics & comparison
configs/          Experiment configs (YAML)
scripts/          Standalone scripts
notebooks/        Exploration
data/             Raw/processed data (git-ignored)
outputs/          Checkpoints, logs, figures (git-ignored)
references/       Papers
tests/            Tests
```
