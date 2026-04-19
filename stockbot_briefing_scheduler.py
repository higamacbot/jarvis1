#!/usr/bin/env python3
"""
HIGA HOUSE Briefing Scheduler
5 AM and 5 PM automated briefings from Stockbot and Cryptoid
Both bots generate reports and send to J.A.R.V.I.S.
"""

import asyncio
import time
import schedule
from bots.stockbot import generate_briefing as stockbot_briefing
from bots.cryptoid import generate_crypto_briefing as cryptoid_briefing

async def combined_morning_briefing():
    """5 AM combined briefing from both bots"""
    print("\n>> HIGA HOUSE MORNING BRIEFING INITIATED")
    print("=" * 60)
    
    # Generate Stockbot briefing
    print(">> STOCKBOT: Generating portfolio briefing...")
    stockbot_report = await stockbot_briefing("morning")
    
    # Generate Cryptoid briefing  
    print(">> CRYPTOID: Generating crypto briefing...")
    cryptoid_report = await cryptoid_briefing()
    
    # Get timestamp from Stockbot report
    timestamp_line = stockbot_report.split('\n')[1] if '\n' in stockbot_report else ''
    
    # Combine reports
    separator = '=' * 60
    combined_briefing = f"""
{separator}
ð J.A.R.V.I.S. MORNING BRIEFING
{timestamp_line}
{separator}

{stockbot_report}

{separator}
{cryptoid_report}

{separator}
MORNING BRIEFING COMPLETE. Standing by, sir.
{separator}
"""
    
    print("\n" + combined_briefing)
    return combined_briefing

async def combined_evening_briefing():
    """5 PM combined briefing from both bots"""
    print("\n>> HIGA HOUSE EVENING BRIEFING INITIATED")
    print("=" * 60)
    
    # Generate Stockbot briefing
    print(">> STOCKBOT: Generating portfolio briefing...")
    stockbot_report = await stockbot_briefing("evening")
    
    # Generate Cryptoid briefing
    print(">> CRYPTOID: Generating crypto briefing...")
    cryptoid_report = await cryptoid_briefing()
    
    # Get timestamp from Stockbot report
    timestamp_line = stockbot_report.split('\n')[1] if '\n' in stockbot_report else ''
    
    # Combine reports
    separator = '=' * 60
    combined_briefing = f"""
{separator}
ð J.A.R.V.I.S. EVENING BRIEFING
{timestamp_line}
{separator}

{stockbot_report}

{separator}
{cryptoid_report}

{separator}
EVENING BRIEFING COMPLETE. Standing by, sir.
{separator}
"""
    
    print("\n" + combined_briefing)
    return combined_briefing

def morning_briefing():
    """Schedule morning briefing"""
    asyncio.run(combined_morning_briefing())

def evening_briefing():
    """Schedule evening briefing"""
    asyncio.run(combined_evening_briefing())

def main():
    print(">> HIGA HOUSE BRIEFING SYSTEM ONLINE")
    print(">> Stockbot + Cryptoid will generate combined briefings at 5 AM and 5 PM")
    print(">> Briefings include portfolio analysis, crypto insights, and trade reports")
    print(">> All reports delivered through J.A.R.V.I.S. interface")
    print("=" * 80)
    
    # Schedule combined briefings
    schedule.every().day.at("05:00").do(morning_briefing)
    schedule.every().day.at("17:00").do(evening_briefing)
    
    print(">> Waiting for scheduled briefings...")
    print(">> Next briefing: " + str(schedule.next_run()))
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
