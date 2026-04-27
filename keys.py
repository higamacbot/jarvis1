import os

# Retrieve Alpaca credentials from environment variables
ALPACA_KEY = os.getenv('ALPACA_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET')

# Keys loaded from environment — never print secrets to logs