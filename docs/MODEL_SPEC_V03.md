# ATS V0.3 Model Specification

## Prediction target

For a 159558 trading session `T`, the target is the adjusted close-to-close return:

`adjusted_close(T) / adjusted_close(T-1) - 1`

The binary class is 1 when the return is positive, otherwise 0.

## Leakage boundary

Every feature attached to date `T` must be available before the 159558 session `T` begins:

- target-internal features use 159558 data from `T-1` or earlier;
- overseas features use the latest source session strictly earlier than `T`;
- labels are generated separately and never used while constructing features.

## Baseline model

- Logistic Regression
- median imputation fitted on the training sample only;
- standardization fitted on the training sample only;
- chronological 75% train / 25% holdout split;
- no random shuffle;
- probability threshold: 0.50 for class evaluation;
- journal signal bands: bullish >= 0.55, bearish <= 0.45, otherwise neutral.

## Reported metrics

- accuracy;
- ROC AUC when both classes exist in the holdout sample;
- Brier score;
- log loss;
- positive-class rate.

This is a diagnostic baseline, not a production trading recommendation.
