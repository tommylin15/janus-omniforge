"""Numeric-only Qlib challenger on Janus PIT arrays; no Qlib data downloads."""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from .model import DEnsembleModel


def fit(x, y, features):
    frame = pd.concat({"feature": pd.DataFrame(x, columns=features),
                       "label": pd.DataFrame({"excess_return": y})}, axis=1)
    # Fixed rounds, no tuning: the logged validation segment is training-only.
    dataset = SimpleNamespace(prepare=lambda *args, **kwargs: [frame, frame])
    model = DEnsembleModel(num_models=3, epochs=20, decay=1., num_threads=1,
                          seed=17, deterministic=True, force_col_wise=True, verbosity=-1,
                          max_depth=3, num_leaves=7)
    state = np.random.get_state()
    try:
        np.random.seed(17)
        model.fit(dataset)
    finally:
        np.random.set_state(state)
    return model


def predict_explained(model, values, features):
    contributions = np.zeros((len(values), len(features)))
    bases, predictions = np.zeros(len(values)), np.zeros(len(values))
    for booster, selected, weight in zip(model.ensemble, model.sub_features, model.sub_weights, strict=True):
        indices = [features.index(name) for name in selected]
        inputs = values[:, indices]
        explained = booster.predict(inputs, pred_contrib=True)
        contributions[:, indices] += explained[:, :-1] * weight
        bases += explained[:, -1] * weight
        predictions += booster.predict(inputs) * weight
    total = sum(model.sub_weights)
    return predictions / total, contributions / total, bases / total
