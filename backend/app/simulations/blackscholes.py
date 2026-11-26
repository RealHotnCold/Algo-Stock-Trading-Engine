"""Black-Scholes(-Merton / Garman-Kohlhagen with yield q). Theoretical values from user-supplied parameters."""
import math
import numpy as np
_N = np.vectorize(lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2))))
_n = lambda x: np.exp(-0.5 * np.asarray(x) ** 2) / math.sqrt(2 * math.pi)

def bs(S, K, T, r, sigma, kind="call", q=0.0):
    S, K, T, sigma = (np.asarray(v, float) for v in (S, K, T, sigma))
    st = sigma * np.sqrt(T); d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / st; d2 = d1 - st
    eq, er = np.exp(-q * T), np.exp(-r * T); call = kind == "call"
    price = S * eq * _N(d1) - K * er * _N(d2) if call else K * er * _N(-d2) - S * eq * _N(-d1)
    delta = eq * _N(d1) if call else eq * (_N(d1) - 1)
    gamma = eq * _n(d1) / (S * st); vega = S * eq * _n(d1) * np.sqrt(T)
    common = -S * eq * _n(d1) * sigma / (2 * np.sqrt(T))
    theta = common - r * K * er * _N(d2) + q * S * eq * _N(d1) if call else common + r * K * er * _N(-d2) - q * S * eq * _N(-d1)
    rho = K * T * er * _N(d2) if call else -K * T * er * _N(-d2)
    return dict(price=price, delta=delta, gamma=gamma, vega=vega / 100, theta=theta / 365, rho=rho / 100)  # vega per 1 vol pt, theta per day, rho per 1% rate
