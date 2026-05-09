import os
import pyotp
import pandas as pd
from dotenv import load_dotenv
from SmartApi import SmartConnect
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AngelOneExtractor:
    def __init__(self):
        # Path to secrets relative to this script
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        load_dotenv(os.path.join(base_dir, "secrets", ".env"))
        
        self.api_key = os.getenv("ANGEL_ONE_API_KEY")
        self.client_id = os.getenv("ANGEL_ONE_CLIENT_ID")
        self.password = os.getenv("ANGEL_ONE_PIN")
        self.totp_secret = os.getenv("ANGEL_ONE_TOTP_SECRET")
        self.smart_api = None

    def login(self):
        """Automated login using TOTP"""
        try:
            self.smart_api = SmartConnect(api_key=self.api_key)
            token = pyotp.TOTP(self.totp_secret).now()
            res = self.smart_api.generateSession(self.client_id, self.password, token)
            
            if res['status']:
                logger.info("Successfully authenticated with Angel One.")
                return True
            else:
                logger.error(f"Login failed: {res['message']}")
                return False
        except Exception as e:
            logger.error(f"Auth Error: {e}")
            return False

    def fetch_and_save_holdings(self):
        """Gets holdings, converts to DataFrame, and saves to CSV"""
        if not self.smart_api:
            if not self.login(): return

        try:
            holdings_res = self.smart_api.holding()
            
            if holdings_res['status'] and holdings_res['data']:
                df = pd.DataFrame(holdings_res['data'])
                
                # Selecting core columns for your 'Exit Sentinel' logic
                # Note: Field names might vary slightly by API version, 
                # but these are standard for SmartAPI 2.0
                cols_to_keep = ['tradingsymbol', 'isin', 'quantity', 'averageprice', 'ltp', 'profitandloss']
                df = df[cols_to_keep]
                
                # Standardizing column names for your future unified DB
                df.columns = ['ticker', 'isin', 'quantity', 'avg_price', 'current_price', 'pnl']
                df['broker'] = 'Angel One'
                df['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Ensure data folder exists
                os.makedirs("data", exist_ok=True)
                
                # Save as a daily snapshot
                filename = f"data/holdings_angel_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename, index=False)
                
                logger.info(f"Successfully saved {len(df)} stocks to {filename}")
                return df
            else:
                logger.warning("No holdings found or API error.")
        except Exception as e:
            logger.error(f"Extraction Error: {e}")

if __name__ == "__main__":
    extractor = AngelOneExtractor()
    holdings = extractor.fetch_and_save_holdings()
    if holdings is not None:
        print("\n--- Top 5 Holdings (by P&L) ---")
        print(holdings.sort_values(by='pnl', ascending=True).head(5))