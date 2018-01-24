# -*- coding: utf-8 -*-

r"""
The :mod:`pygsp.learning` module implements functions to solve learning
problems.

Semi-supervized learning
========================

Those functions help to solve a semi-supervized learning problem, i.e. a
problem where only some values of a graph signal are known and the others shall
be inferred.

.. autosummary::

    regression_tik
    classification_tik

"""

import numpy as np
import scipy


def classification_tik(G, y, M, tau=0):
    r"""Solve a classification problem on graph via Tikhonov minimization.

    The function first transform :math:`y` in logits :math:`Y`. It then solves

    .. math:: \operatorname*{arg min}_X \| M X - Y \|_2^2 + \tau \ tr(X^T L X)

    if :math:`\tau > 0` and

    .. math:: \operatorname*{arg min}_X tr(X^T L X) \ \text{ s. t. } \ Y = M X

    otherwise, where :math:`X` and :math:`Y` are logits. The function return
    the maximum of the logits.

    Parameters
    ----------
    G : Graph
    y : array of length G.N
        Measurements
    M : array of boolean, length G.N
        Masking vector.
    tau : float
        Regularization parameter.

    Examples
    --------
    >>> from pygsp import graphs, learning
    >>> import matplotlib.pyplot as plt
    >>>
    >>> G = graphs.Logo()

    Create a ground truth signal:

    >>> signal = np.zeros(G.N)
    >>> signal[G.info['idx_s']] = 1
    >>> signal[G.info['idx_p']] = 2

    Construct a measurements signal from a binary mask:

    >>> rs = np.random.RandomState(42)
    >>> mask = rs.uniform(0, 1, G.N) > 0.5
    >>> measurements = signal.copy()
    >>> measurements[~mask] = np.nan

    Solve the classification problem by reconstructing the signal:

    >>> recovery = learning.classification_tik(G, measurements, mask, tau=0)

    Plot the results:

    >>> fig, (ax1, ax2, ax3) = plt.subplots(1, 3, sharey=True, figsize=(10, 3))
    >>> G.plot_signal(signal, plot_name='Ground truth', ax=ax1)
    >>> G.plot_signal(measurements, plot_name='Measurements', ax=ax2)
    >>> G.plot_signal(recovery, plot_name='Recovery', ax=ax3)
    >>> fig.tight_layout()

    """

    def to_logits(x):
        l = np.zeros([len(x), np.max(x)+1])
        l[range(len(x)), x] = 1
        return l
    y[M == False] = 0
    Y = to_logits(y.astype(np.int))
    X = regression_tik(G, Y, M, tau)

    return np.argmax(X, axis=1)


def regression_tik(G, y, M, tau=0):
    r"""Solve a regression problem on graph via Tikhonov minimization.

    If :math:`\tau > 0`:

    .. math:: \operatorname*{arg min}_x \| M x - y \|_2^2 + \tau \ x^T L x

    else:

    .. math:: \operatorname*{arg min}_x x^T L x \ \text{ s. t. } \ y = M x

    Parameters
    ----------
    G : Graph
    y : array of length G.N
        Measurements
    M : array of boolean, length G.N
        Masking vector.
    tau : float
        Regularization parameter.

    Examples
    --------
    >>> from pygsp import graphs, filters, learning
    >>> import matplotlib.pyplot as plt
    >>>
    >>> G = graphs.Sensor(N=100, seed=42)
    >>> G.estimate_lmax()

    Create a smooth ground truth signal:

    >>> filt = lambda x: 1 / (1 + 10*x)
    >>> g_filt = filters.Filter(G, filt)
    >>> rs = np.random.RandomState(42)
    >>> signal = g_filt.analyze(rs.randn(G.N))

    Construct a measurements signal from a binary mask:

    >>> mask = rs.uniform(0, 1, G.N) > 0.5
    >>> measurements = signal.copy()
    >>> measurements[~mask] = np.nan

    Solve the regression problem by reconstructing the signal:

    >>> recovery = learning.regression_tik(G, measurements, mask, tau=0)

    Plot the results:

    >>> f, (ax1, ax2, ax3) = plt.subplots(1, 3, sharey=True)
    >>> c = [signal.min(), signal.max()]
    >>> G.plot_signal(signal, plot_name='Ground truth', ax=ax1, limits=c)
    >>> G.plot_signal(measurements, plot_name='Measurements', ax=ax2, limits=c)
    >>> G.plot_signal(recovery, plot_name='Recovery', ax=ax3, limits=c)

    """

    if tau > 0:
        y[M == False] = 0
        # Creating this matrix may be problematic in term of memory.
        # Consider using an operator instead...
        if type(G.L).__module__ == np.__name__:
            LinearOp = np.diag(M*1) + tau * G.L
        else:
            def Op(x):
                return (M * x.T).T + tau * (G.L.dot(x))
            LinearOp = scipy.sparse.linalg.LinearOperator([G.N, G.N], Op)

        if type(G.L).__module__ == np.__name__:
            sol = np.linalg.solve(LinearOp, M * y)
        else:
            if len(y.shape) > 1:
                sol = np.zeros(shape=y.shape)
                res = np.zeros(shape=y.shape[1])
                for i in range(y.shape[1]):
                    sol[:, i], res[i] = scipy.sparse.linalg.cg(
                        LinearOp, y[:, i])
            else:
                sol, res = scipy.sparse.linalg.cg(LinearOp, y)
            # Do something with the residual...
        return sol

    else:

        if np.prod(M.shape) != G.N:
            ValueError("M should be of size [G.N,]")

        indl = M
        indu = M == False

        Luu = G.L[indu, :][:, indu]
        Wul = - G.L[indu, :][:, indl]
        if type(Luu).__module__ == np.__name__:
            sol_part = np.linalg.solve(Luu, np.matmul(Wul,y[indl]))
        else:
            sol_part = scipy.sparse.linalg.spsolve(Luu, Wul.dot(y[indl]))

        sol = y.copy()
        sol[indu] = sol_part

        return sol