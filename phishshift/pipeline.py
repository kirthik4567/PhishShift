"""Core logic for PhishShift: cleaning, dedup, models, abstain, explanations, robustness."""
import re, json
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics.pairwise import cosine_similarity

ABSTAIN_LOW, ABSTAIN_HIGH = 0.35, 0.65      # prob band where the tool says "not sure"
DEDUP_THRESHOLD = 0.90                       # cosine similarity above this = near-duplicate

# ---------- text building (NFR-01: we only read text, never open links) ----------
def build_text(df):
    return (df["channel"].fillna("") + " sender_" + df["sender_domain_type"].fillna("") + " "
            + df["subject_or_title"].fillna("") + " " + df["body_text"].fillna("") + " "
            + df["sanitized_url_features"].fillna(""))

def normalise(s):
    s = s.lower()
    s = re.sub(r"\d+", "0", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------- FR-01 dedup ----------
def deduplicate(df, threshold=DEDUP_THRESHOLD):
    """Greedy near-duplicate removal on the BODY wording. Returns (clean_df, log_df)."""
    texts = (df["subject_or_title"].fillna("") + " " + df["body_text"].fillna("")).map(normalise)
    # strip slot values (names, services) so template clones collapse together
    X = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(texts)
    sim = cosine_similarity(X)
    keep, dropped = [], []
    for i in range(len(df)):
        dup_of = next((j for j in keep if sim[i, j] >= threshold), None)
        if dup_of is None: keep.append(i)
        else: dropped.append((df.iloc[i]["message_id"], df.iloc[dup_of]["message_id"], round(float(sim[i, dup_of]), 3)))
    log = pd.DataFrame(dropped, columns=["removed_id", "kept_id", "similarity"])
    return df.iloc[keep].reset_index(drop=True), log

# ---------- Model 1: rules ----------
RULE_CUES = {
    "urgency wording":            (r"\b(urgent|immediately|now|today|within \d+|final warning|expires?|suspend|suspension|locked|disabled)\b", 1.0),
    "credential request":         (r"\b(verify|validate|confirm|re-?enter|login|sign in)\b.*\b(password|account|credentials|bank|details)\b", 1.5),
    "money / reward lure":        (r"\b(gift card|voucher|reward|winner|won|salary|bonus|fee|pay)\b", 1.0),
    "shortened link":             (r"url_short|sh0rt", 2.0),
    "suspicious link ending":     (r"tld_(xyz|top|click|info|site)", 2.0),
    "look-alike / unknown sender":(r"sender_(lookalike_domain|unknown_number)", 1.5),
    "secrecy / off-channel ask":  (r"\b(discreet|discreetly|quietly|between us|reply here only|cannot take calls)\b", 2.0),
}
def rule_cues(text):
    t = text.lower()
    return {name: w for name, (pat, w) in RULE_CUES.items() if re.search(pat, t)}

def rules_proba(texts):
    out = []
    for t in texts:
        score = sum(rule_cues(t).values())
        out.append(1 / (1 + np.exp(-(score - 3.0))))   # score 3 -> 50%
    return np.array(out)

# ---------- Models 2 and 3 ----------
def make_tfidf_lr():
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    return vec, LogisticRegression(max_iter=1000, C=2.0, class_weight="balanced")

def make_rf():
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=3000)
    return vec, RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1)

class Scanner:
    """Wraps the three models behind one predict_proba(texts) -> P(phish)."""
    def __init__(self):
        self.vecs, self.models = {}, {}
    def fit(self, texts, y):
        for name, maker in [("tfidf_lr", make_tfidf_lr), ("random_forest", make_rf)]:
            vec, clf = maker()
            clf.fit(vec.fit_transform(texts), y)
            self.vecs[name], self.models[name] = vec, clf
        return self
    def proba(self, texts, model="tfidf_lr"):
        texts = list(texts)
        if model == "rules": return rules_proba(texts)
        return self.models[model].predict_proba(self.vecs[model].transform(texts))[:, 1]
    def decide(self, p):
        """FR-04: phish / legit / abstain."""
        if p >= ABSTAIN_HIGH: return "phish"
        if p <= ABSTAIN_LOW: return "legit"
        return "abstain"
    def explain(self, text, top_k=5):
        """Safe explanation: only cue NAMES and word pieces, never the link itself."""
        cues = list(rule_cues(text).keys())
        vec, clf = self.vecs["tfidf_lr"], self.models["tfidf_lr"]
        x = vec.transform([text]); names = np.array(vec.get_feature_names_out())
        contrib = x.toarray()[0] * clf.coef_[0]
        idx = np.argsort(-contrib)[:top_k]
        words = [names[i] for i in idx if contrib[i] > 0 and not names[i].startswith(("hxxp", "http"))]
        return cues, words

# ---------- Metrics ----------
def evaluate(y_true, p, urgent_legit=None):
    y_true = np.asarray(y_true); y_bin = (y_true == "phish").astype(int)
    pred_all = (p >= 0.5).astype(int)
    tp = int(((pred_all == 1) & (y_bin == 1)).sum()); fp = int(((pred_all == 1) & (y_bin == 0)).sum())
    fn = int(((pred_all == 0) & (y_bin == 1)).sum()); tn = int(((pred_all == 0) & (y_bin == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    res = dict(n=len(y_true), accuracy=round((tp + tn) / len(y_true), 3), precision=round(prec, 3),
               recall=round(rec, 3), f1=round(f1, 3), fpr_all_legit=round(fp / (fp + tn), 3) if fp + tn else 0.0,
               tp=tp, fp=fp, fn=fn, tn=tn)
    if urgent_legit is not None:
        m = (np.asarray(urgent_legit) == 1)
        res["fpr_urgent_legit"] = round(float((pred_all[m] == 1).mean()), 3) if m.sum() else None
    inside = (p > ABSTAIN_LOW) & (p < ABSTAIN_HIGH)
    res["abstain_rate"] = round(float(inside.mean()), 3)
    ans = ~inside
    res["accuracy_when_answering"] = round(float((pred_all[ans] == y_bin[ans]).mean()), 3) if ans.sum() else None
    return res

# ---------- AT-03 perturbations (all harmless text edits) ----------
PERTURBATIONS = {
    "refang_url":      lambda t: t.replace("hxxp", "http").replace("[.]", "."),
    "no_punctuation":  lambda t: re.sub(r"[^\w\s]", "", t),
    "extra_exclaim":   lambda t: re.sub(r"([.:])", r"\1!!", t),
    "ALL_CAPS":        lambda t: t.upper(),
    "spaced_url_dots": lambda t: t.replace("[.]", " [ . ] "),
}
