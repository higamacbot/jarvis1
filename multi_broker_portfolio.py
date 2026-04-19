#!/usr/bin/env python3
"""
Multi-Broker Portfolio Tracker
Tracks all investments across Webull, Robinhood, Coinbase, Acorns, and paper trading
"""

import json
from datetime import datetime

class MultiBrokerPortfolio:
    def __init__(self):
        self.portfolio_data = {
            "webull": {
                "stocks": {
                    "META": {"qty": None, "price": 688.55, "value": 183.01, "pl": 123.01, "pl_pct": 1.73},
                    "NFLX": {"qty": None, "price": 97.31, "value": 154.99, "pl": 94.99, "pl_pct": -9.72},
                    "AMD": {"qty": None, "price": 278.39, "value": 154.63, "pl": 94.63, "pl_pct": 0.05},
                    "NVDA": {"qty": None, "price": 201.68, "value": 57.52, "pl": 6.81, "pl_pct": 1.68},
                    "TSLA": {"qty": None, "price": 400.62, "value": 33.53, "pl": 8.53, "pl_pct": 3.01},
                    "PYPL": {"qty": None, "price": 50.81, "value": 25.89, "pl": -34.10, "pl_pct": 2.01}
                },
                "crypto": {
                    "BTC": {"qty": None, "price": 75843.847, "value": 140.07, "pl": 56.46, "pl_pct": 0.25},
                    "ETH": {"qty": None, "price": 2358.70, "value": 74.31, "pl": -25.69, "pl_pct": 0.38},
                    "SHIBxM": {"qty": None, "price": 6.09, "value": 10.43, "pl": -39.57, "pl_pct": 0.33}
                },
                "cash": 0.44,
                "total_value": 834.81
            },
            "robinhood": {
                "stocks": {
                    "VOO": {"qty": None, "price": None, "value": 234.44, "pl": None, "pl_pct": None},
                    "TSLA": {"qty": None, "price": None, "value": 29.87, "pl": None, "pl_pct": None}
                },
                "cash": 9.54,
                "total_value": 273.85,
                "total_pl": 19.28,
                "total_pl_pct": 7.57
            },
            "coinbase": {
                "crypto": {
                    "SOL": {"qty": None, "price": None, "value": 189.61, "pl": -44.38, "pl_pct": -18.97},
                    "BNB": {"qty": None, "price": None, "value": 37.65, "pl": -12.47, "pl_pct": -24.88},
                    "XRP": {"qty": None, "price": None, "value": 5.08, "pl": -1.55, "pl_pct": -23.38}
                },
                "total_value": 232.36,
                "daily_pl": -7.32,
                "daily_pl_pct": -3.05
            },
            "acorns": {
                "invest": 136.16,
                "ira": 318.20,
                "total_value": 454.36,
                "monthly_contribution": 5
            },
            "other": {
                "pi_network": {"amount": 52.66753, "value": None},
                "bee_network": {"amount": 595.7274, "value": None}
            },
            "paper_trading": {
                "alpaca": {
                    "stocks": {
                        "AMD": {"qty": 0.5557, "value": 154.70, "pl": 25.71},
                        "META": {"qty": 0.2658, "value": 183.02, "pl": 21.94},
                        "NFLX": {"qty": 1.5934, "value": 155.05, "pl": -2.71},
                        "NVDA": {"qty": 0.2852, "value": 57.52, "pl": 4.90},
                        "PYPL": {"qty": 0.5094, "value": 25.88, "pl": 2.46},
                        "TSLA": {"qty": 0.1581, "value": 63.34, "pl": 5.79},
                        "VOO": {"qty": 0.3587, "value": 234.15, "pl": 11.02}
                    },
                    "equity": 1801.29,
                    "buying_power": 6.37
                },
                "kraken": {
                    "crypto": {
                        "DOGE": {"qty": 100, "value": 9.49, "pl": -0.03}
                    },
                    "equity": 99.97
                }
            }
        }
    
    def get_total_portfolio_value(self):
        """Calculate total value across all accounts"""
        total = 0
        total += self.portfolio_data["webull"]["total_value"]
        total += self.portfolio_data["robinhood"]["total_value"]
        total += self.portfolio_data["coinbase"]["total_value"]
        total += self.portfolio_data["acorns"]["total_value"]
        total += self.portfolio_data["paper_trading"]["alpaca"]["equity"]
        total += self.portfolio_data["paper_trading"]["kraken"]["equity"]
        return total
    
    def get_all_stocks(self):
        """Get all stock positions across brokers"""
        all_stocks = {}
        
        # Webull stocks
        for symbol, data in self.portfolio_data["webull"]["stocks"].items():
            all_stocks[symbol] = {**data, "broker": "webull"}
        
        # Robinhood stocks
        for symbol, data in self.portfolio_data["robinhood"]["stocks"].items():
            if symbol in all_stocks:
                # Combine positions if same symbol across brokers
                all_stocks[symbol]["value"] += data["value"]
                all_stocks[symbol]["broker"] += ", robinhood"
            else:
                all_stocks[symbol] = {**data, "broker": "robinhood"}
        
        # Alpaca paper stocks
        for symbol, data in self.portfolio_data["paper_trading"]["alpaca"]["stocks"].items():
            if symbol in all_stocks:
                all_stocks[symbol]["value"] += data["value"]
                all_stocks[symbol]["broker"] += ", alpaca_paper"
            else:
                all_stocks[symbol] = {**data, "broker": "alpaca_paper"}
        
        return all_stocks
    
    def get_all_crypto(self):
        """Get all crypto positions across brokers"""
        all_crypto = {}
        
        # Webull crypto
        for symbol, data in self.portfolio_data["webull"]["crypto"].items():
            all_crypto[symbol] = {**data, "broker": "webull"}
        
        # Coinbase crypto
        for symbol, data in self.portfolio_data["coinbase"]["crypto"].items():
            if symbol in all_crypto:
                all_crypto[symbol]["value"] += data["value"]
                all_crypto[symbol]["broker"] += ", coinbase"
            else:
                all_crypto[symbol] = {**data, "broker": "coinbase"}
        
        # Kraken paper crypto
        for symbol, data in self.portfolio_data["paper_trading"]["kraken"]["crypto"].items():
            if symbol in all_crypto:
                all_crypto[symbol]["value"] += data["value"]
                all_crypto[symbol]["broker"] += ", kraken_paper"
            else:
                all_crypto[symbol] = {**data, "broker": "kraken_paper"}
        
        return all_crypto
    
    def generate_portfolio_summary(self):
        """Generate comprehensive portfolio summary"""
        total_value = self.get_total_portfolio_value()
        all_stocks = self.get_all_stocks()
        all_crypto = self.get_all_crypto()
        
        summary = f"""
{'='*80}
ð COMPLETE MULTI-BROKER PORTFOLIO SUMMARY
{datetime.now().strftime('%B %d, %Y â %I:%M %p CST')}
{'='*80}

TOTAL PORTFOLIO VALUE: ${total_value:,.2f}

{'='*80}
ð BROKER BREAKDOWN
{'='*80}

Webull: ${self.portfolio_data['webull']['total_value']:,.2f}
  - Stocks: ${sum(s['value'] for s in self.portfolio_data['webull']['stocks'].values()):,.2f}
  - Crypto: ${sum(c['value'] for c in self.portfolio_data['webull']['crypto'].values()):,.2f}
  - Cash: ${self.portfolio_data['webull']['cash']:.2f}

Robinhood: ${self.portfolio_data['robinhood']['total_value']:,.2f} (+{self.portfolio_data['robinhood']['total_pl_pct']:.2f}%)
  - Stocks: ${sum(s['value'] for s in self.portfolio_data['robinhood']['stocks'].values()):,.2f}
  - Cash: ${self.portfolio_data['robinhood']['cash']:.2f}

Coinbase: ${self.portfolio_data['coinbase']['total_value']:,.2f} ({self.portfolio_data['coinbase']['daily_pl_pct']:+.2f}% today)
  - Crypto: ${sum(c['value'] for c in self.portfolio_data['coinbase']['crypto'].values()):,.2f}

Acorns: ${self.portfolio_data['acorns']['total_value']:,.2f}
  - Invest: ${self.portfolio_data['acorns']['invest']:,.2f}
  - IRA: ${self.portfolio_data['acorns']['ira']:,.2f}

Paper Trading: ${self.portfolio_data['paper_trading']['alpaca']['equity'] + self.portfolio_data['paper_trading']['kraken']['equity']:,.2f}
  - Alpaca: ${self.portfolio_data['paper_trading']['alpaca']['equity']:,.2f}
  - Kraken: ${self.portfolio_data['paper_trading']['kraken']['equity']:,.2f}

{'='*80}
ð ALL STOCK POSITIONS
{'='*80}
"""
        
        for symbol, data in sorted(all_stocks.items(), key=lambda x: x[1]['value'], reverse=True):
            emoji = "ð" if (data.get('pl', 0) or 0) >= 0 else "ð"
            pl_info = f"P/L: ${data.get('pl', 0):+,.2f}" if data.get('pl') is not None else "P/L: N/A"
            summary += f"{emoji} {symbol}: ${data['value']:,.2f} | {pl_info} | Broker: {data['broker']}\n"
        
        summary += f"""
{'='*80}
ð ALL CRYPTO POSITIONS
{'='*80}
"""
        
        for symbol, data in sorted(all_crypto.items(), key=lambda x: x[1]['value'], reverse=True):
            emoji = "ð" if (data.get('pl', 0) or 0) >= 0 else "ð"
            pl_info = f"P/L: ${data.get('pl', 0):+,.2f}" if data.get('pl') is not None else "P/L: N/A"
            summary += f"{emoji} {symbol}: ${data['value']:,.2f} | {pl_info} | Broker: {data['broker']}\n"
        
        summary += f"""
{'='*80}
OTHER ASSETS
{'='*80}
Pi Network: {self.portfolio_data['other']['pi_network']['amount']} ð
Bee Network: {self.portfolio_data['other']['bee_network']['amount']} BEE

{'='*80}
Portfolio summary complete. Standing by, sir.
{'='*80}
"""
        
        return summary

if __name__ == "__main__":
    portfolio = MultiBrokerPortfolio()
    print(portfolio.generate_portfolio_summary())
