from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import TimeSeriesSplit

from fair3.engine.utils.rand import generator_from_seed

__all__ = ["MuBlend", "estimate_mu_ensemble"]


@dataclass(frozen=True)
class MuBlend:
    mu_post: pd.Series
    mu_star: pd.Series
    mu_eq: pd.Series
    omega: float
    reason: str  # "fallback" | "blend"


def _lag_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    lagged = frame.shift(1)
    return lagged.fillna(0.0)


def _prepare_feature_matrix(returns: pd.DataFrame, macro: pd.DataFrame | None) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    lagged_returns = _lag_features(returns)
    if not lagged_returns.empty:
        pieces.append(lagged_returns.add_suffix("_lag1"))

    if macro is not None and not macro.empty:
        macro_aligned = macro.reindex(returns.index).ffill().bfill().fillna(0.0)
        pieces.append(_lag_features(macro_aligned))

    if not pieces:
        return pd.DataFrame(np.zeros((len(returns), 1)), index=returns.index, columns=["bias"])

    features = pd.concat(pieces, axis=1)
    return features.replace([np.inf, -np.inf], 0.0).fillna(0.0)


def _bagging_linear_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_eval: np.ndarray,
    rng: np.random.Generator,
    n_bags: int = 8,
    sample_frac: float = 0.8,
) -> np.ndarray:
    if x_train.size == 0 or y_train.size == 0:
        return np.zeros(x_eval.shape[0])
    preds = np.zeros(x_eval.shape[0])
    n_samples = y_train.shape[0]
    draw_size = max(1, int(sample_frac * n_samples))
    for _ in range(n_bags):
        idx = rng.choice(n_samples, size=draw_size, replace=True)
        model = LinearRegression()
        model.fit(x_train[idx], y_train[idx])
        preds += model.predict(x_eval)
    return preds / float(n_bags)


def _gbt_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_eval: np.ndarray,
    seed: int,
) -> np.ndarray:
    if x_train.size == 0 or y_train.size == 0:
        return np.zeros(x_eval.shape[0])
    model = GradientBoostingRegressor(
        random_state=seed,
        n_estimators=200,
        learning_rate=0.05,
        max_depth=2,
        subsample=0.7,
        min_samples_leaf=5,
        validation_fraction=0.2,
        n_iter_no_change=5,
    )
    model.fit(x_train, y_train)
    return model.predict(x_eval)


def _stack_weights(
    base_preds: Iterable[np.ndarray],
    target: np.ndarray,
) -> np.ndarray:
    matrix = np.column_stack([np.asarray(pred) for pred in base_preds])
    if matrix.size == 0 or target.size == 0:
        n_cols = matrix.shape[1] if matrix.ndim > 1 else 1
        return np.full(n_cols, 1.0 / max(n_cols, 1))
    ridge = Ridge(alpha=1.0, fit_intercept=False, positive=True)
    ridge.fit(matrix, target)
    weights = ridge.coef_
    weight_sum = float(weights.sum())
    if weight_sum <= 1e-12:
        return np.full_like(weights, 1.0 / len(weights))
    return weights / weight_sum


def estimate_mu_ensemble(
    returns_frame: pd.DataFrame,
    macro: pd.DataFrame,
    cv_splits: int,
    seed: int,
) -> pd.Series:
    if returns_frame.empty:
        raise ValueError("Returns frame cannot be empty")
    returns = returns_frame.dropna(how="all")
    if returns.empty:
        raise ValueError("Returns frame contains only NaNs")

    features = _prepare_feature_matrix(returns, macro)
    feature_matrix = features.to_numpy(dtype=float, copy=True)
    sample_means = returns.mean()
    shrink_intensity = min(1.0, returns.shape[1] / max(returns.shape[0], 1))
    mu_shrink = (1.0 - shrink_intensity) * sample_means

    rng_global = generator_from_seed(seed, stream="mu-ensemble")
    mu_values: dict[str, float] = {}

    for asset in returns.columns:
        asset_returns = returns[asset].to_numpy(dtype=float)
        n_obs = asset_returns.shape[0]
        if n_obs < 5:
            mu_values[asset] = mu_shrink.loc[asset]
            continue

        asset_rng = np.random.default_rng(rng_global.integers(0, 2**32 - 1))
        tscv_splits = min(cv_splits, n_obs - 1)
        bagging_cv: list[np.ndarray] = []
        gbt_cv: list[np.ndarray] = []
        mean_cv: list[np.ndarray] = []
        target_cv: list[np.ndarray] = []
        if tscv_splits >= 2:
            splitter = TimeSeriesSplit(n_splits=tscv_splits)
            for train_idx, test_idx in splitter.split(feature_matrix):
                x_train, x_test = feature_matrix[train_idx], feature_matrix[test_idx]
                y_train, y_test = asset_returns[train_idx], asset_returns[test_idx]
                bagging_rng = np.random.default_rng(asset_rng.integers(0, 2**32 - 1))
                gbt_seed = int(asset_rng.integers(0, 2**31 - 1))
                bagging_cv.append(_bagging_linear_predict(x_train, y_train, x_test, bagging_rng))
                gbt_cv.append(_gbt_predict(x_train, y_train, x_test, gbt_seed))
                mean_cv.append(np.full_like(y_test, y_train.mean(), dtype=float))
                target_cv.append(y_test)

        if target_cv:
            stacked_weights = _stack_weights(
                [np.concatenate(mean_cv), np.concatenate(bagging_cv), np.concatenate(gbt_cv)],
                np.concatenate(target_cv),
            )
        else:
            stacked_weights = np.array([1.0, 0.0, 0.0])

        bagging_rng_final = np.random.default_rng(asset_rng.integers(0, 2**32 - 1))
        gbt_seed_final = int(asset_rng.integers(0, 2**31 - 1))
        bagging_next = _bagging_linear_predict(
            feature_matrix, asset_returns, feature_matrix[-1:], bagging_rng_final
        )[0]
        gbt_next = _gbt_predict(feature_matrix, asset_returns, feature_matrix[-1:], gbt_seed_final)[
            0
        ]
        base_next = np.array([mu_shrink.loc[asset], bagging_next, gbt_next], dtype=float)
        mu_values[asset] = float(np.dot(stacked_weights, base_next))

    return pd.Series(mu_values).reindex(returns.columns)
