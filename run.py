import yaml
import threading
from queue import Queue

from logger import logger
from brokers.upstox import UpstoxBroker
from dispatcher import DataDispatcher
from orders import OrderTracker
from data_processor import CandleProcessor
from strategy.scalping_strategy import ScalpingStrategy

def main():
    """
    Main function to run the trading bot.
    """
    logger.info("--- Starting Trading Bot ---")

    # 1. Load Configuration
    config_file = 'strategy/configs/scalping.yml'
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from {config_file}")
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_file}. Exiting.")
        return
    except Exception as e:
        logger.error(f"Error loading configuration: {e}", exc_info=True)
        return

    # 2. Initialize Core Components
    broker = UpstoxBroker()
    dispatcher = DataDispatcher()
    order_tracker = OrderTracker() # Assuming default file path for orders

    # Register a queue with the dispatcher
    data_queue = Queue()
    dispatcher.register_main_queue(data_queue)

    # Initialize the data processor
    candle_processor = CandleProcessor(dispatcher)

    # 3. Handle Authentication
    try:
        # The authenticate method now returns the message for the user
        auth_message = broker.authenticate()
        print("\n" + "="*80)
        print("AUTHENTICATION REQUIRED")
        print("="*80)
        print(auth_message)
        print("="*80)

        # Prompt user for the authorization code
        auth_code = input("Please paste the authorization code here: ")

        if not auth_code:
            logger.error("Authorization code not provided. Exiting.")
            return

        broker.set_access_token(auth_code)

        # Verify authentication
        profile = broker.get_profile()
        if profile and profile.data:
            logger.info(f"Authentication successful for user: {profile.data.user_name}")
        else:
            logger.error("Authentication failed. Could not fetch profile. Exiting.")
            return

    except Exception as e:
        logger.error(f"An error occurred during authentication: {e}", exc_info=True)
        return

    # 4. Initialize the Strategy
    strategy = ScalpingStrategy(
        broker=broker,
        dispatcher=dispatcher,
        order_tracker=order_tracker,
        config=config
    )

    # 5. Start the Strategy in a separate thread
    strategy_thread = threading.Thread(target=strategy.start, daemon=True)
    strategy_thread.start()
    logger.info("Strategy thread started.")

    # 6. Connect to the WebSocket (this is a blocking call, so it runs in the main thread)
    instruments_to_trade = config.get('instruments', [])
    if not instruments_to_trade:
        logger.error("No instruments to trade found in configuration. Exiting.")
        return

    logger.info(f"Connecting to WebSocket for instruments: {instruments_to_trade}")
    # The on_message_callback will be the candle_processor's method
    broker.connect_websocket(
        instrument_keys=instruments_to_trade,
        on_message_callback=candle_processor.process_message
    )

    # The script will keep running here as streamer.connect() is blocking.
    # To stop the bot, the user can press Ctrl+C.
    logger.info("--- Trading Bot Shutdown ---")


if __name__ == "__main__":
    main()
