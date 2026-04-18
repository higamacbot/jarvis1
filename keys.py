import os

# Retrieve Alpaca credentials from environment variables
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')

# Example usage: print the credentials (remove this line in production)
print(f"API Key: {ALPACA_API_KEY}")
print(f"Secret Key: {ALPACA_SECRET_KEY}")