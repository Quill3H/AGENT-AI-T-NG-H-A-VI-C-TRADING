"""
src/research/ml/models.py
=========================
The pre-registered model families (design §4/§7): L2 logistic regression, shallow gradient-boosted
trees and their average. Each fit happens inside one training window: hyperparameters, the
isotonic calibration map (model_governance.fit_isotonic) and the dissimilarity threshold are all
chosen on that window's calibration tail, never on test data.

Abstention rules (no trade on that sample):
- dissimilarity index (FreqAI DI_threshold idea): nearest-neighbour distance to the fit set,
  divided by the fit set's own mean nearest-neighbour distance, above the 99th percentile seen
  on the calibration tail;
- blend only: |p_logistic - p_trees| > 0.15.
The blend counts as one configuration in the K = 24 trial budget.
"""
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.neighbors import NearestNeighbors

from src.research.model_governance import fit_isotonic

FAMILIES = ("logistic", "trees", "blend")
DISAGREEMENT_MAX = 0.15
DI_QUANTILE = 0.99


@dataclass(frozen=True)
class ModelSpec:
    family: str = "logistic"
    use_di: bool = False
    seed: int = 0

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}")


def _standardise(x_fit, *others):
    mu, sd = x_fit.mean(axis=0), x_fit.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return [(x - mu) / sd for x in (x_fit, *others)]


def _fit_logistic(x, y, w, x_cal, y_cal):
    best = None
    for c in (0.01, 0.1, 1.0):
        m = LogisticRegression(C=c, max_iter=2000).fit(x, y, sample_weight=w)
        loss = log_loss(y_cal, m.predict_proba(x_cal)[:, 1], labels=[0, 1])
        if best is None or loss < best[0]:
            best = (loss, m)
    return best[1]


def _fit_trees(x, y, w, x_cal, y_cal, seed):
    best = None
    for lr in (0.03, 0.1):
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=lr, l2_regularization=1.0,
                                           early_stopping=False, random_state=seed).fit(x, y, sample_weight=w)
        loss = log_loss(y_cal, m.predict_proba(x_cal)[:, 1], labels=[0, 1])
        if best is None or loss < best[0]:
            best = (loss, m)
    return best[1]


def dissimilarity(x_fit, x_query, rng, max_ref=5000):
    """DI of each query row against (a sample of) the fit set, in standardised feature space."""
    ref = x_fit if len(x_fit) <= max_ref else x_fit[rng.choice(len(x_fit), max_ref, replace=False)]
    nn = NearestNeighbors(n_neighbors=2).fit(ref)
    own = nn.kneighbors(ref)[0][:, 1].mean()
    dist = nn.kneighbors(x_query, n_neighbors=1)[0][:, 0]
    return dist / max(own, 1e-12)


def fit_predict(spec, x_fit, y_fit, w_fit, x_cal, y_cal, x_test):
    """(calibrated probability, raw score, abstain mask) for the test rows of one training window.
    Isotonic maps are step functions, so ranking (the long/short book) uses the raw score and
    thresholds/calibration metrics use the calibrated probability."""
    if len(np.unique(y_fit)) < 2 or len(np.unique(y_cal)) < 2:
        raise ValueError("fit and calibration slices need both classes")
    xs_fit, xs_cal, xs_test = _standardise(np.asarray(x_fit, float), np.asarray(x_cal, float), np.asarray(x_test, float))
    raw_cal, raw_test = [], []
    if spec.family in ("logistic", "blend"):
        m = _fit_logistic(xs_fit, y_fit, w_fit, xs_cal, y_cal)
        raw_cal.append(m.predict_proba(xs_cal)[:, 1])
        raw_test.append(m.predict_proba(xs_test)[:, 1])
    if spec.family in ("trees", "blend"):
        m = _fit_trees(xs_fit, y_fit, w_fit, xs_cal, y_cal, spec.seed)
        raw_cal.append(m.predict_proba(xs_cal)[:, 1])
        raw_test.append(m.predict_proba(xs_test)[:, 1])
    cal_test = [fit_isotonic(rc, y_cal)(rt) for rc, rt in zip(raw_cal, raw_test)]
    p, score = np.mean(cal_test, axis=0), np.mean(raw_test, axis=0)
    abstain = np.zeros(len(p), dtype=bool)
    if spec.family == "blend":
        abstain |= np.abs(cal_test[0] - cal_test[1]) > DISAGREEMENT_MAX
    if spec.use_di:
        rng = np.random.default_rng(spec.seed)
        threshold = np.quantile(dissimilarity(xs_fit, xs_cal, rng), DI_QUANTILE)
        abstain |= dissimilarity(xs_fit, xs_test, rng) > threshold
    return p, score, abstain
