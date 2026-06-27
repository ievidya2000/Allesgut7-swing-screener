import numpy as np
import pandas as pd
import warnings
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

from screener_v2.config import SL_MULTIPLIER, RR1, RR2, RR3, MC_N_SIM, MC_HORIZON


def calculate_tp_sl(close, atr, signal_type, custom_params=None):
    p = custom_params or {}
    sl_mult = p.get("sl_multiplier", SL_MULTIPLIER)
    rr1 = p.get("rr1", RR1)
    rr2 = p.get("rr2", RR2)
    rr3 = p.get("rr3", RR3)

    if signal_type in ("BUY", "STRONG BUY"):
        stop_loss = close - (atr * sl_mult)
        risk = close - stop_loss
        tp1 = close + (risk * rr1)
        tp2 = close + (risk * rr2)
        tp3 = close + (risk * rr3)

        if not (stop_loss < tp1 <= tp2 <= tp3):
            tp1 = round(close + risk * rr1, 2)
            tp2 = round(close + risk * rr2, 2)
            tp3 = round(close + risk * rr3, 2)

        profit_pct = ((tp1 - close) / close) * 100
        risk_pct = ((close - stop_loss) / close) * 100
    elif signal_type == "SELL":
        stop_loss = close + (atr * sl_mult)
        risk = stop_loss - close
        tp1 = close - (risk * rr1)
        tp2 = close - (risk * rr2)
        tp3 = close - (risk * rr3)
        profit_pct = ((close - tp1) / close) * 100
        risk_pct = ((stop_loss - close) / close) * 100
    else:
        return None, None, None, None, None, None

    return stop_loss, tp1, tp2, tp3, profit_pct, risk_pct


def simulate_tp_sl_probability(df, entry_price, stop_loss, tp1, tp2, tp3,
                               n_sim=MC_N_SIM, horizon=MC_HORIZON,
                               markov_cache=None, markov_cache_key=None):
    returns = np.log(df['Close'] / df['Close'].shift(1)).dropna()

    if len(returns) < 120 or returns.std() < 1e-6:
        return None

    cached_params = None
    if markov_cache is not None and markov_cache_key is not None:
        cached_params = markov_cache.get(markov_cache_key)

    if cached_params is not None:
        use_markov = cached_params["use_markov"]
        if use_markov:
            mu = cached_params["mu"]
            sigma = cached_params["sigma"]
            transition_matrix = cached_params["transition_matrix"]
    else:
        use_markov = True
        try:
            model = MarkovRegression(
                returns, k_regimes=2, trend='c', switching_variance=True
            )
            res = model.fit(disp=False, maxiter=15)

            mu = np.empty(2)
            sigma = np.empty(2)
            for r in range(2):
                const_key = next(k for k in res.params.index if k.startswith('const') and f'[{r}]' in k)
                sigma_key = next(k for k in res.params.index if k.startswith('sigma2') and f'[{r}]' in k)
                mu[r] = res.params[const_key]
                sigma[r] = np.sqrt(res.params[sigma_key])

            p_keys = [k for k in res.params.index if k.startswith('p[')]
            p00 = next(res.params[k] for k in p_keys if '0->0' in k or '0,0' in k)
            p10 = next(res.params[k] for k in p_keys if '1->0' in k or '1,0' in k)
            transition_matrix = np.array([[p00, 1 - p00], [p10, 1 - p10]])
        except Exception:
            use_markov = False

        if markov_cache is not None and markov_cache_key is not None:
            if use_markov:
                markov_cache[markov_cache_key] = {
                    "use_markov": True, "mu": mu, "sigma": sigma,
                    "transition_matrix": transition_matrix
                }
            else:
                markov_cache[markov_cache_key] = {"use_markov": False}

    if not use_markov:
        mu_val = returns.mean()
        sigma_val = returns.std()

    # Vectorized Monte Carlo simulation
    if use_markov:
        # Pre-generate all random numbers
        regime_returns = np.empty((n_sim, horizon))
        regime_rands = np.random.random((n_sim, horizon))
        init_rands = np.random.random(n_sim)

        # Vectorized regime initialization
        regimes = (init_rands >= 0.5).astype(int)

        # Vectorized simulation per time step
        for t in range(horizon):
            # Generate returns for current regime
            regime_returns[:, t] = np.random.normal(mu[regimes], sigma[regimes])
            # Vectorized regime transition
            trans_probs = transition_matrix[regimes, 0]
            regimes = (regime_rands[:, t] >= trans_probs).astype(int)

        cum_returns = np.cumsum(regime_returns, axis=1)
    else:
        rand_returns = np.random.normal(mu_val, sigma_val, (n_sim, horizon))
        cum_returns = np.cumsum(rand_returns, axis=1)

    prices = entry_price * np.exp(cum_returns)

    sl_hit_at = np.full(n_sim, horizon + 1, dtype=np.int32)
    tp1_hit_at = np.full(n_sim, horizon + 1, dtype=np.int32)
    tp2_hit_at = np.full(n_sim, horizon + 1, dtype=np.int32)
    tp3_hit_at = np.full(n_sim, horizon + 1, dtype=np.int32)

    for t in range(horizon):
        p = prices[:, t]
        not_sl = sl_hit_at > t
        if stop_loss:
            sl_hit = not_sl & (p <= stop_loss)
            sl_hit_at[sl_hit] = t + 1
        if tp1:
            tp1_hit = not_sl & (tp1_hit_at > t) & (p >= tp1)
            tp1_hit_at[tp1_hit] = t + 1
        if tp2:
            tp2_hit = not_sl & (tp2_hit_at > t) & (p >= tp2)
            tp2_hit_at[tp2_hit] = t + 1
        if tp3:
            tp3_hit = not_sl & (tp3_hit_at > t) & (p >= tp3)
            tp3_hit_at[tp3_hit] = t + 1

    hit_sl = int(np.sum(sl_hit_at <= horizon))
    hit_tp1 = int(np.sum(tp1_hit_at <= horizon))
    hit_tp2 = int(np.sum(tp2_hit_at <= horizon))
    hit_tp3 = int(np.sum(tp3_hit_at <= horizon))

    valid_tp1 = tp1_hit_at[tp1_hit_at <= horizon]
    valid_tp2 = tp2_hit_at[tp2_hit_at <= horizon]
    valid_tp3 = tp3_hit_at[tp3_hit_at <= horizon]

    return {
        "P_TP1": f"{(hit_tp1 / n_sim * 100):.2f}%" if tp1 else None,
        "P_TP2": f"{(hit_tp2 / n_sim * 100):.2f}%" if tp2 else None,
        "P_TP3": f"{(hit_tp3 / n_sim * 100):.2f}%" if tp3 else None,
        "P_SL": f"{(hit_sl / n_sim * 100):.2f}%" if stop_loss else None,
        "AVG_DAYS_TP1": float(np.mean(valid_tp1)) if len(valid_tp1) > 0 else None,
        "AVG_DAYS_TP2": float(np.mean(valid_tp2)) if len(valid_tp2) > 0 else None,
        "AVG_DAYS_TP3": float(np.mean(valid_tp3)) if len(valid_tp3) > 0 else None,
    }
