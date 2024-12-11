import os
from dotenv import load_dotenv
import xrpl
from xrpl.clients import JsonRpcClient, WebsocketClient
from xrpl.models.transactions import Payment, TrustSet
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountTx, Subscribe
import openai
from datetime import datetime
import time
import threading
import json

class SimplePFTNode:
    def __init__(self, rippled_url=None, node_seed=None):
        """Initialize a simple PFT node."""
        load_dotenv()  # Load environment variables
        
        # XRPL configuration
        self.local_url = 'http://127.0.0.1:5005'  # Default local RippleD
        self.public_url = 'wss://s2.ripple.com'   # Fallback public node
        
        # Try local first, then fallback to specified URL or public
        self.rippled_url = self._get_rippled_url(rippled_url)
        self.client = None
        self._connect()
        
        self.pft_issuer = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"  # PFT token issuer
        
        # Node wallet configuration - add debug logging
        self.node_seed = node_seed if node_seed else os.getenv('NODE_WALLET_SEED')
        print(f"Debug - Seed length: {len(self.node_seed) if self.node_seed else 'None'}")
        print(f"Debug - Seed characters: {[ord(c) for c in self.node_seed] if self.node_seed else 'None'}")
        
        if self.node_seed:
            # Strip any whitespace
            self.node_seed = self.node_seed.strip()
            self.node_wallet = Wallet.from_seed(self.node_seed)
            self.node_address = self.node_wallet.classic_address
        
        # OpenAI configuration
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Transaction monitoring
        self.stop_monitoring = False
        self.monitoring_thread = None
        self.start_ledger = None  # Track when monitoring begins
        self.responded_to = set()  # Track which transactions we've responded to

    def _get_rippled_url(self, specified_url=None):
        """Try local connection first, then fall back to specified URL or public node."""
        # Try local connection first
        try:
            print(f"Attempting to connect to local RippleD at {self.local_url}")
            client = JsonRpcClient(self.local_url)
            client.request(xrpl.models.requests.ServerInfo())
            print("Successfully connected to local RippleD")
            return self.local_url
        except Exception as e:
            print(f"Could not connect to local RippleD: {str(e)}")
        
        # If local fails, try specified URL from env or parameter
        if specified_url or os.getenv('RIPPLED_URL'):
            try:
                url = specified_url or os.getenv('RIPPLED_URL')
                print(f"Attempting to connect to specified RippleD at {url}")
                if url.startswith('wss://'):
                    client = WebsocketClient(url)
                else:
                    client = JsonRpcClient(url)
                client.request(xrpl.models.requests.ServerInfo())
                print(f"Successfully connected to specified RippleD at {url}")
                return url
            except Exception as e:
                print(f"Could not connect to specified RippleD: {str(e)}")
        
        # Fallback to public node
        print(f"Falling back to public XRPL node at {self.public_url}")
        return self.public_url

    def _connect(self):
        """Establish connection to XRPL."""
        if self.client:
            try:
                self.client.close()
            except:
                pass
        
        if self.rippled_url.startswith('wss://'):
            self.client = WebsocketClient(self.rippled_url)
            self.client.open()
        else:
            self.client = JsonRpcClient(self.rippled_url)
        
        print(f"Connected to {self.rippled_url}")

    def _process_transaction(self, tx):
        """Process a single transaction."""
        try:
            if not isinstance(tx, dict):
                return
                
            # Get the transaction data
            tx_data = tx.get('tx_json', tx.get('transaction', {}))
            if not tx_data:
                return
                
            # Check if it's a Payment
            if tx_data.get('TransactionType') != 'Payment':
                return
                
            # Check if it's a PFT payment - check both Amount and DeliverMax
            amount = tx_data.get('DeliverMax', tx_data.get('Amount', {}))
            if not isinstance(amount, dict):
                return
                
            if amount.get('currency') != 'PFT' or amount.get('issuer') != self.pft_issuer:
                return
                
            # Check for memos
            memos = tx_data.get('Memos', [])
            if not memos:
                return
                
            print(f"\nProcessing PFT transaction: {json.dumps(tx_data, indent=2)}")
            
            # Process memos
            for memo in memos:
                try:
                    memo_data = memo.get('Memo', {}).get('MemoData', '')
                    if not memo_data:
                        continue
                        
                    memo_text = xrpl.utils.hex_to_str(memo_data)
                    print(f"\nReceived memo: {memo_text}")
                    
                    # Analyze with GPT
                    print("Analyzing with GPT...")
                    analysis = self.parse_memo_with_llm(memo_text)
                    print(f"Analysis: {analysis}")
                    
                    # Send response if transaction was successful
                    meta = tx.get('meta', {})
                    if meta.get('TransactionResult') == 'tesSUCCESS':
                        sender = tx_data.get('Account')
                        # Get hash from the correct location in transaction data
                        tx_hash = tx.get('hash', tx_data.get('hash', ''))
                        
                        print(f"\nTransaction hash: {tx_hash}")
                        print(f"Already responded to: {tx_hash in self.responded_to}")
                        print(f"Current responded_to set: {self.responded_to}")
                        
                        # Only send a response if we haven't already responded to this transaction
                        if sender and tx_hash and tx_hash not in self.responded_to:
                            print(f"Sending response to {sender}")
                            response = self.send_pft(
                                from_seed=self.node_seed,
                                to_address=sender,
                                amount="1",
                                memo_text=f"Analysis: {analysis}"
                            )
                            print(f"Response sent! Hash: {response.result.get('hash', 'unknown')}")
                            self.responded_to.add(tx_hash)  # Mark that we've responded
                            print(f"Added {tx_hash} to responded_to set")
                        else:
                            print(f"Already responded to transaction {tx_hash}")
                            
                except Exception as e:
                    print(f"Error processing memo: {str(e)}")
                    
        except Exception as e:
            print(f"Error processing transaction: {str(e)}")
            print("Full error details:", e.__class__.__name__)

    def _monitor_transactions(self):
        """Monitor transactions using polling."""
        last_ledger = None
        
        # Get current ledger as starting point
        if self.start_ledger is None:
            try:
                request = AccountTx(
                    account=self.node_address,
                    ledger_index_min=-1,
                    ledger_index_max=-1
                )
                response = self.client.request(request)
                self.start_ledger = response.result.get('ledger_index_max')
                print(f"\nStarting monitoring from ledger {self.start_ledger}")
            except Exception as e:
                print(f"Error getting start ledger: {str(e)}")
                self.start_ledger = 0
        
        while not self.stop_monitoring:
            try:
                # Get latest transactions
                request = AccountTx(
                    account=self.node_address,
                    ledger_index_min=-1,
                    ledger_index_max=-1
                )
                
                response = self.client.request(request)
                current_ledger = response.result.get('ledger_index_max')
                
                # Only process if we have new transactions
                if current_ledger != last_ledger:
                    transactions = response.result.get('transactions', [])
                    print(f"\nChecking ledger {current_ledger}")
                    
                    for tx in transactions:
                        try:
                            # Get transaction data exactly as we see it in test_tx.py
                            tx_data = tx.get('tx', tx.get('tx_json', {}))
                            meta = tx.get('meta', {})
                            
                            # Only process transactions from ledgers after we started monitoring
                            tx_ledger = tx.get('ledger_index', 0)
                            if tx_ledger <= self.start_ledger:
                                continue
                                
                            # Process if it's a successful transaction
                            if meta.get('TransactionResult') == 'tesSUCCESS':
                                self._process_transaction(tx)
                            
                        except Exception as e:
                            print(f"Error processing transaction: {str(e)}")
                            print(f"Full error details: {e.__class__.__name__}")
                    
                    last_ledger = current_ledger
                
                time.sleep(1)  # Wait before checking again
                
            except Exception as e:
                print(f"Error in monitoring loop: {str(e)}")
                print(f"Full error details: {e.__class__.__name__}")
                time.sleep(5)
                try:
                    self._connect()
                except:
                    pass

    def start_monitoring(self):
        """Start monitoring for incoming transactions."""
        if not self.node_seed:
            raise ValueError("Node wallet seed is required for monitoring transactions")
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            print("Monitoring is already running")
            return
        
        self.stop_monitoring = False
        self.monitoring_thread = threading.Thread(target=self._monitor_transactions)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        print(f"Started monitoring transactions for node wallet: {self.node_address}")

    def stop_monitoring(self):
        """Stop monitoring for transactions."""
        self.stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join()
            print("Stopped monitoring transactions")

    def create_wallet(self):
        """Create a new XRP wallet."""
        wallet = Wallet.create()
        return {
            "address": wallet.classic_address,
            "seed": wallet.seed,
            "public_key": wallet.public_key,
            "private_key": wallet.private_key
        }
    
    def setup_trust_line(self, wallet_seed):
        """Set up PFT trust line for a wallet."""
        try:
            if not self.client.is_open():
                self._connect()
            
            wallet = Wallet.from_seed(wallet_seed)
            trust_set_tx = TrustSet(
                account=wallet.classic_address,
                limit_amount=IssuedCurrencyAmount(
                    currency="PFT",
                    issuer=self.pft_issuer,
                    value="100000000"
                )
            )
            return xrpl.transaction.submit_and_wait(trust_set_tx, self.client, wallet)
        except Exception as e:
            if "Websocket is not open" in str(e):
                self._connect()  # Try reconnecting
                return self.setup_trust_line(wallet_seed)  # Retry once
            raise
    
    def send_pft(self, from_seed, to_address, amount, memo_text):
        """Send PFT tokens with a memo."""
        wallet = Wallet.from_seed(from_seed)
        
        # Create memo object
        memo_data = {
            "timestamp": datetime.now().isoformat(),
            "text": memo_text
        }
        
        # Create payment with memo
        payment = Payment(
            account=wallet.classic_address,
            amount=IssuedCurrencyAmount(
                currency="PFT",
                issuer=self.pft_issuer,
                value=str(amount)
            ),
            destination=to_address,
            memos=[xrpl.models.transactions.Memo(
                memo_data=xrpl.utils.str_to_hex(str(memo_data))
            )]
        )
        
        return xrpl.transaction.submit_and_wait(payment, self.client, wallet)
    
    def get_account_transactions(self, address):
        """Get all transactions for an account."""
        request = AccountTx(account=address)
        return self.client.request(request)
    
    def parse_memo_with_llm(self, memo_text):
        """Parse memo text using OpenAI."""
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are analyzing PFT transaction memos. Extract key information and intentions from the memo."},
                {"role": "user", "content": f"Please analyze this memo: {memo_text}"}
            ]
        )
        return response.choices[0].message.content
    
    def process_transactions(self, address):
        """Process and analyze all PFT transactions for an address."""
        txns = self.get_account_transactions(address)
        processed_txns = []
        
        for tx in txns.result.get("transactions", []):
            if "memos" in tx["tx"]:
                for memo in tx["tx"]["memos"]:
                    memo_text = xrpl.utils.hex_to_str(memo["Memo"]["MemoData"])
                    analysis = self.parse_memo_with_llm(memo_text)
                    processed_txns.append({
                        "tx_hash": tx["tx"]["hash"],
                        "memo": memo_text,
                        "analysis": analysis
                    })
        
        return processed_txns 