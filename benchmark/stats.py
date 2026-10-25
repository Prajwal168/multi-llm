"""Confidence intervals and paired tests (paper Section V, 'seventh')."""

import math

import numpy as np


def bootstrap_ci(x, n=5000, alpha=0.05, seed=0):
    """Percentile bootstrap CI of the mean. Returns (mean, lo, hi)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (n, len(x)))
    boots = x[idx].mean(axis=1)
    return float(x.mean()), float(np.quantile(boots, alpha / 2)), float(np.quantile(boots, 1 - alpha / 2))


def bootstrap_ratio_ci(num, den, n=5000, alpha=0.05, seed=0):
    """Pooled ratio sum(num)/sum(den), resampling clusters (e.g. tasks)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    if len(num) == 0 or den.sum() == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), (n, len(num)))
    d = den[idx].sum(axis=1)
    ok = d > 0
    boots = num[idx].sum(axis=1)[ok] / d[ok]
    return float(num.sum() / den.sum()), float(np.quantile(boots, alpha / 2)), float(np.quantile(boots, 1 - alpha / 2))


def mcnemar_exact(x, y):
    """Exact McNemar on paired binary outcomes. Returns (b, c, p)."""
    x, y = np.asarray(x, int), np.asarray(y, int)
    b = int(((x == 1) & (y == 0)).sum())
    c = int(((x == 0) & (y == 1)).sum())
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return b, c, min(1.0, p)


def wilcoxon_paired(x, y):
    """Wilcoxon signed-rank on paired continuous values. Returns (n_pairs, p)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    d = (x - y)[ok]
    if len(d) == 0 or np.all(d == 0):
        return int(ok.sum()), 1.0
    from scipy.stats import wilcoxon
    return int(ok.sum()), float(wilcoxon(d).pvalue)
