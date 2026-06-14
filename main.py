"""
Simple YNAB Transaction Example
================================

Demonstrates how to use the config system with the YNAB API.
Edit config.yml with your API token before running.
"""

import requests
from config import load_config, ConfigError


def main():
    try:
        config = load_config()
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")
        return 1

    headers = {"Authorization": f"Bearer {config.ynab_api_token}"}

    # Example transaction
    transactions = [
        {
            "account_id": "your-account-uuid",
            "date": "2026-06-14",
            "amount": -42500,        # -$42.50 (negative = outflow)
            "payee_name": "Whole Foods",
            "memo": "Groceries",
            "cleared": "cleared"
        }
    ]

    print(f"📤 Sending {len(transactions)} transaction(s) to YNAB...")
    print(f"   Budget: {config.ynab_budget_id}")

    response = requests.post(
        f"{config.ynab_base_url}/transactions",
        headers=headers,
        json={"transactions": transactions}
    )

    if response.ok:
        print(f"✅ Success!")
        print(response.json())
    else:
        print(f"✗ API error {response.status_code}: {response.text}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
