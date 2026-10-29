"""Train + evaluate everything and save results for the dashboard.
Run:  python train.py
"""
import json, joblib, numpy as np, pandas as pd
from sklearn.model_selection import train_test_split
from pipeline import *

raw = pd.read_csv("data/messages_raw.csv")                      # raw file is never modified
clean, dedup_log = deduplicate(raw)                              # FR-01
clean.to_csv("data/messages_clean.csv", index=False)
dedup_log.to_csv("results/dedup_log.csv", index=False)
print(f"Dedup: {len(raw)} -> {len(clean)} rows ({len(dedup_log)} near-duplicates removed)")

# ---- FR-03: campaign-separated holdout (unseen templates) ----
HOLDOUT = ["P6_novel_bec", "P7_novel_share", "L6_urgent_it", "L7_urgent_payroll"]
test = clean[clean.campaign_group.isin(HOLDOUT)].reset_index(drop=True)
train = clean[~clean.campaign_group.isin(HOLDOUT)].reset_index(drop=True)
assert not set(train.campaign_group) & set(test.campaign_group)
print("Train campaigns:", sorted(train.campaign_group.unique()))
print("Holdout campaigns:", HOLDOUT, "| train", len(train), "test", len(test))

Xtr, Xte = build_text(train), build_text(test)
sc = Scanner().fit(Xtr, (train.label == "phish").astype(int))

# ---- FR-02: compare 3 models on campaign holdout ----
rows = []
for m in ["rules", "tfidf_lr", "random_forest"]:
    r = evaluate(test.label, sc.proba(Xte, m), test.urgent_legit); r["model"] = m; r["split"] = "campaign_holdout"
    rows.append(r)

# ---- Comparison: random split (leaky) to show why campaign split matters (CP-3) ----
rtr, rte = train_test_split(clean, test_size=0.25, random_state=42, stratify=clean.label)
sc_r = Scanner().fit(build_text(rtr), (rtr.label == "phish").astype(int))
for m in ["rules", "tfidf_lr", "random_forest"]:
    r = evaluate(rte.label, sc_r.proba(build_text(rte), m), rte.urgent_legit); r["model"] = m; r["split"] = "random_split"
    rows.append(r)
res = pd.DataFrame(rows)[["model", "split", "n", "accuracy", "precision", "recall", "f1",
                          "fpr_all_legit", "fpr_urgent_legit", "abstain_rate", "accuracy_when_answering", "tp", "fp", "fn", "tn"]]
res.to_csv("results/results_table.csv", index=False)
print("\n", res.to_string(index=False))

# ---- Per-campaign breakdown (error analysis by subset) ----
p = sc.proba(Xte, "tfidf_lr")
test["p_phish"] = p; test["decision"] = [sc.decide(x) for x in p]
per_c = test.groupby("campaign_group").apply(
    lambda g: pd.Series({"n": len(g), "label": g.label.iloc[0], "mean_p_phish": round(g.p_phish.mean(), 3),
                         "correct_pct": round(((g.p_phish >= .5) == (g.label == "phish")).mean(), 3),
                         "abstain_pct": round((g.decision == "abstain").mean(), 3)}), include_groups=False).reset_index()
per_c.to_csv("results/per_campaign.csv", index=False); print("\n", per_c.to_string(index=False))

# ---- Error examples (CP-4: one missed phish, one false alarm) ----
wrong = test[((test.p_phish >= .5) != (test.label == "phish"))]
cols = ["message_id", "campaign_group", "label", "p_phish", "decision", "body_text"]
wrong[cols].sort_values("p_phish").head(30).to_csv("results/error_examples.csv", index=False)

# ---- AT-03: robustness drift ----
drift = []
base_acc = ((p >= .5) == (test.label == "phish")).mean()
for name, fn in PERTURBATIONS.items():
    pt = sc.proba([fn(t) for t in Xte], "tfidf_lr")
    drift.append(dict(perturbation=name, mean_abs_prob_shift=round(float(np.abs(pt - p).mean()), 3),
                      max_prob_shift=round(float(np.abs(pt - p).max()), 3),
                      accuracy=round(float(((pt >= .5) == (test.label == "phish")).mean()), 3),
                      accuracy_drift=round(float(((pt >= .5) == (test.label == "phish")).mean() - base_acc), 3),
                      label_flips=int(((pt >= .5) != (p >= .5)).sum())))
pd.DataFrame(drift).to_csv("results/robustness.csv", index=False)
print("\n", pd.DataFrame(drift).to_string(index=False))

joblib.dump(sc, "models/scanner_v1.joblib")
json.dump(dict(version="scanner_v1", holdout=HOLDOUT, train_rows=len(train), test_rows=len(test)),
          open("results/run_info.json", "w"), indent=2)
print("\nSaved models/scanner_v1.joblib and results/*.csv  -> now run: streamlit run app.py")
