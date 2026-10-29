"""Generate a SAFE synthetic dataset (no real URLs, no real people, no attachments).
All URLs are defanged (hxxp / [.]). Replace/extend with your mentor's data later.
Run:  python make_data.py
"""
import random, csv, datetime as dt
random.seed(7)

SERVICES = ["MailPortal", "CampusID", "CloudDrive", "PayDesk", "StaffHub", "VPN Access"]
NAMES = ["Anita", "Ravi", "Meena", "Arun", "Divya", "Suresh", "Priya", "Karthik", "Lakshmi", "Vimal"]
MONTHS = ["January", "February", "March", "April", "May", "June"]
BAD_TLD = ["xyz", "top", "click", "info", "site"]
GOOD_TLD = ["edu", "org", "com", "ac.in"]

def bad_url():
    host = random.choice(["secure-login", "verify-id", "acct-check", "update-now", "portal-sync"])
    return f"hxxp://{host}{random.randint(1,99)}[.]{random.choice(['evil-demo','fake-sim','lure-test'])}[.]{random.choice(BAD_TLD)}/{random.randint(100,999)}"

def short_url():
    return f"hxxp://sh0rt[.]ly/{random.choice('abcdefgh')}{random.randint(1000,9999)}"

def good_url():
    return f"hxxps://portal[.]{random.choice(['college','company','campus'])}[.]{random.choice(GOOD_TLD)}/{random.choice(['hr','it','login','docs'])}"

def url_features(u, kind):
    if not u: return "no_url"
    f = []
    f.append("url_short" if "sh0rt" in u else "url_full")
    tld = u.split("[.]")[-1].split("/")[0].split(".")[-1]
    f.append("tld_" + tld.replace(".", "_"))
    f.append("url_https" if u.startswith("hxxps") else "url_http")
    f.append("url_digits" if any(c.isdigit() for c in u.split("//")[1].split("/")[0]) else "url_nodigits")
    return " ".join(f)

GREET = ["Hi {n},", "Dear {n},", "Hello,", "Dear user,", "", "Hi team,"]
CLOSE = ["Thanks.", "Regards, IT Desk", "Do not reply to this message.", "- Admin", "Thank you for your cooperation.", "", "Have a good day."]

# ---------------- PHISHING CAMPAIGNS ----------------
PHISH = {
 "P1_credential": dict(channel="email", sender="lookalike", url="bad", cores=[
   "Your {s} password expires in {h} hours. Verify your account now at {u} to avoid suspension.",
   "Unusual sign-in detected on {s}. Confirm your password immediately: {u}",
   "Action required: your {s} access will be disabled today unless you validate credentials at {u}",
   "Security alert for {s}. Login again at {u} within {h} hours or your account will be locked."],
   subj=["Password expires soon", "Security alert", "Verify your account", "Account suspension notice"]),
 "P2_payroll": dict(channel="email", sender="lookalike", url="bad", cores=[
   "Payroll update: confirm your bank details at {u} before Friday to receive your salary.",
   "Your salary payment failed. Re-enter account information at {u} to release funds.",
   "HR notice: new direct deposit form must be completed today {u}",
   "Bonus payment pending for {n}. Submit your payment details here {u}"],
   subj=["Payroll update", "Salary on hold", "Direct deposit", "Bonus pending"]),
 "P3_parcel_sms": dict(channel="sms", sender="unknown", url="short", cores=[
   "Parcel {id} is on hold. Pay a small fee {u} now.",
   "Delivery failed for order {id}. Reschedule here {u}",
   "Customs charge due for package {id}: {u} pay within {h}h",
   "Your package could not be delivered. Update address {u}"],
   subj=["", "", "Parcel", "Delivery"]),
 "P4_quota": dict(channel="email", sender="lookalike", url="bad", cores=[
   "Your mailbox is full. Upgrade storage at {u} or lose incoming messages.",
   "Storage quota exceeded for {s}. Click {u} to restore access now.",
   "Final warning: {s} storage 99% used. Free up space via {u}",
   "Mail delivery halted. Re-activate your mailbox: {u}"],
   subj=["Mailbox full", "Storage warning", "Final warning", "Mail halted"]),
 "P5_prize": dict(channel="sms", sender="unknown", url="short", cores=[
   "Congratulations {n}! You were selected for a staff wellness reward. Claim here {u}",
   "You have won a gift card from the annual draw. Collect it at {u}",
   "Exclusive offer for employees: free voucher waiting {u}",
   "Lucky winner {n}: claim your reward before midnight {u}"],
   subj=["", "Reward", "", "Winner"]),
 # Unfamiliar wording: few classic phishing keywords. Used as unseen campaign.
 "P6_novel_bec": dict(channel="email", sender="lookalike", url="none", cores=[
   "Hi {n}, are you at your desk? I am in a meeting and cannot take calls. I need a small favour, reply to me here only.",
   "Quick favour {n}. Please purchase a few gift vouchers for a client and send me the codes by reply. I will reimburse you later.",
   "{n}, can you handle something discreetly for me today? Keep this between us and reply as soon as you see this.",
   "Are you free now? I need you to settle a vendor invoice quietly before the meeting ends, details by reply."],
   subj=["Quick favour", "Are you available", "Request", "Small task"]),
 "P7_novel_share": dict(channel="email", sender="lookalike", url="bad", cores=[
   "{n} shared a document with you: Q3 team review. Open it here {u}",
   "A file from HR is waiting for your review {u}",
   "Please see the updated seating plan and policy notes {u}",
   "Your colleague added you to a shared folder {u}"],
   subj=["Document shared", "File for review", "Seating plan", "Shared folder"]),
}

# ---------------- LEGITIMATE CAMPAIGNS ----------------
LEGIT = {
 "L1_pw_reset": dict(channel="email", sender="official", url="good", cores=[
   "You requested a password reset for {s}. Use the official portal at {u}. If you did not request this, ignore this message.",
   "Your {s} password was changed successfully. If this was not you, contact the helpdesk on extension {id}.",
   "To reset your password, sign in to the staff portal {u} and choose Forgot password."],
   subj=["Password reset requested", "Password changed", "Reset instructions"]),
 "L2_payslip": dict(channel="email", sender="official", url="good", cores=[
   "Your payslip for {m} is now available in the HR portal {u}. No action is needed.",
   "Payroll for {m} has been processed. Please review your payslip on the HR system.",
   "Reminder: submit your timesheet through the HR portal for {m} payroll."],
   subj=["Payslip available", "Payroll processed", "Timesheet reminder"]),
 "L3_it_notice": dict(channel="email", sender="official", url="none", cores=[
   "Scheduled maintenance this Saturday from 10 PM. Please save your work before then.",
   "The VPN will be upgraded on {m} 12. Expect a short outage of about {h} hours.",
   "New laptop refresh round begins next week. Check the IT calendar for your slot."],
   subj=["Maintenance notice", "VPN upgrade", "Laptop refresh"]),
 "L4_meeting": dict(channel="email", sender="official", url="none", cores=[
   "Team meeting moved to 3 PM tomorrow in room {id}. Agenda attached to the calendar invite.",
   "Please confirm your attendance for the review session on {m} 18.",
   "Lunch and learn on data privacy next Wednesday, all welcome."],
   subj=["Meeting update", "Attendance", "Lunch and learn"]),
 "L5_delivery": dict(channel="sms", sender="official", url="none", cores=[
   "Your order {id} has been delivered to the front desk.",
   "Courier will arrive between 2 and 4 PM today. Please keep your ID ready.",
   "Library book {id} is ready for pickup until Friday."],
   subj=["", "Delivery", ""]),
 # Unseen legit campaigns that sound urgent (the hard false-positive set)
 "L6_urgent_it": dict(channel="email", sender="official", url="good", cores=[
   "URGENT: your password expires in 2 days. Please change it today via the IT portal {u}. Helpdesk: extension {id}.",
   "Action required by Friday: complete the mandatory security training on the staff portal {u}.",
   "Important: account verification is required for all staff after the system migration. Use the official portal {u}.",
   "Immediate attention: your VPN certificate expires tomorrow. Renew it through IT Self Service {u}."],
   subj=["URGENT password expiry", "Action required", "Important notice", "Certificate expiry"]),
 "L7_urgent_payroll": dict(channel="email", sender="official", url="good", cores=[
   "Payroll cut-off is tomorrow 5 PM. Please submit pending timesheets in the HR system {u}.",
   "Urgent: confirm your bank details change request in person at the HR desk before payroll closes.",
   "Final reminder: expense claims for {m} must be approved today so they reach this month's salary.",
   "Your reimbursement is pending manager approval. Please follow up by end of day."],
   subj=["Payroll cut-off", "Urgent HR request", "Final reminder", "Reimbursement pending"]),
}
URGENT_CAMPAIGNS = {"L6_urgent_it", "L7_urgent_payroll"}

def make_row(i, camp, spec, label):
    core = random.choice(spec["cores"])
    kind = spec["url"]
    u = {"bad": bad_url, "short": short_url, "good": good_url}.get(kind, lambda: "")()
    n = random.choice(NAMES)
    text = core.format(n=n, s=random.choice(SERVICES), h=random.choice([2, 4, 12, 24, 48]),
                       id=random.randint(1000, 9999), m=random.choice(MONTHS), u=u)
    if spec["channel"] == "email":
        text = " ".join(x for x in [random.choice(GREET).format(n=n), text, random.choice(CLOSE)] if x)
    subj = random.choice(spec["subj"])
    sender = {"lookalike": "lookalike_domain", "unknown": "unknown_number", "official": "official_domain"}[spec["sender"]]
    d = dt.date(2026, 1, 1) + dt.timedelta(days=random.randint(0, 270))
    return dict(message_id=f"M{i:04d}", channel=spec["channel"], subject_or_title=subj, body_text=text,
                sanitized_url_features=url_features(u, kind), sender_domain_type=sender,
                label=label, campaign_group=camp, collected_date=d.isoformat(),
                urgent_legit=int(camp in URGENT_CAMPAIGNS),
                provenance="locally authored synthetic simulation (template generator, make_data.py)")

rows, i = [], 1
for camp, spec in PHISH.items():
    for _ in range(95):
        rows.append(make_row(i, camp, spec, "phish")); i += 1
for camp, spec in LEGIT.items():
    for _ in range(95):
        rows.append(make_row(i, camp, spec, "legit")); i += 1
random.shuffle(rows)
with open("data/messages_raw.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("wrote data/messages_raw.csv", len(rows), "rows")
