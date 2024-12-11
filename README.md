# Simple PFT Node

A minimal implementation of a Post Fiat Token (PFT) node that monitors and responds to PFT transactions on the XRPL network. When it receives a PFT transaction with a memo, it analyzes the memo using GPT and sends back a response.

## Prerequisites

- Python 3.11+
- OpenAI API key
- XRPL wallet seed (funded with XRP and trust line set up for PFT)
- 15+ XRP for wallet activation and trust line

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following configuration:
```bash
OPENAI_API_KEY=your_openai_api_key_here
RIPPLED_URL=wss://s2.ripple.com  # Optional, defaults to public node if not specified
NODE_WALLET_SEED=your_wallet_seed_here  # Your funded XRPL wallet seed
```

## Core Features

1. **XRPL Connectivity**
   - Automatic connection to XRPL network (local node, specified node, or public node)
   - Fallback mechanism for reliable connectivity

2. **Transaction Monitoring**
   - Real-time monitoring of incoming PFT transactions
   - Memo parsing and analysis
   - Automatic response generation using GPT

3. **Response System**
   - Automated responses to PFT transactions
   - GPT-powered memo analysis
   - Transaction deduplication to prevent double responses

## Usage

Run the monitoring script:
```bash
python monitor.py
```

The node will:
1. Connect to the XRPL network
2. Start monitoring for incoming PFT transactions
3. When a PFT transaction with a memo is received:
   - Parse and analyze the memo using GPT
   - Send back 1 PFT with the analysis as a response memo

To interact with the node:
1. Send 1 PFT to the node's address
2. Include a memo with your message
3. Wait for the response transaction with GPT's analysis

## Environment Setup Notes

1. **Wallet Requirements**:
   - Your wallet must be funded with XRP (minimum 15 XRP for reserve)
   - A trust line must be set up for PFT
   - The wallet seed in .env must be the base58-encoded seed string (starts with 's')

2. **API Keys**:
   - OpenAI API key must have sufficient credits
   - Store API keys securely and never commit them to version control

## Security Notes

1. Never share your wallet seed
2. Keep your .env file secure and never commit it to version control
3. Maintain sufficient XRP balance for operations
4. Monitor your OpenAI API usage

## Troubleshooting

1. **Connection Issues**:
   - The node will automatically try local RippleD first
   - Then attempt to use the specified RIPPLED_URL
   - Finally fall back to public node if needed

2. **Wallet Issues**:
   - Ensure wallet seed is properly formatted (base58-encoded)
   - Verify wallet is funded and trust line is set up
   - Check for sufficient XRP balance

## License

MIT License - See LICENSE file for details. 