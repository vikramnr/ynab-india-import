"""
ICICI Bank → YNAB Importer
===========================
Supports: CSV and Excel (.xls/.xlsx) exports from ICICI Net Banking

Usage:
    python icici_to_ynab.py --file statement.csv --account-id <ynab_account_id>
    python icici_to_ynab.py --file statement.xlsx --account-id <ynab_account_id> --dry-run

Setup:
    pip install pandas openpyxl xlrd requests pyyaml python-dotenv
    cp config.yml.example config.yml
    # Edit config.yml with your YNAB API token

Create a config.yml file in the same directory (see config.yml for format).
Or set environment variables (YNAB_API_TOKEN, YNAB_BUDGET_ID, etc.)
"""

import os
import re
import hashlib
import argparse
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from config import load_config, get_config, ConfigError

load_dotenv()

# ── ICICI Statement Parser ────────────────────────────────────────────────────

# ICICI Net Banking exports typically have a few junk header rows before the
# actual table. We scan for the row that contains known column headers.
ICICI_COLUMNS = {
    "date":        ["Transaction Date", "Txn Date", "Date"],
    "description": ["Description", "Particulars", "Narration"],
    "ref":         ["Ref No./Cheque No.", "Ref No", "Cheque No"],
    "debit":       ["Debit", "Withdrawal Amt.", "Withdrawal"],
    "credit":      ["Credit", "Deposit Amt.", "Deposit"],
    "balance":     ["Balance", "Closing Balance"],
}


def find_header_row(df: pd.DataFrame) -> int:
    """Scan rows to find the one that looks like the column header."""
    date_keywords = {c.lower() for c in ICICI_COLUMNS["date"]}
    for i, row in df.iterrows():
        row_vals = [str(v).strip().lower() for v in row.values]
        if any(kw in row_vals for kw in date_keywords):
            return i
    raise ValueError(
        "Could not find a header row in the statement. "
        "Make sure you're using an ICICI Net Banking export."
    )


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename whatever ICICI called the columns to standard internal names."""
    col_map = {}
    df_cols_lower = {c.strip().lower(): c for c in df.columns}

    for canonical, variants in ICICI_COLUMNS.items():
        for v in variants:
            if v.strip().lower() in df_cols_lower:
                col_map[df_cols_lower[v.strip().lower()]] = canonical
                break

    missing = [k for k in ["date", "description", "debit", "credit"] if k not in col_map.values()]
    if missing:
        raise ValueError(f"Missing expected columns: {missing}. Found: {list(df.columns)}")

    return df.rename(columns=col_map)


def parse_amount(value) -> float:
    """Convert ICICI amount strings like '1,23,456.78' to float."""
    if pd.isna(value) or str(value).strip() in ("", "-"):
        return 0.0
    cleaned = re.sub(r"[₹,\s]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(value: str) -> str:
    """Parse ICICI date formats (DD/MM/YYYY or DD-MM-YYYY) → YYYY-MM-DD."""
    value = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {value!r}")


def load_statement(filepath: str) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".csv":
        # Try reading with different encodings; ICICI sometimes uses latin-1
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                raw = pd.read_csv(filepath, header=None, encoding=enc, dtype=str)
                break
            except UnicodeDecodeError:
                continue
    elif ext in (".xls", ".xlsx"):
        engine = "xlrd" if ext == ".xls" else "openpyxl"
        raw = pd.read_excel(filepath, header=None, dtype=str, engine=engine)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Drop completely empty rows/columns
    raw.dropna(how="all", inplace=True)
    raw.reset_index(drop=True, inplace=True)

    header_row = find_header_row(raw)

    # Promote that row to column headers
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[header_row]]
    df = df[df.columns[df.columns != ""]]  # drop empty-header columns
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return normalise_columns(df)


# ── YNAB Conversion ────────────────────────────────────────────────────────

def make_import_id(date: str, amount_milliunits: int, description: str, index: int) -> str:
    """
    Stable, unique ID so YNAB deduplicates if you re-import the same file.
    Format: YNAB:milliunits:date:hash
    """
    raw = f"{date}:{amount_milliunits}:{description}:{index}"
    digest = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"YNAB:{amount_milliunits}:{date}:{digest}"


def to_ynab_transactions(df: pd.DataFrame, account_id: str) -> list[dict]:
    transactions = []

    for i, row in df.iterrows():
        try:
            date = parse_date(row["date"])
        except ValueError as e:
            print(f"  ⚠  Row {i}: skipping — {e}")
            continue

        debit  = parse_amount(row.get("debit",  0))
        credit = parse_amount(row.get("credit", 0))

        if debit == 0 and credit == 0:
            continue  # skip blank/summary rows

        # YNAB: outflows are negative milliunits, inflows positive
        amount_milliunits = int(round((credit - debit) * 1000))

        description = str(row.get("description", "")).strip() or "No description"
        ref         = str(row.get("ref", "")).strip()
        memo        = f"{description} | Ref: {ref}" if ref and ref not in ("nan", "") else description

        import_id = make_import_id(date, amount_milliunits, description, i)

        transactions.append({
            "account_id": account_id,
            "date":       date,
            "amount":     amount_milliunits,
            "payee_name": description[:100],   # YNAB max 100 chars
            "memo":       memo[:200],           # YNAB max 200 chars
            "cleared":    "cleared",
            "import_id":  import_id,
        })

    return transactions


# ── YNAB API ───────────────────────────────────────────────────────────

def get_accounts(config) -> list[dict]:
    """Fetch list of YNAB accounts."""
    headers = {"Authorization": f"Bearer {config.ynab_api_token}"}
    resp = requests.get(f"{config.ynab_base_url}/accounts", headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]["accounts"]


def push_transactions(config, transactions: list[dict], dry_run: bool = False) -> dict:
    """Push transactions to YNAB API."""
    if dry_run:
        print(f"\n[DRY RUN] Would send {len(transactions)} transactions to YNAB.")
        for t in transactions[:5]:
            print(f"  {t['date']}  {t['amount']/1000:>10.2f}  {t['payee_name'][:50]}")
        if len(transactions) > 5:
            print(f"  ... and {len(transactions) - 5} more")
        return {}

    headers = {"Authorization": f"Bearer {config.ynab_api_token}"}
    batch_size = config.max_batch_size

    # YNAB allows max batch_size per request; chunk if needed
    results = []
    for chunk_start in range(0, len(transactions), batch_size):
        chunk = transactions[chunk_start:chunk_start + batch_size]
        resp = requests.post(
            f"{config.ynab_base_url}/transactions",
            headers=headers,
            json={"transactions": chunk},
        )
        if not resp.ok:
            print(f"  ✗ YNAB API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        data = resp.json()["data"]
        results.append(data)
        dupes = len(data.get("duplicate_import_ids", []))
        created = len(data.get("transaction_ids", []))
        print(f"  ✓ Chunk {chunk_start//batch_size + 1}: {created} created, {dupes} duplicates skipped")

    return results


# ── CLI ────────────────────────────────────────────────────────────

def list_accounts(config):
    """List all YNAB accounts."""
    print("\nYour YNAB accounts:\n")
    for acc in get_accounts(config):
        if not acc["deleted"] and not acc["closed"]:
            print(f"  {acc['name']:<35} {acc['id']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Import ICICI Bank statement into YNAB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python icici_to_ynab.py --list-accounts
  python icici_to_ynab.py --file statement.csv --account-id <uuid> --dry-run
  python icici_to_ynab.py --file statement.xlsx --account-id <uuid>

Configuration:
  Settings are loaded from config.yml (required).
  Environment variables (YNAB_API_TOKEN, etc.) override config.yml.
        """
    )
    parser.add_argument("--file",            help="Path to ICICI statement (.csv or .xlsx)")
    parser.add_argument("--account-id",      help="YNAB account UUID to import into")
    parser.add_argument("--dry-run",         action="store_true", help="Parse and preview without sending to YNAB")
    parser.add_argument("--no-dry-run",      action="store_true", help="Override dry_run config setting")
    parser.add_argument("--list-accounts",   action="store_true", help="List all YNAB accounts and their IDs")
    parser.add_argument("--config",          default="config.yml", help="Path to config file (default: config.yml)")
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")
        return 1

    try:
        _ = config.ynab_api_token  # Validate token is set
    except ConfigError as e:
        print(f"✗ {e}")
        return 1

    # Handle --list-accounts
    if args.list_accounts:
        try:
            list_accounts(config)
        except requests.RequestException as e:
            print(f"✗ API error: {e}")
            return 1
        return 0

    # Handle file import
    if not args.file:
        parser.error("--file is required (unless using --list-accounts)")

    # Determine dry-run mode
    dry_run = config.import_dry_run
    if args.dry_run:
        dry_run = True
    if args.no_dry_run:
        dry_run = False

    # Get account ID
    account_id = args.account_id or config.import_account_id
    if not account_id and not dry_run:
        parser.error("--account-id is required (or set in config.yml, or use --dry-run)")

    print(f"\n📄 Loading statement: {args.file}")
    try:
        df = load_statement(args.file)
    except (ValueError, FileNotFoundError) as e:
        print(f"✗ Error loading statement: {e}")
        return 1

    print(f"   Found {len(df)} rows")

    account_id = account_id or "DRY-RUN-ACCOUNT"
    transactions = to_ynab_transactions(df, account_id)
    print(f"   Parsed {len(transactions)} valid transactions")

    if not transactions:
        print("Nothing to import.")
        return 0

    try:
        push_transactions(config, transactions, dry_run=dry_run)
    except requests.RequestException as e:
        print(f"✗ API error: {e}")
        return 1

    if not dry_run:
        print(f"\n✅ Done! {len(transactions)} transactions sent to YNAB.")

    return 0


if __name__ == "__main__":
    exit(main())
