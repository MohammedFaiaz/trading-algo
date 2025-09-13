from logger import logger
import pandas as pd

class CandleProcessor:
    """
    Processes incoming WebSocket messages to identify, parse, and dispatch candlestick data.
    """

    def __init__(self, dispatcher):
        """
        Initializes the CandleProcessor.

        Args:
            dispatcher: An instance of the DataDispatcher class.
        """
        self.dispatcher = dispatcher
        logger.info("CandleProcessor initialized.")

    def process_message(self, message):
        """
        Processes a single message from the WebSocket feed.
        If the message contains candlestick data, it parses it and dispatches it.

        Args:
            message (dict): The message received from the Upstox WebSocket.
        """
        try:
            # The Upstox SDK returns a dictionary. We need to find the candle data within it.
            # Based on observing sample data, the candle data is in a nested dictionary.
            # The structure might be something like message['data']['candles']
            # We will assume a structure and adjust if needed after seeing live data.

            # The SDK might decode the protobuf into a structure. Let's assume it has 'feeds'
            if 'feeds' in message:
                for instrument_key, feed_data in message['feeds'].items():
                    # Check for OHLC data which indicates a candle
                    if 'ohlc' in feed_data:
                        candle_data = feed_data['ohlc']['candles'][0] # Assuming it's a list

                        # We have a candle. Let's structure it and dispatch it.
                        processed_candle = {
                            'instrument_key': instrument_key,
                            'interval': candle_data['interval'],
                            'open': float(candle_data['open']),
                            'high': float(candle_data['high']),
                            'low': float(candle_data['low']),
                            'close': float(candle_data['close']),
                            'volume': int(candle_data['volume']),
                            'timestamp': pd.to_datetime(candle_data['ts'], unit='ms', utc=True)
                        }

                        logger.debug(f"Dispatching candle for {instrument_key}: {processed_candle}")
                        self.dispatcher.dispatch(processed_candle)

            # The strategy will also need live ticks to check for breach of high/low.
            # We can also dispatch the Last Traded Price (LTP).
            if 'ltpc' in message:
                 ltp_data = message['ltpc']
                 processed_ltp = {
                     'type': 'ltp',
                     'instrument_key': ltp_data['instrument_token'],
                     'ltp': float(ltp_data['last_price'])
                 }
                 self.dispatcher.dispatch(processed_ltp)


        except KeyError as e:
            # This is not an error, just means the message was not a candle.
            logger.debug(f"Received non-candle or non-LTP message type. Key not found: {e}")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
            logger.error(f"Problematic message: {message}")
