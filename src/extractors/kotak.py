import os
import pyotp
import pandas as pd
from dotenv import load_dotenv
from neo_api_client import NeoAPI
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KotakNeoExtractor:
    def __init__(self):
        # Resolve the path to the .env file dynamically
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        load_dotenv(os.path.join(base_dir, "secrets", ".env"))
        
        self.consumer_key = os.getenv("KOTAK_API_KEY")
        self.ucc = os.getenv("KOTAK_UCC")
        self.mobile = os.getenv("KOTAK_MOBILE")
        self.mpin = os.getenv("KOTAK_MPIN")
        self.totp_secret = os.getenv("KOTAK_TOTP_SECRET")
        self.client = None

    def login(self):
        """Automated two-step login using TOTP and MPIN with Debugging"""
        try:
            self.client = NeoAPI(environment='prod', consumer_key=self.consumer_key)
            totp_code = pyotp.TOTP(self.totp_secret).now()
            
            print(f"\n--- ATTEMPTING KOTAK LOGIN ---")
            print(f"Using UCC: {self.ucc} | Mobile: {self.mobile}")
            
            # Step 1: Session Login
            login_res = self.client.totp_login(mobile_number=self.mobile, ucc=self.ucc, totp=totp_code)
            print("STEP 1 (TOTP) RESPONSE:", login_res)
            
            # Step 2: Validate MPIN
            val_res = self.client.totp_validate(mpin=self.mpin)
            print("STEP 2 (MPIN) RESPONSE:", val_res)
            
            # Check if token generation actually succeeded
            if val_res and 'data' in val_res and 'token' in val_res['data']:
                logger.info("✅ Successfully authenticated with Kotak Neo.")
                return True
            else:
                logger.error("❌ Authentication failed. Did not receive trade tokens.")
                return False
                
        except Exception as e:
            logger.error(f"Auth Error: {e}")
            return False

    def fetch_and_save_holdings(self):
        """Fetches Kotak holdings and transforms them to match the standard schema"""
        if not self.client:
            if not self.login(): return None

        try:
            res = self.client.holdings()
            
            if 'data' in res and res['data']:
                df = pd.DataFrame(res['data'])
                
                # Data Transformation: Calculate missing fields to match Angel One
                df['current_price'] = df['mktValue'] / df['quantity']
                df['pnl'] = df['mktValue'] - df['holdingCost']
                df['isin'] = "N/A" # Kotak API may not expose ISIN in this endpoint
                
                # Rename Kotak's columns to our unified schema
                df.rename(columns={
                    'displaySymbol': 'ticker',
                    'averagePrice': 'avg_price',
                }, inplace=True)
                
                # Filter down to the core columns
                cols_to_keep = ['ticker', 'isin', 'quantity', 'avg_price', 'current_price', 'pnl']
                df = df[cols_to_keep]
                
                df['broker'] = 'Kotak Neo'
                df['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Save the snapshot
                os.makedirs("data", exist_ok=True)
                filename = f"data/holdings_kotak_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename, index=False)
                
                logger.info(f"Successfully saved {len(df)} stocks to {filename}")
                return df
            else:
                logger.warning("No holdings found or API error.")
        except Exception as e:
            logger.error(f"Extraction Error: {e}")

if __name__ == "__main__":
    extractor = KotakNeoExtractor()
    holdings = extractor.fetch_and_save_holdings()
    
    if holdings is not None and not holdings.empty:
        print("\n--- Top 5 Holdings (by P&L) ---")
        print(holdings.sort_values(by='pnl', ascending=True).head(5))