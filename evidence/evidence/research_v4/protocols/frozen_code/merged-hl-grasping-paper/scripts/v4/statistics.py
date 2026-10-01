"""Pre-test simulator-free statistics with explicit abstention denominators."""
import math

import numpy as np

SEED = 2026100101
DRAWS = 10000


def wilson(success, total, z=1.959963984540054):
    if total == 0:
        return [None, None]
    p = success/total
    center = (p+z*z/(2*total))/(1+z*z/total)
    radius = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [max(0., center-radius), min(1., center+radius)]


def classification(prediction, reference, validity=None):
    if len(prediction) != len(reference):
        raise ValueError('Unpaired classification data')
    validity = ['VALID']*len(prediction) if validity is None else validity
    if len(validity) != len(prediction):
        raise ValueError('Unpaired validity data')
    matrix = {f'{r}_{p}': 0 for r in ('PASS', 'FAIL', 'INDETERMINATE') for p in ('PASS', 'FAIL', 'INDETERMINATE')}
    invalid = 0
    for p, r, valid in zip(prediction, reference, validity):
        if valid != 'VALID':
            invalid += 1
            p = 'INDETERMINATE'
        matrix[f'{r}_{p}'] += 1
    positive = sum(matrix['PASS_'+p] for p in ('PASS', 'FAIL', 'INDETERMINATE'))
    negative = sum(matrix['FAIL_'+p] for p in ('PASS', 'FAIL', 'INDETERMINATE'))
    tp, fp, fn = matrix['PASS_PASS'], matrix['FAIL_PASS'], matrix['PASS_FAIL']
    unknown_pos, unknown_neg = matrix['PASS_INDETERMINATE'], matrix['FAIL_INDETERMINATE']
    accepted_unlabeled = matrix['INDETERMINATE_PASS']
    accepted = tp+fp+accepted_unlabeled
    divide = lambda a, b: a/b if b else None
    return dict(n=len(prediction), invalid=invalid, reference_positive=positive, reference_negative=negative,
                reference_unknown=len(reference)-positive-negative, false_accept=fp, false_reject=fn,
                unknown_positive=unknown_pos, unknown_negative=unknown_neg,
                unknown_prediction=sum(matrix[r+'_INDETERMINATE'] for r in ('PASS', 'FAIL', 'INDETERMINATE')),
                FPR=divide(fp, negative), FNR=divide(fn, positive), accepted_risk=divide(fp, tp+fp),
                conditional_FPR=divide(fp, negative-unknown_neg), conditional_FNR=divide(fn, positive-unknown_pos),
                FPR_bounds=[divide(fp, negative), divide(fp+unknown_neg, negative)],
                FNR_bounds=[divide(fn, positive), divide(fn+unknown_pos, positive)],
                accepted_risk_bounds=[divide(fp, accepted), divide(fp+accepted_unlabeled, accepted)],
                correct_accept_per_assigned=divide(tp, len(prediction)), accepted_per_assigned=divide(accepted, len(prediction)),
                FPR_wilson_iid_only=wilson(fp, negative), FNR_wilson_iid_only=wilson(fn, positive), matrix=matrix)


def paired_stratified_bootstrap(a, b, strata, *, draws=DRAWS, seed=SEED):
    a, b, strata = np.asarray(a, float), np.asarray(b, float), np.asarray(strata)
    if a.shape != b.shape or a.ndim != 1 or len(a) != len(strata) or not len(a):
        raise ValueError('Invalid paired scene-level bootstrap arrays')
    rng = np.random.default_rng(seed)
    samples = np.zeros(draws)
    for group in sorted(set(strata)):
        ids = np.flatnonzero(strata == group)
        chosen = rng.integers(0, len(ids), size=(draws, len(ids)))
        samples += (a[ids]-b[ids])[chosen].sum(axis=1)/len(a)
    return dict(effect=float(np.mean(a-b)), interval95=np.quantile(samples, [.025, .975]).tolist(),
                interval975_bonferroni_two_primary=np.quantile(samples, [.0125, .9875]).tolist(),
                draws=draws, seed=seed, independent_unit='scene, stratified by declared fixed family/mechanism',
                paired_discordant=int(np.sum(a != b)),
                zero_discordance_caution='A degenerate percentile interval is not proof of population equivalence',
                zero_discordance_iid_upper95=(1-.05**(1/len(a))) if np.array_equal(a, b) else None)


def cluster_mean_interval(values, clusters, *, draws=DRAWS, seed=SEED):
    values, clusters = np.asarray(values, float), np.asarray(clusters)
    unique = sorted(set(clusters))
    if not unique:
        raise ValueError('No clusters')
    sums = np.array([values[clusters == c].sum() for c in unique])
    counts = np.array([(clusters == c).sum() for c in unique])
    rng = np.random.default_rng(seed)
    ids = rng.integers(0, len(unique), size=(draws, len(unique)))
    means = sums[ids].sum(axis=1)/counts[ids].sum(axis=1)
    return dict(mean=float(values.mean()), interval95=np.quantile(means, [.025, .975]).tolist(),
                clusters=len(unique), draws=draws, seed=seed,
                limitation='Very few object identities do not support claims about arbitrary new identities')
