import requests

API_TOKEN = "your_token_here"
BUDGET_ID = "last-used"
BASE_URL = f"https://api.youneedabudget.com/v1/budgets/{BUDGET_ID}"

headers = {"Authorization": f"Bearer {API_TOKEN}"}

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

response = requests.post(
    f"{BASE_URL}/transactions",
    headers=headers,
    json={"transactions": transactions}
)
print(response.json())