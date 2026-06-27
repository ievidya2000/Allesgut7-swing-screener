"""TabNet configuration presets for different regularization levels."""

TABNET_CONFIGS = {
    "baseline": {
        "n_d": 16,
        "n_a": 16,
        "n_steps": 5,
        "gamma": 1.5,
        "lambda_sparse": 1e-4,
        "optimizer_params": {"lr": 0.02},
        "scheduler_params": {"step_size": 10, "gamma": 0.9},
        "mask_type": "entmax",
    },
    "regularized_v1": {
        "n_d": 8,
        "n_a": 8,
        "n_steps": 3,
        "gamma": 1.5,
        "lambda_sparse": 1e-3,
        "optimizer_params": {"lr": 0.01},
        "scheduler_params": {"step_size": 5, "gamma": 0.8},
        "mask_type": "entmax",
    },
    "regularized_v2": {
        "n_d": 16,
        "n_a": 16,
        "n_steps": 3,
        "gamma": 2.0,
        "lambda_sparse": 5e-3,
        "optimizer_params": {"lr": 0.01},
        "scheduler_params": {"step_size": 5, "gamma": 0.8},
        "mask_type": "sparsemax",
    },
}
