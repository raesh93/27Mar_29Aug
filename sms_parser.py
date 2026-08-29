import re
import json
import os
import pandas as pd
from datetime import datetime

DEFAULT_RULES_FILE = "merchant_rules.json"

def load_rules(rules_path=DEFAULT_RULES_FILE):
    if os.path.exists(rules_path):
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"merchants": {}}

def save_rules(rules, rules_path=DEFAULT_RULES_FILE):
    with open(rules_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)

def clean_merchant_string(raw_m):
    if not raw_m:
        return "Unknown"
    m = str(raw_m).strip()
    m = re.sub(r"^UPI/(?:UPI/)?", "", m, flags=re.IGNORECASE)
    m = re.sub(r"^UPI-\d+-", "", m, flags=re.IGNORECASE)
    m = re.sub(r"^PYU\*", "", m, flags=re.IGNORECASE)
    m = re.sub(r"^WWW\s+", "", m, flags=re.IGNORECASE)
    m = re.sub(r"^ACHCR/", "", m, flags=re.IGNORECASE)
    m = re.sub(r"\s+", " ", m).strip()
    return m

def match_hierarchy(raw_merchant, content, txn_type, rules):
    merchants = rules.get("merchants", {})
    clean_raw = clean_merchant_string(raw_merchant)
    m_lower = clean_raw.lower()
    c_lower = str(content).lower()
    
    # 1. Match against explicit rules in config
    for key, rule in merchants.items():
        patterns = rule.get("match_patterns", [key])
        for p in patterns:
            p_lower = p.lower()
            if p_lower in m_lower or p_lower in c_lower:
                return (
                    rule.get("name", clean_raw),
                    rule.get("type", txn_type),
                    rule.get("bucket", "Other / Uncategorized"),
                    rule.get("sub_bucket", "General"),
                    rule.get("sub_sub_bucket", "Unspecified")
                )
                
    # 2. Fallbacks based on structure
    if "@" in clean_raw:
        handle_name = clean_raw.split("@")[0]
        if handle_name.isdigit():
            display_name = f"UPI {handle_name}"
        else:
            display_name = handle_name.replace(".", " ").replace("_", " ").title()
        return (
            display_name,
            "Transfer" if txn_type == "Expense" else txn_type,
            "Family & Personal Transfers",
            "Peer to Peer (UPI)",
            "P2P Transfer"
        )
        
    if re.search(r"^X\d{4}$", clean_raw):
        return (
            f"Bank A/C {clean_raw}",
            "Transfer",
            "Family & Personal Transfers",
            "Account Transfer",
            "Direct A/C Transfer"
        )
        
    if txn_type in ["Income", "Salary / Income", "Dividend / Inflow"]:
        return (
            clean_raw if clean_raw != "Unknown" else "Other Income",
            "Income",
            "Income & Inflows",
            "Other Inflows",
            "General Inflow"
        )

    if txn_type in ["Refund / Reversal", "Cashback / Reward"]:
        return (
            clean_raw if clean_raw != "Unknown" else "Refund",
            txn_type,
            "Income & Inflows",
            "Refunds & Cashbacks",
            "Refund / Reversal"
        )
        
    return (
        clean_raw if clean_raw else "Uncategorized Merchant",
        txn_type,
        "Other / Uncategorized",
        "Unclassified Spends",
        "Unspecified"
    )

def parse_sms_record(row, rules):
    contact = str(row.get("Contact", "")).strip()
    content = str(row.get("Content", "")).strip()
    dt_str = str(row.get("DateTime", "")).strip()
    
    # Filter pure OTP / 2FA alerts
    if re.search(r"\b(is the otp|is secret otp|is your otp|otp to|use otp|one-time password for|otp is \d+)\b", content, re.IGNORECASE):
        return None, "OTP"
        
    # Filter promotional / marketing
    if re.search(r"\b(get simply save|instant discount|flat \d+% off|pre-approved|apply for|apply now|win up to|congrats.*life cover|launches premium|save rs\.|hurry! last few days|enjoy zero processing fee|manage spends effectively by increasing|spacious 2 & 3bhk|special deal on flights)\b", content, re.IGNORECASE):
        return None, "PROMO"
        
    # Filter pure informational / non-payment statements
    if re.search(r"\b(statement for credit card|bill for your airtel|total due:|min due:|re-kyc due|is maturing on|e-voting for|passbook balance against|reported your fund bal|traded value for|investment value in tier)\b", content, re.IGNORECASE):
        if not re.search(r"\b(payment received|payment of rs.*received|debited|spent|sent rs|credited to)\b", content, re.IGNORECASE):
            return None, "STATEMENT_REPORT"
            
    # Extract Amount
    amt_match = re.search(r"(?:INR|Rs\.?|e₹)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", content, re.IGNORECASE)
    if not amt_match:
        return None, "NO_AMOUNT"
        
    amount = float(amt_match.group(1).replace(",", ""))
    
    # Account Detection
    account = "Other"
    if "KOTAK" in contact.upper() or "KOTAK" in content.upper():
        ac_m = re.search(r"(?:AC\s*(?:no\.?\s*)?|A/C\s*(?:no\.?\s*)?|a/c\s*)([X\d]+)", content, re.IGNORECASE)
        card_m = re.search(r"(?:Card\s*(?:no\.?\s*)?)([X\d]+)", content, re.IGNORECASE)
        if ac_m: account = f"Kotak Bank AC {ac_m.group(1)}"
        elif card_m: account = f"Kotak Card {card_m.group(1)}"
        else: account = "Kotak Bank"
    elif "AUBANK" in contact.upper() or "AU BANK" in content.upper():
        card_m = re.search(r"(?:Credit Card\s*|Card\s*)([xX\d]+)", content, re.IGNORECASE)
        account = f"AU Bank Card {card_m.group(1)}" if card_m else "AU Bank Card x1292"
    elif "ICICI" in contact.upper() or "ICICI" in content.upper():
        card_m = re.search(r"(?:Credit Card\s*|Card\s*)([xX\d]+)", content, re.IGNORECASE)
        account = f"ICICI Card {card_m.group(1)}" if card_m else "ICICI Card"
    elif "AXIS" in contact.upper() or "AXIS" in content.upper():
        card_m = re.search(r"(?:Card no\.\s*|Credit Card\s*|Card\s*)([xX\d]+)", content, re.IGNORECASE)
        account = f"Axis Card {card_m.group(1)}" if card_m else "Axis Card XX2873"
    elif "HDFC" in contact.upper() or "HDFC" in content.upper():
        card_m = re.search(r"(?:Card\s*(?:ending with\s*)?)([xX\d]+)", content, re.IGNORECASE)
        account = f"HDFC Card {card_m.group(1)}" if card_m else "HDFC Card 7699"
    elif "BOB" in contact.upper():
        ac_m = re.search(r"(?:A/c\s*|A/C\s*)([.\d]+|[X\d]+)", content, re.IGNORECASE)
        account = f"BOB AC {ac_m.group(1)}" if ac_m else "BOB AC 2235"
    elif "QCAMZN" in contact.upper() or "AMAZON" in content.upper():
        account = "Amazon Pay Wallet"
    elif "ZEPTO" in contact.upper() or "ZEPTO CASH" in content.upper():
        account = "Zepto Cash"
    elif "CREDIN" in contact.upper():
        account = "CRED"
    else:
        account = contact

    # Merchant & Raw Type Parsing
    txn_type = "Expense"
    merchant = "Unknown"
    ref_no = ""
    
    # Specific Bank Debit Patterns
    kotak_sent = re.search(r"Sent Rs\.?\s*[\d,.]+\s+from Kotak Bank AC [^\s]+ to ([^\s]+)\s+on", content, re.IGNORECASE)
    au_spent = re.search(r"spent at (.+?) on AU Bank", content, re.IGNORECASE)
    icici_debited = re.search(r"debited for INR\s*[\d,.]+\s+on [^\s]+ for (.+?)(?:\.|$)", content, re.IGNORECASE)
    icici_spent = re.search(r"spent using ICICI Bank Card [^\s]+ on [^\s]+ on (.+?)(?:\. Avl|$)", content, re.IGNORECASE)
    axis_spent = re.search(r"Spent INR\s*[\d,.]+\s+Axis Bank Card no\.\s*[^\s]+\s+[^\s]+\s+[^\s]+\s+(?:IST\s+)?(.+?)\s+Avl Limit", content, re.IGNORECASE)
    hdfc_spent = re.search(r"Spent Rs\.?\s*[\d,.]+\s+On HDFC Bank Card [^\s]+ At (.+?)\s+On", content, re.IGNORECASE)
    kotak_atm = re.search(r"withdrawn via Kotak Debit Card [^\s]+ on [^\s]+ at (.+?)(?:\. Avl|$)", content, re.IGNORECASE)
    bob_dr = re.search(r"Dr\.\s*from A/C [^\s]+ and Cr\.\s*to (.+?)(?:\. Ref|\.|$)", content, re.IGNORECASE)
    
    # Specific Bank Credit / Inflow Patterns
    kotak_neft = re.search(r"credited to your Kotak Bank a/c [^\s]+ via NEFT from beneficiary (.+?)(?:\. UTR|$)", content, re.IGNORECASE)
    kotak_rev = re.search(r"credited to Kotak Bank A/C.*reversal", content, re.IGNORECASE)
    icici_ref = re.search(r"^(.*?)\s*refund of Rs\.?\s*[\d,.]+\s+credited to your ICICI", content, re.IGNORECASE)
    bob_cr = re.search(r"Credited to A/c .* from:ACHCR/(.+?)(?:\s*\.|\s+Total|$)", content, re.IGNORECASE)
    axis_cashback = re.search(r"Cashback of INR\s*[\d,.]+\s+has been credited", content, re.IGNORECASE)
    groww_settle = re.search(r"Transfer successful from Groww", content, re.IGNORECASE)
    cc_pmt_rcvd = re.search(r"(?:PAYMENT OF Rs\.\s*[\d,.]+\s*RECEIVED TOWARDS YOUR CREDIT CARD|Payment of INR\s*[\d,.]+\s*received towards your ICICI|credited to AU Bank Credit Card)", content, re.IGNORECASE)
    
    ref_match = re.search(r"(?:UPI Ref|Ref no|UTR|Ref:)\s*([A-Za-z0-9-]+)", content, re.IGNORECASE)
    if ref_match:
        ref_no = ref_match.group(1).strip()

    if kotak_sent:
        merchant = kotak_sent.group(1).strip()
        txn_type = "Expense"
    elif au_spent:
        merchant = au_spent.group(1).strip()
        txn_type = "Expense"
    elif icici_debited:
        merchant = icici_debited.group(1).strip()
        txn_type = "Expense"
    elif icici_spent:
        merchant = icici_spent.group(1).strip()
        txn_type = "Expense"
    elif axis_spent:
        merchant = axis_spent.group(1).strip()
        txn_type = "Expense"
    elif hdfc_spent:
        merchant = hdfc_spent.group(1).strip()
        txn_type = "Expense"
    elif kotak_atm:
        merchant = f"ATM Cash ({kotak_atm.group(1).strip()})"
        txn_type = "Cash Withdrawal"
    elif bob_dr:
        merchant = bob_dr.group(1).strip()
        txn_type = "Expense"
    elif kotak_neft:
        merchant = kotak_neft.group(1).strip()
        txn_type = "Income"
    elif bob_cr:
        merchant = bob_cr.group(1).strip()
        txn_type = "Income"
    elif axis_cashback:
        merchant = "Axis Cashback"
        txn_type = "Cashback / Reward"
    elif groww_settle:
        merchant = "Groww Settlement"
        txn_type = "Investment Inflow"
    elif kotak_rev or icici_ref:
        merchant = (icici_ref.group(1).strip() if icici_ref else "UPI Reversal")
        txn_type = "Refund / Reversal"
    elif cc_pmt_rcvd:
        merchant = "Credit Card Bill Payment"
        txn_type = "Credit Card Bill Payment"
    elif "Payment of Rs" in content and "using Apay balance" in content:
        merchant = "Amazon Pay"
        txn_type = "Expense"
    elif "Your payment of Rs" in content and "using Zepto Cash" in content:
        merchant = "Zepto"
        txn_type = "Expense"
    elif "received a payment of Rs" in content and "AIRBIL" in contact:
        merchant = "Airtel"
        txn_type = "Expense"
    elif "purchase @ Apollo Pharmacy" in content:
        merchant = "Apollo Pharmacy"
        txn_type = "Expense"
    elif "Your CRED Cash EMI" in content:
        merchant = "CRED EMI"
        txn_type = "Debt / EMI"
    else:
        if re.search(r"\b(spent|debited|paid|transferred to)\b", content, re.IGNORECASE):
            txn_type = "Expense"
            merchant = contact
        elif re.search(r"\b(credited|received|refund)\b", content, re.IGNORECASE):
            txn_type = "Income"
            merchant = contact
        else:
            return None, "UNCLASSIFIED"

    clean_name, final_type, bucket, sub_bucket, sub_sub_bucket = match_hierarchy(
        merchant, content, txn_type, rules
    )

    parsed_date = dt_str
    try:
        dt_obj = pd.to_datetime(dt_str)
        parsed_date = dt_obj.strftime("%Y-%m-%d")
        month_year = dt_obj.strftime("%Y-%m (%b)")
    except Exception:
        month_year = "Unknown"

    return {
        "Date": parsed_date,
        "Month": month_year,
        "Amount": amount,
        "Type": final_type,
        "Bucket": bucket,
        "Sub_Bucket": sub_bucket,
        "Sub_Sub_Bucket": sub_sub_bucket,
        "Merchant": clean_name,
        "Raw_Merchant": clean_merchant_string(merchant),
        "Account": account,
        "Ref_No": ref_no,
        "Sender": contact,
        "Raw_SMS": content
    }, "SUCCESS"

def parse_sms_file(csv_source, rules=None):
    if rules is None:
        rules = load_rules()
        
    df = pd.read_csv(csv_source)
    df.columns = [c.strip().lstrip("\ufeff") for c in df.columns]
    
    parsed_rows = []
    for _, row in df.iterrows():
        rec, status = parse_sms_record(row, rules)
        if rec:
            parsed_rows.append(rec)
            
    res_df = pd.DataFrame(parsed_rows)
    if not res_df.empty:
        try:
            res_df["_dt"] = pd.to_datetime(res_df["Date"])
            res_df = res_df.sort_values("_dt", ascending=False).drop(columns=["_dt"]).reset_index(drop=True)
        except Exception:
            pass
    return res_df
