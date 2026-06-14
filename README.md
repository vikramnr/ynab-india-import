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

### 3. Create a configuration file

Copy the provided config template:

```bash
cp config.yml config.yml
```

Edit `config.yml` and add your YNAB API token:

```yaml
ynab:
  api_token: "your_token_from_ynab_here"
  budget_id: "last-used"
```

**⚠️ Important:** Never commit `config.yml` to version control if it contains real credentials! Use it only locally.

For production/CI environments, **use environment variables** instead:
```bash
export YNAB_API_TOKEN="your_token_here"
export YNAB_BUDGET_ID="last-used"
```

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

**Or configure a default account in `config.yml`:**
```yaml
import:
  account_id: "your-account-uuid-here"
  dry_run: false
```

Then just run:
```bash
python icici_to_ynab.py --file statement.csv
```

---

## Configuration

Configuration is managed through `config.yml`. All settings can be overridden by environment variables:

| Setting | Env Var | Description | Default |
|---------|---------|-------------|----------|
| `ynab.api_token` | `YNAB_API_TOKEN` | Your YNAB API token (required) | — |
| `ynab.budget_id` | `YNAB_BUDGET_ID` | Budget ID or "last-used" | `last-used` |
| `import.account_id` | `IMPORT_ACCOUNT_ID` | Default account to import into | `null` (must specify via CLI) |
| `import.dry_run` | `IMPORT_DRY_RUN` | Preview transactions without sending | `false` |
| `import.max_batch_size` | `IMPORT_MAX_BATCH_SIZE` | Max transactions per API request | `1000` |

**Priority order (highest to lowest):**
1. Command-line arguments (e.g., `--account-id`, `--dry-run`)
2. Environment variables (e.g., `YNAB_API_TOKEN`)
3. `config.yml` settings
4. Built-in defaults

---

## How It Works

- Automatically detects and skips junk header rows in ICICI exports
- Handles Indian number formatting (e.g. `1,23,456.78`)
- Converts separate Debit/Credit columns to YNAB's signed milliunit format
- Generates stable `import_id` values per transaction — re-importing the same file will **not** create duplicates
- Chunks large statements into batches (respects YNAB API limit per request)

## Amount Format

YNAB stores amounts in **milliunits** (1/1000th of a currency unit):

| Transaction | Amount (₹) | Milliunits |
|-------------|------------|------------|
| Debit ₹500  | -500.00    | -500000    |
| Credit ₹1,200 | +1200.00 | +1200000   |

## Project Structure

```
ynab-india-import/
├── config.py             # Configuration management module
├── config.yml            # Configuration file (create from template)
├── icici_to_ynab.py      # ICICI importer
├── main.py               # Simple example
├── requirements.txt      # Python dependencies
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## Environment Variable Setup (Production)

For CI/CD or production environments, set environment variables instead of config.yml:

```bash
# Linux/macOS
export YNAB_API_TOKEN="your_token_here"
export YNAB_BUDGET_ID="last-used"
export IMPORT_ACCOUNT_ID="your-account-uuid"
export IMPORT_DRY_RUN="false"

# Windows PowerShell
$env:YNAB_API_TOKEN = "your_token_here"
$env:YNAB_BUDGET_ID = "last-used"
```

## Contributing

PRs welcome — especially for other Indian banks (HDFC, SBI, Axis, Kotak).
Each bank tends to have its own quirky export format, so a new parser function
in the same pattern is all that's needed.

## License

MIT
