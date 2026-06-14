# YNAB Indian Bank Importer

Python scripts to import Indian bank statements into [YNAB (You Need A Budget)](https://www.youneedabudget.com/) via the YNAB API.

## Supported Banks

| Bank  | Formats         | Script               |
|-------|-----------------|----------------------|
| ICICI | CSV, XLS, XLSX  | `icici_to_ynab.py`  |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get your YNAB API token

1. Log in to YNAB → **My Account** → **Developer Settings**
2. Click **New Token** and copy it

### 3. Create a `.env` file

```
YNAB_API_TOKEN=your_token_here
YNAB_BUDGET_ID=last-used
```

> ⚠️ Never commit `.env` to version control. It's already in `.gitignore`.

### 4. Find your YNAB account ID

```bash
python icici_to_ynab.py --list-accounts
```

---

## Usage

### ICICI Bank

Download your statement from ICICI Net Banking as **CSV** or **Excel**.

**Dry run (preview without importing):**
```bash
python icici_to_ynab.py --file statement.xlsx --account-id <ynab-account-id> --dry-run
```

**Import for real:**
```bash
python icici_to_ynab.py --file statement.csv --account-id <ynab-account-id>
```

---

## How It Works

- Automatically detects and skips junk header rows in ICICI exports
- Handles Indian number formatting (e.g. `1,23,456.78`)
- Converts separate Debit/Credit columns to YNAB's signed milliunit format
- Generates stable `import_id` values per transaction — re-importing the same file will **not** create duplicates
- Chunks large statements into batches of 1,000 (YNAB API limit per request)

## Amount Format

YNAB stores amounts in **milliunits** (1/1000th of a currency unit):

| Transaction | Amount (₹) | Milliunits |
|-------------|------------|------------|
| Debit ₹500  | -500.00    | -500000    |
| Credit ₹1,200 | +1200.00 | +1200000   |

## Project Structure

```
ynab-importers/
├── icici_to_ynab.py   # ICICI importer
├── requirements.txt
├── .env               # Your API token (never commit this)
├── .gitignore
└── README.md
```

## Contributing

PRs welcome — especially for other Indian banks (HDFC, SBI, Axis, Kotak).
Each bank tends to have its own quirky export format, so a new parser function
in the same pattern is all that's needed.

## License

MIT
