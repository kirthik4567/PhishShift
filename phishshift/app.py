"""PhishShift dashboard. Run:  streamlit run app.py
Educational triage tool: it never opens, fetches or runs links (NFR-01)."""
import json, joblib, pandas as pd, streamlit as st
from pipeline import *

st.set_page_config(page_title="PhishShift Message Risk Scanner", page_icon="🛡️", layout="wide")
st.title("🛡️ PhishShift Message Risk Scanner")
st.warning("Decision support only - NOT a guarantee of safety. Never click links in suspicious messages. "
           "Use only simulated messages; do not paste real passwords or personal data.")  # NFR-03 / NFR-02

@st.cache_resource
def load():
    return joblib.load("models/scanner_v1.joblib")
try:
    sc = load()
except Exception:
    st.error("Model not found. Run `python make_data.py` then `python train.py` first."); st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["🔍 Scan a message", "📊 Model comparison", "🧪 Errors & campaigns", "🌪️ Robustness (AT-03)"])

# ---------------- Tab 1: scanner ----------------
with tab1:
    c1, c2 = st.columns([2, 1])
    with c1:
        channel = st.selectbox("Channel", ["email", "sms"])
        sender = st.selectbox("Sender type", ["official_domain", "lookalike_domain", "unknown_number"])
        subject = st.text_input("Subject / title", "Password expires soon")
        body = st.text_area("Message body (defang links: hxxp://site[.]com)", height=140,
                            value="Your StaffHub password expires in 2 days. Please change it via the IT portal hxxps://portal[.]college[.]edu/it")
        url_feat = st.text_input("URL features (optional)", "url_full tld_edu url_https url_nodigits")
        model_name = st.radio("Model", ["tfidf_lr", "random_forest", "rules"], horizontal=True)
    if c2.button("Scan message", type="primary") or True:
        row = pd.DataFrame([dict(channel=channel, sender_domain_type=sender, subject_or_title=subject,
                                 body_text=body, sanitized_url_features=url_feat)])
        text = build_text(row)[0]
        p = float(sc.proba([text], model_name)[0]); decision = sc.decide(p)
        with c2:
            st.subheader("Result")
            if decision == "phish": st.error(f"⚠️ LIKELY PHISHING  ({p:.0%})")
            elif decision == "legit": st.success(f"✅ Looks legitimate  ({p:.0%} phishing risk)")
            else: st.info(f"🤔 NOT SURE - send to human review  ({p:.0%})")
            st.progress(min(max(p, 0.0), 1.0))
            st.caption(f"Abstain band: {ABSTAIN_LOW:.0%}-{ABSTAIN_HIGH:.0%}")
    cues, words = sc.explain(text)
    st.subheader("Why? (safe explanation)")
    a, b = st.columns(2)
    a.markdown("**Rule cues spotted**"); a.write(cues if cues else "None")
    b.markdown("**Words pushing the model toward 'phishing'**"); b.write(words if words else "None")

# ---------------- Tab 2: comparison ----------------
with tab2:
    res = pd.read_csv("results/results_table.csv")
    st.subheader("Rules vs TF-IDF + Logistic Regression vs Random Forest")
    st.dataframe(res, use_container_width=True)
    st.markdown("**Campaign holdout vs random split** - a big gap means the random split was too optimistic.")
    pv = res.pivot(index="model", columns="split", values="accuracy")
    st.bar_chart(pv)
    st.caption(open("results/run_info.json").read())

# ---------------- Tab 3: errors ----------------
with tab3:
    st.subheader("Per-campaign results (unseen campaigns)")
    st.dataframe(pd.read_csv("results/per_campaign.csv"), use_container_width=True)
    st.subheader("Misclassified examples (TF-IDF LR)")
    st.dataframe(pd.read_csv("results/error_examples.csv"), use_container_width=True)
    st.subheader("Near-duplicate removal log (FR-01)")
    st.dataframe(pd.read_csv("results/dedup_log.csv").head(50), use_container_width=True)

# ---------------- Tab 4: robustness ----------------
with tab4:
    st.subheader("Probability shift after harmless text changes")
    rb = pd.read_csv("results/robustness.csv")
    st.dataframe(rb, use_container_width=True)
    st.bar_chart(rb.set_index("perturbation")["mean_abs_prob_shift"])
    st.subheader("Try your own perturbation")
    base = st.text_area("Base message", "Payroll update: confirm your bank details at hxxp://secure-login1[.]evil-demo[.]xyz/123 before Friday")
    for name, fn in PERTURBATIONS.items():
        r = pd.DataFrame([dict(channel="email", sender_domain_type="lookalike_domain", subject_or_title="",
                               body_text=fn(base), sanitized_url_features="url_full tld_xyz url_http url_digits")])
        st.write(f"**{name}** -> {float(sc.proba(build_text(r), 'tfidf_lr')[0]):.0%} phishing risk")
