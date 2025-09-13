from brokers.upstox import UpstoxBroker

def run_authentication():
    """
    Tests the first step of the Upstox authentication process.
    """
    print("Initializing Upstox broker...")
    try:
        broker = UpstoxBroker()
        auth_message = broker.authenticate()
        print("\n" + "="*80)
        print("AUTHENTICATION REQUIRED")
        print("="*80)
        print(auth_message)
        print("="*80)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_authentication()
