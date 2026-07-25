# V0.5 Ensemble Model Specification

## Purpose

V0.5 adds a temporally calibrated ensemble. It remains a research model and does not
constitute investment advice.

## Chronological split

For every full training run, observations are ordered by `feature_date` and divided into:

1. base fitting sample;
2. later calibration sample;
3. final holdout sample.

No holdout observation is used for model fitting, probability calibration, or model weighting.

## Components

- Logistic regression: linear reference model.
- Extra Trees: nonlinear bagged tree model.
- Histogram gradient boosting: nonlinear boosting model.

All models use median imputation. Logistic regression also uses standardization.

## Calibration and weighting

Each component is fitted on the earliest sample. Its probability is then calibrated with a
sigmoid model using the later calibration sample. If that sample contains only one class, the
component retains its raw probability.

Weights are proportional to inverse calibration Brier score and normalized to sum to one.
The holdout ensemble probability is the weighted mean of calibrated component probabilities.

## Agreement and position tiers

Agreement is derived from cross-model probability dispersion and is clipped to `[0, 1]`.
Higher dispersion means lower agreement.

The long-only research position is:

- below 52% probability or below 50% agreement: 0%;
- 52% to below 57%: 25%;
- 57% to below 62%: 50%;
- 62% or above: 75%.

Agreement below 65% caps position at 25%; agreement below 80% caps it at 50%.
No short selling is implemented.

## Audit tables

- `ensemble_weights`
- `ensemble_component_predictions`
- `ensemble_decisions`

These tables preserve calibration quality, component-level probabilities, ensemble agreement,
confidence, position, signal, and realized outcome.
