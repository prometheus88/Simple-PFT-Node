from pft_node import SimplePFTNode
import time
import os
from dotenv import load_dotenv

def main():
    # Initialize the node with monitoring capabilities
    print("\n1. Starting PFT Node...")
    
    # Debug: Print environment variable
    load_dotenv()
    seed = os.getenv('NODE_WALLET_SEED')
    print(f"Debug - Raw seed value: '{seed}'")
    print(f"Debug - Seed length: {len(seed) if seed else 'None'}")
    print(f"Debug - Seed characters: {[ord(c) for c in seed] if seed else 'None'}")
    
    node = SimplePFTNode()
    
    # Start monitoring for incoming transactions
    print("\n2. Starting transaction monitoring...")
    node.start_monitoring()
    print(f"\nNode wallet address: {node.node_address}")
    print("\nMonitoring for incoming PFT transactions with memos...")
    print("Send 1 PFT with a memo to this address and you'll receive a response with GPT's analysis.")
    print("\nPress Ctrl+C to stop monitoring...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
        node.stop_monitoring()
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        node.stop_monitoring()

if __name__ == "__main__":
    main() 