"""Demo: inference wrapper usage for DQN/MDP integration.

Runs Model B and Model C on random (but correctly shaped) inputs
to show the API before integrating real pitch sequences.

Usage:
    uv run python scripts/11_inference_demo.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inference import (
    HIT_LOCATION_CLASSES,
    PITCH_RESULT_CLASSES_10,
    TransitionModelB,
    TransitionModelC,
)


def _header(title: str) -> None:
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")


def demo_model_b() -> None:
    _header("Model B (Otremba MLP, 4-class)")

    ckpt = Path(TransitionModelB.DEFAULT_CHECKPOINT)
    if not ckpt.exists():
        print(f"[SKIP] Checkpoint not found: {ckpt}")
        return

    model = TransitionModelB()
    print(f"Device: {model.device}  |  Classes: {model.classes}")

    # --- Single prediction ---
    x_single = np.random.randn(77).astype(np.float32)
    probs = model.predict(x_single)
    print("\n[Single pitch prediction]")
    for cls, p in zip(model.classes, probs):
        bar = "#" * int(p * 30)
        print(f"  {cls:<8} {p:.4f}  {bar}")

    # --- Top-k ---
    top3 = model.predict_top_k(x_single, k=3)
    print("\n[Top-3 predictions]")
    for rank, item in enumerate(top3, 1):
        print(f"  #{rank}  {item['class']:<8}  {item['probability']:.4f}")

    # --- Batch prediction ---
    batch = np.random.randn(8, 77).astype(np.float32)
    batch_probs = model.predict(batch)
    print(f"\n[Batch prediction]  input: {batch.shape}  ->  output: {batch_probs.shape}")
    print(f"  Row sums (should all be 1.0): {batch_probs.sum(axis=1).round(4)}")


def demo_model_c() -> None:
    _header("Model C (MIT Sloan Transformer, 10-class)")

    ckpt = Path(TransitionModelC.DEFAULT_CHECKPOINT)
    if not ckpt.exists():
        print(f"[SKIP] Checkpoint not found: {ckpt}")
        return

    model = TransitionModelC()
    print(f"Device: {model.device}")
    print(f"PR classes : {model.pr_classes}")
    print(f"HL classes : {model.hl_classes}")

    # Build a valid sequence: random + sub-token mask
    seq = np.random.randn(400, 87).astype(np.float32)
    seq[-1, 68:87] = 0.0  # sub-token mask (반드시!)

    result = model.predict(seq)
    pr_probs = result["pitch_result"]
    hl_probs = result["hit_location"]

    print("\n[Pitch Result probabilities]")
    for cls, p in zip(model.pr_classes, pr_probs):
        bar = "#" * int(p * 40)
        print(f"  {cls:<12} {p:.4f}  {bar}")

    print("\n[Hit Location probabilities  (InPlay 한정)]")
    for cls, p in zip(model.hl_classes, hl_probs):
        bar = "#" * int(p * 40)
        print(f"  {cls:<18} {p:.4f}  {bar}")

    # Top-3
    top3 = model.predict_top_k(seq, k=3)
    print("\n[Top-3 Pitch Result predictions]")
    for rank, item in enumerate(top3, 1):
        print(f"  #{rank}  {item['class']:<12}  {item['probability']:.4f}")

    # Batch
    batch = np.random.randn(4, 400, 87).astype(np.float32)
    batch[:, -1, 68:87] = 0.0
    batch_result = model.predict(batch)
    print(f"\n[Batch prediction]  input: {batch.shape}")
    print(f"  pitch_result shape: {batch_result['pitch_result'].shape}")
    print(f"  hit_location shape: {batch_result['hit_location'].shape}")


def demo_dqn_pattern() -> None:
    """DQN 환경 통합 예시 패턴."""
    _header("DQN 환경 통합 패턴 (예시)")

    ckpt = Path(TransitionModelC.DEFAULT_CHECKPOINT)
    if not ckpt.exists():
        print(f"[SKIP] Checkpoint not found: {ckpt}")
        return

    model = TransitionModelC()

    class _FakeEnv:
        """SmartPitch MDP 환경 통합 패턴 데모."""

        def __init__(self, transition_model: TransitionModelC):
            self.model = transition_model
            self.step_count = 0

        def step(self, action: int) -> tuple:
            # 실제 환경에서는 action으로 새 pitch feature를 만들어야 함
            sequence = np.random.randn(400, 87).astype(np.float32)
            sequence[-1, 68:87] = 0.0  # sub-token mask

            result = self.model.predict(sequence)
            probs = result["pitch_result"]

            # 확률에 따라 outcome sampling
            outcome_idx = np.random.choice(len(PITCH_RESULT_CLASSES_10), p=probs)
            outcome = PITCH_RESULT_CLASSES_10[outcome_idx]

            reward = {"HomeRun": 4, "Triple": 3, "Double": 2, "Single": 1}.get(outcome, 0)
            self.step_count += 1
            done = self.step_count >= 3

            return outcome, reward, done

    env = _FakeEnv(model)
    print("\n[3-step simulation]")
    for step in range(3):
        action = np.random.randint(0, 4)
        outcome, reward, done = env.step(action)
        print(f"  Step {step + 1}:  action={action}  outcome={outcome:<12}  reward={reward}")
    print("\n완료  DQN 팀은 _FakeEnv.step()을 실제 pitch 생성 로직으로 교체하면 됩니다.")


def main() -> None:
    _header("SmartPitch Transition Model Inference Demo")
    demo_model_b()
    demo_model_c()
    demo_dqn_pattern()
    print("\n" + "=" * 55)
    print("  Demo 완료")
    print("=" * 55)


if __name__ == "__main__":
    main()
