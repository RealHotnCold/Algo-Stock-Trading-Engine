"""Double DQN in NumPy (PyTorch not installable in the build sandbox; swap MLP for nn.Module if desired).
Actions = target position {0:short, 1:flat, 2:long}. Market is unaffected by our actions, so reward for ANY (state, action)
is computable offline: r = new_pos * next_return - cost*|new_pos - prev_pos|."""
import copy, numpy as np

class MLP:
    def __init__(s, sizes, seed=0):
        r = np.random.default_rng(seed)
        s.W = [r.normal(0, np.sqrt(2 / a), (a, b)) for a, b in zip(sizes, sizes[1:])]; s.b = [np.zeros(b) for b in sizes[1:]]
        s.m = [np.zeros_like(p) for p in s.W + s.b]; s.v = [np.zeros_like(p) for p in s.W + s.b]; s.t = 0
    def fwd(s, x):
        hs = [x]
        for i, (W, b) in enumerate(zip(s.W, s.b)):
            x = x @ W + b
            if i < len(s.W) - 1: x = np.maximum(x, 0)
            hs.append(x)
        return x, hs
    def update(s, hs, g, lr):
        gW, gb = [], []
        for i in reversed(range(len(s.W))):
            gW.insert(0, hs[i].T @ g); gb.insert(0, g.sum(0))
            if i > 0: g = (g @ s.W[i].T) * (hs[i] > 0)
        s.t += 1
        for k, (p, gr) in enumerate(zip(s.W + s.b, gW + gb)):
            s.m[k] = .9 * s.m[k] + .1 * gr; s.v[k] = .999 * s.v[k] + .001 * gr * gr
            p -= lr * (s.m[k] / (1 - .9 ** s.t)) / (np.sqrt(s.v[k] / (1 - .999 ** s.t)) + 1e-8)
    def q(s, x): return s.fwd(x)[0]

def simulate(net, B, r, lo, hi, cost):
    """Run greedy policy sequentially over bars [lo,hi). Returns per-bar net reward and positions."""
    pos, out, ps = 0, np.zeros(hi - lo), np.zeros(hi - lo)
    for i, t in enumerate(range(lo, hi)):
        npos = int(net.q(np.append(B[t], pos)[None])[0].argmax()) - 1
        out[i] = npos * r[t] - cost * abs(npos - pos); ps[i] = npos; pos = npos
    return out, ps

def train(B, r, idx, cost, val_range, steps=3000, hidden=32, gamma=0.9, lr=1e-3, batch=128, eval_every=500, seed=0):
    rng = np.random.default_rng(seed); net = MLP([B.shape[1] + 1, hidden, hidden, 3], seed); tgt = copy.deepcopy(net)
    best, best_net, hist = -1e18, copy.deepcopy(net), []; n = np.arange(batch)
    for step in range(1, steps + 1):
        t = rng.choice(idx, batch); pp = rng.integers(-1, 2, batch); a = rng.integers(0, 3, batch); npos = a - 1
        x, x2 = np.c_[B[t], pp], np.c_[B[t + 1], npos]
        rew = npos * r[t] - cost * np.abs(npos - pp)
        an = net.q(x2).argmax(1); y = rew + gamma * tgt.q(x2)[n, an]
        q, hs = net.fwd(x); g = np.zeros_like(q); g[n, a] = np.clip(q[n, a] - y, -5, 5) * 2 / batch
        net.update(hs, g, lr)
        if step % 200 == 0: tgt = copy.deepcopy(net)
        if step % eval_every == 0:      # early stopping on VALIDATION net reward (mean bps/bar)
            sc = simulate(net, B, r, *val_range, cost)[0].mean(); hist.append(float(sc))
            if sc > best: best, best_net = sc, copy.deepcopy(net)
    return best_net, hist
