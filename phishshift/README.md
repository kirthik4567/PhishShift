# PhishShift Message Risk Scanner (ML-07)
Educational triage tool. It NEVER opens, fetches or runs links. Data is synthetic, URLs are defanged.

## Setup (VS Code terminal)
    python -m venv venv
    venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
    pip install -r requirements.txt

## Run
    python make_data.py            # creates data/messages_raw.csv (raw file, never edited later)
    python train.py                # dedup + 3 models + campaign holdout + robustness -> results/ + models/
    streamlit run app.py           # opens the dashboard at http://localhost:8501

## Files
- make_data.py  synthetic dataset (schema from SRS section 05)
- pipeline.py   dedup, rules, TF-IDF LR, Random Forest, abstain, explanations, perturbations
- train.py      experiments (FR-01 to FR-05)
- app.py        dashboard (risk-review UI)

## AI-usage disclosure
Starter code was generated with Claude (Anthropic). Replace the synthetic data and explain every part before submission.
