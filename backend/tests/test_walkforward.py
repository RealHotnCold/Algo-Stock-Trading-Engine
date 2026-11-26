import numpy as np
from app.walkforward import folds_for, sign_p, boot_ci, stitch

def test_fold_geometry():
    for n in (100002, 33335, 8334):
        W, starts = folds_for(n); assert len(starts) >= 5 and starts[0] == 0 and starts[-1] + W <= n
        assert all(b - a == starts[1] - starts[0] for a, b in zip(starts, starts[1:]))
        step = starts[1] - starts[0]; test_len = int(0.2 * (W - 96)) - 1      # approx size of the final-20% test window
        assert step >= test_len - 2                                               # consecutive test windows do not overlap

def test_sign_test_and_ci():
    assert abs(sign_p(5, 6) - 7 / 64) < 1e-12 and sign_p(0, 6) == 1.0
    x = np.random.default_rng(0).normal(5, 1, 200); lo, hi = boot_ci(x); assert lo < x.mean() < hi and hi - lo < 1

def test_stitch_compounds_and_drawdown():
    st, curve = stitch([np.array([0.1, 0.1]), np.array([-0.5])], cap=100.0)
    assert abs(st["total_return_pct"] - (100 * (1.1 * 1.1 * 0.5 - 1))) < 1e-9 and abs(st["max_dd_pct"] - 50) < 1e-9 and len(curve) == 300
