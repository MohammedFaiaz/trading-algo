import pandas as pd
import pandas_ta as ta
from logger import logger

class ScalpingStrategy:
    """
    Implements the user-defined scalping strategy based on JMA, EMA, SMA, and ADX.
    """

    def __init__(self, broker, dispatcher, order_tracker, config):
        """
        Initializes the ScalpingStrategy.

        Args:
            broker: An instance of a broker class (e.g., UpstoxBroker).
            dispatcher: An instance of the DataDispatcher.
            order_tracker: An instance of the OrderTracker.
            config (dict): A dictionary containing strategy parameters.
        """
        self.broker = broker
        self.dispatcher = dispatcher
        self.order_tracker = order_tracker
        self.config = config

        # Data storage for each instrument
        self.instrument_data = {}

        logger.info("ScalpingStrategy initialized.")

    def _initialize_instrument_data(self, instrument_key):
        """Initializes data storage for a new instrument."""
        if instrument_key not in self.instrument_data:
            self.instrument_data[instrument_key] = {
                'candles': pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']),
                'signal': None,  # To store pending entry signals
                'active_trade': None # To store details of an open position
            }
            logger.info(f"Initialized data store for instrument: {instrument_key}")

    def start(self):
        """Starts the strategy's main loop to process data from the dispatcher."""
        logger.info("ScalpingStrategy started. Waiting for data...")
        while True:
            try:
                data = self.dispatcher._main_queue.get()
                if data:
                    self._process_data(data)
            except KeyboardInterrupt:
                logger.info("ScalpingStrategy stopped by user.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the strategy loop: {e}", exc_info=True)

    def _process_data(self, data):
        """
        Routes incoming data to the appropriate handler (candle or LTP).
        """
        instrument_key = data.get('instrument_key')
        if not instrument_key:
            return

        # Ensure data storage is initialized for the instrument
        self._initialize_instrument_data(instrument_key)

        if 'open' in data: # Heuristic to identify a candle
            self._handle_candle(data)
        elif data.get('type') == 'ltp':
            self._handle_ltp(data)

    def _handle_candle(self, candle):
        """
        Handles a new closed candle.
        Calculates indicators and checks for entry signals.
        """
        instrument_key = candle['instrument_key']
        logger.debug(f"Handling new candle for {instrument_key}")

        # Append new candle to the DataFrame
        new_candle_df = pd.DataFrame([candle])
        # Ensure timestamp is the index
        new_candle_df.set_index('timestamp', inplace=True)

        instrument_df = self.instrument_data[instrument_key]['candles']
        instrument_df = pd.concat([instrument_df, new_candle_df])

        # Prune old data to keep the DataFrame size manageable
        max_candles = self.config.get('max_candles', 200)
        if len(instrument_df) > max_candles:
            instrument_df = instrument_df.iloc[-max_candles:]

        # Calculate indicators
        instrument_df = self._calculate_indicators(instrument_df)

        # Store the updated dataframe back
        self.instrument_data[instrument_key]['candles'] = instrument_df

        # --- Signal Generation Logic ---
        # Don't generate a new signal if a trade is already active or a signal is pending
        if self.instrument_data[instrument_key]['active_trade'] or self.instrument_data[instrument_key]['signal']:
            return

        # Need at least 2 candles to refer to the 'last' one
        if len(instrument_df) < 2:
            return

        last_candle = instrument_df.iloc[-1]

        # Get indicator names from pandas-ta conventions
        jma_col = f'JMA_{self.config.get("ma_period", 21)}'
        ema_col = f'EMA_{self.config.get("ma_period", 21)}'
        sma_col = f'SMA_{self.config.get("ma_period", 21)}'
        adx_col = f'ADX_{self.config.get("adx_period", 14)}'

        # Check if all indicator columns exist
        required_cols = [jma_col, ema_col, sma_col, adx_col]
        if not all(col in last_candle.index for col in required_cols):
            logger.debug("Indicator columns not yet available.")
            return

        # Check for missing indicator values
        if any(pd.isna(last_candle[col]) for col in required_cols):
            logger.debug("Waiting for indicators to populate.")
            return

        adx_threshold = self.config.get('adx_threshold', 25)

        # Buy Signal Condition
        is_buy_signal = (last_candle[jma_col] > last_candle[ema_col] and
                         last_candle[ema_col] > last_candle[sma_col] and
                         last_candle[adx_col] > adx_threshold)

        # Sell Signal Condition
        is_sell_signal = (last_candle[jma_col] < last_candle[ema_col] and
                          last_candle[ema_col] < last_candle[sma_col] and
                          last_candle[adx_col] > adx_threshold)

        if is_buy_signal:
            signal_data = {
                'type': 'BUY',
                'signal_candle': last_candle.to_dict()
            }
            self.instrument_data[instrument_key]['signal'] = signal_data
            logger.info(f"BUY SIGNAL detected for {instrument_key} at {last_candle.name}")

        elif is_sell_signal:
            signal_data = {
                'type': 'SELL',
                'signal_candle': last_candle.to_dict()
            }
            self.instrument_data[instrument_key]['signal'] = signal_data
            logger.info(f"SELL SIGNAL detected for {instrument_key} at {last_candle.name}")

    def _handle_ltp(self, ltp):
        """
        Handles a new Last Traded Price tick.
        Checks for entry execution or trailing stop loss triggers.
        """
        instrument_key = ltp['instrument_key']
        live_price = ltp['ltp']

        # Check for pending entry signals to execute a trade
        signal = self.instrument_data[instrument_key].get('signal')
        if signal:
            signal_candle = signal['signal_candle']
            trade_executed = False

            if signal['type'] == 'BUY' and live_price > signal_candle['high']:
                logger.info(f"BUY ENTRY TRIGGERED for {instrument_key} at {live_price}")

                # 1. Calculate Stop Loss
                lookback = self.config.get('sl_lookback_period', 10)
                stop_loss = self._find_swing_low(self.instrument_data[instrument_key]['candles'], lookback)
                if not stop_loss:
                    stop_loss = signal_candle['low'] # Fallback to signal candle low

                # 2. Place Order
                order_id = self.broker.place_order(
                    quantity=self.config.get('quantity', 1),
                    product=self.config.get('product_type', 'I'),
                    instrument_token=instrument_key,
                    order_type='MARKET',
                    transaction_type='BUY'
                )

                # 3. Create Active Trade
                if order_id:
                    self.instrument_data[instrument_key]['active_trade'] = {
                        'type': 'BUY',
                        'entry_price': live_price, # Note: This is approx. Actual fill price may differ.
                        'stop_loss': stop_loss,
                        'quantity': self.config.get('quantity', 1),
                        'order_id': order_id,
                        'status': 'OPEN'
                    }
                    trade_executed = True

            elif signal['type'] == 'SELL' and live_price < signal_candle['low']:
                logger.info(f"SELL ENTRY TRIGGERED for {instrument_key} at {live_price}")

                # 1. Calculate Stop Loss
                lookback = self.config.get('sl_lookback_period', 10)
                stop_loss = self._find_swing_high(self.instrument_data[instrument_key]['candles'], lookback)
                if not stop_loss:
                    stop_loss = signal_candle['high'] # Fallback to signal candle high

                # 2. Place Order
                order_id = self.broker.place_order(
                    quantity=self.config.get('quantity', 1),
                    product=self.config.get('product_type', 'I'),
                    instrument_token=instrument_key,
                    order_type='MARKET',
                    transaction_type='SELL'
                )

                # 3. Create Active Trade
                if order_id:
                    self.instrument_data[instrument_key]['active_trade'] = {
                        'type': 'SELL',
                        'entry_price': live_price,
                        'stop_loss': stop_loss,
                        'quantity': self.config.get('quantity', 1),
                        'order_id': order_id,
                        'status': 'OPEN'
                    }
                    trade_executed = True

            # 4. Clear the signal if trade was executed
            if trade_executed:
                self.instrument_data[instrument_key]['signal'] = None
                logger.info(f"Trade activated for {instrument_key}. Signal cleared.")


        # Check for active trades to manage exits
        active_trade = self.instrument_data[instrument_key].get('active_trade')
        if active_trade and active_trade['status'] != 'CLOSED':
            self._manage_active_trade(instrument_key, live_price)

    def _manage_active_trade(self, instrument_key, live_price):
        """Manages exits for an active trade."""
        trade = self.instrument_data[instrument_key]['active_trade']

        # 1. Check initial stop-loss
        if trade['type'] == 'BUY' and live_price <= trade['stop_loss']:
            logger.info(f"STOP LOSS hit for BUY trade on {instrument_key} at {live_price}")
            self.broker.place_order(trade['quantity'], self.config['product_type'], instrument_key, 'MARKET', 'SELL')
            self.instrument_data[instrument_key]['active_trade']['status'] = 'CLOSED'
            return
        elif trade['type'] == 'SELL' and live_price >= trade['stop_loss']:
            logger.info(f"STOP LOSS hit for SELL trade on {instrument_key} at {live_price}")
            self.broker.place_order(trade['quantity'], self.config['product_type'], instrument_key, 'MARKET', 'BUY')
            self.instrument_data[instrument_key]['active_trade']['status'] = 'CLOSED'
            return

        # 2. Check for partial profit booking (if not already done)
        if trade['status'] == 'OPEN':
            risk = abs(trade['entry_price'] - trade['stop_loss'])
            rr_ratio = self.config.get('rr_ratio', 1.5)
            profit_target = trade['entry_price'] + (risk * rr_ratio) if trade['type'] == 'BUY' else trade['entry_price'] - (risk * rr_ratio)

            if (trade['type'] == 'BUY' and live_price >= profit_target) or \
               (trade['type'] == 'SELL' and live_price <= profit_target):
                logger.info(f"PARTIAL PROFIT TARGET hit for {instrument_key} at {live_price}")
                partial_qty_pct = self.config.get('partial_profit_pct', 0.7)
                exit_qty = int(trade['quantity'] * partial_qty_pct)

                if exit_qty > 0:
                    exit_side = 'SELL' if trade['type'] == 'BUY' else 'BUY'
                    self.broker.place_order(exit_qty, self.config['product_type'], instrument_key, 'MARKET', exit_side)

                    trade['quantity'] -= exit_qty
                    trade['status'] = 'PARTIALLY_EXITED'
                    logger.info(f"Partially exited {exit_qty} units. Remaining: {trade['quantity']}")
                else:
                    # If partial quantity is zero (e.g., total qty was 1), just move to trailing
                    trade['status'] = 'PARTIALLY_EXITED'


        # 3. Check for Heikin Ashi trailing stop (if partially exited)
        if trade['status'] == 'PARTIALLY_EXITED':
            candles_df = self.instrument_data[instrument_key]['candles']
            if len(candles_df) < 3: return # Need at least 2 HA candles to check

            ha_df = self._calculate_heikin_ashi(candles_df)
            if ha_df is None or len(ha_df) < 2: return

            last_ha = ha_df.iloc[-1]
            prev_ha = ha_df.iloc[-2]

            # Trail for BUY trade: Exit on two consecutive red HA candles
            if trade['type'] == 'BUY':
                is_ha_red = lambda candle: candle['HA_open'] > candle['HA_close']
                if is_ha_red(last_ha) and is_ha_red(prev_ha):
                    if live_price < prev_ha['HA_low']:
                        logger.info(f"HEIKIN ASHI TRAIL STOP hit for BUY trade on {instrument_key} at {live_price}")
                        self.broker.place_order(trade['quantity'], self.config['product_type'], instrument_key, 'MARKET', 'SELL')
                        self.instrument_data[instrument_key]['active_trade']['status'] = 'CLOSED'

            # Trail for SELL trade: Exit on two consecutive green HA candles
            elif trade['type'] == 'SELL':
                is_ha_green = lambda candle: candle['HA_open'] < candle['HA_close']
                if is_ha_green(last_ha) and is_ha_green(prev_ha):
                    if live_price > prev_ha['HA_high']:
                        logger.info(f"HEIKIN ASHI TRAIL STOP hit for SELL trade on {instrument_key} at {live_price}")
                        self.broker.place_order(trade['quantity'], self.config['product_type'], instrument_key, 'MARKET', 'BUY')
                        self.instrument_data[instrument_key]['active_trade']['status'] = 'CLOSED'

    def _calculate_indicators(self, df):
        """
        Calculates all required indicators for the given DataFrame of candles.
        """
        if df.empty:
            return df

        # Get parameters from config
        ma_period = self.config.get('ma_period', 21)
        adx_period = self.config.get('adx_period', 14)

        # Calculate indicators using pandas-ta
        df.ta.sma(length=ma_period, append=True)
        df.ta.ema(length=ma_period, append=True)
        df.ta.jma(length=ma_period, append=True) # JMA might not be in all versions, ensure installed pandas-ta supports it.
        df.ta.adx(length=adx_period, append=True)

        return df

    def _find_swing_low(self, df, lookback_period):
        """
        Finds the lowest low in the lookback period, ignoring the most recent candle.
        """
        if len(df) < lookback_period + 1:
            return None
        # Look at the period before the last candle
        relevant_df = df.iloc[-(lookback_period + 1):-1]
        return relevant_df['low'].min()

    def _find_swing_high(self, df, lookback_period):
        """
        Finds the highest high in the lookback period, ignoring the most recent candle.
        """
        if len(df) < lookback_period + 1:
            return None
        # Look at the period before the last candle
        relevant_df = df.iloc[-(lookback_period + 1):-1]
        return relevant_df['high'].max()

    def _calculate_heikin_ashi(self, df):
        """
        Calculates Heikin Ashi candles from a standard OHLC DataFrame.
        Returns a new DataFrame with Heikin Ashi candles.
        """
        if df.empty:
            return None

        ha_df = ta.ha(df['open'], df['high'], df['low'], df['close'])
        # The ta.ha function returns a DataFrame with columns like 'HA_open', 'HA_high', etc.
        return ha_df
