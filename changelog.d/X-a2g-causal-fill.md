### Fixed
- **line X:** the global cell-level LSTM (arm A2g) filled missing inputs backward in time, so cells treeless in
  1985–2014 read the test run's late-century values. Inputs are now filled forward only, in training and prediction
  (`scripts/explore_glob_lstm.py --fill causal`, default). The clean retrain gives a tree-count response slope of 0.85
  (published 0.86) — the earlier "clean" figure of 0.65 came from re-predicting with the leak-trained model and is
  withdrawn (ADR 0315 §15). The Germany LSTM was not exposed (`scripts/explore_de_lstm_leak_probe.py`).
