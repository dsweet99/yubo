import torch
from botorch.acquisition import PosteriorMean
from botorch.models import SingleTaskGP
from botorch.optim import optimize_acqf

import acq.fit_gp as fit_gp


class AcqBT:
    def __init__(self, acq_factory, data, num_dim, acq_kwargs=None):
        dtype = torch.float64
        if len(data) == 0:
            X = torch.empty(size=(0, num_dim), dtype=dtype)
            Y = torch.empty(size=(0, 1), dtype=dtype)
            gp = SingleTaskGP(X, Y)
            gp.eval()
        else:
            gp, Y, X = fit_gp.fit_gp(data, dtype)

        # All BoTorch stuff is coded to bounds of [0,1]!
        self.bounds = torch.tensor([[0.0] * num_dim, [1.0] * num_dim], device=X.device, dtype=X.dtype)

        if not acq_kwargs:
            kwargs = {}
        else:
            kwargs = dict(acq_kwargs)
        if "X_max" in kwargs:
            kwargs["X_max"] = self._find_max(gp, self.bounds)
        if "best_f" in kwargs:
            kwargs["best_f"] = gp(self._find_max(gp, self.bounds)).mean
        if "X_baseline" in kwargs:
            kwargs["X_baseline"] = X
        if "candidate_set" in kwargs:
            kwargs["candidate_set"] = torch.rand(1000, num_dim)
        if "Y_max" in kwargs:
            kwargs["Y_max"] = gp(self._find_max(gp, self.bounds)).mean
        if "bounds" in kwargs:
            kwargs["bounds"] = self.bounds

        self.acq_function = acq_factory(gp, **kwargs)

    def _find_max(self, gp, bounds):
        x_cand, _ = optimize_acqf(
            acq_function=PosteriorMean(model=gp),
            bounds=bounds,
            q=1,
            num_restarts=10,
            raw_samples=512,
            options={"batch_limit": 10, "maxiter": 200},
        )
        return x_cand

    def __call__(self, policy):
        X = torch.atleast_2d(fit_gp.mk_x(policy)).unsqueeze(0)
        return self.acq_function(X).squeeze().item()
