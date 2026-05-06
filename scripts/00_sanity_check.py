"""Sanity check: verify PyTorch install and MPS availability."""

import sys

import torch


def main():
    print(f"Python: {sys.version}")
    print(f"PyTorch: {torch.__version__}")
    print()

    # CPU 텐서 연산
    a = torch.randn(3, 3)
    b = torch.randn(3, 3)
    c = a @ b
    print(f"[CPU] matmul result shape: {c.shape}, dtype: {c.dtype}")
    print(f"[CPU] sample value: {c[0, 0].item():.4f}")
    print()

    # MPS 가용성 확인
    mps_built = torch.backends.mps.is_built()
    mps_available = torch.backends.mps.is_available()
    print(f"MPS built: {mps_built}")
    print(f"MPS available: {mps_available}")

    if mps_available:
        device = torch.device("mps")
        a_mps = a.to(device)
        b_mps = b.to(device)
        c_mps = a_mps @ b_mps
        print(f"[MPS] matmul result shape: {c_mps.shape}, device: {c_mps.device}")
        print(f"[MPS] sample value: {c_mps[0, 0].item():.4f}")

        # CPU 결과와 비교
        diff = (c - c_mps.cpu()).abs().max().item()
        print(f"[MPS] max diff vs CPU: {diff:.2e}")
    else:
        print("MPS not available — skipping MPS test")

    print()
    print("Sanity check passed!")


if __name__ == "__main__":
    main()
