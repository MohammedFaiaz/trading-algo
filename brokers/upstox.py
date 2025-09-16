import os
from dotenv import load_dotenv
import upstox_client
from logger import logger
from brokers.base import BrokerBase

load_dotenv()

class UpstoxBroker(BrokerBase):
    """
    Broker implementation for Upstox.
    """
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("UPSTOX_API_KEY")
        self.api_secret = os.getenv("UPSTOX_API_SECRET")
        self.redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")
        self.access_token = None
        self.api_client = None

        if not all([self.api_key, self.api_secret, self.redirect_uri]):
            raise ValueError("UPSTOX_API_KEY, UPSTOX_API_SECRET, and UPSTOX_REDIRECT_URI must be set in .env file")

        logger.info("UpstoxBroker initialized with API Key.")

    def _generate_auth_url(self):
        """
        Generates the authentication URL for the user to log in by constructing it manually
        based on the Upstox API documentation.
        """
        base_url = "https://api.upstox.com/v2/login/authorization/dialog"
        params = {
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "response_type": "code"
        }
        # The upstox_client.rest.urllib3.util.url.Url class can be used for proper encoding,
        # but for these simple params, manual construction is fine.
        auth_url = f"{base_url}?client_id={params['client_id']}&redirect_uri={params['redirect_uri']}&response_type={params['response_type']}"

        logger.info(f"Generated authentication URL: {auth_url}")
        return auth_url

    def set_access_token(self, auth_code):
        """
        Exchanges the authorization code for an access token.
        """
        api_instance = upstox_client.LoginApi()
        api_response = api_instance.token(
            api_version="v2",
            client_id=self.api_key,
            client_secret=self.api_secret,
            code=auth_code,
            grant_type="authorization_code",
            redirect_uri=self.redirect_uri
        )
        self.access_token = api_response.access_token
        logger.info("Successfully generated access token.")

        # Configure the API client with the access token
        configuration = upstox_client.Configuration()
        configuration.access_token = self.access_token
        self.api_client = upstox_client.ApiClient(configuration)


    def authenticate(self):
        """
        Handles the OAuth 2.0 authentication flow for Upstox.
        This is an interactive process.
        """
        logger.info("Starting interactive authentication process for Upstox.")
        login_url = self._generate_auth_url()

        message = (
            "Please follow these steps to authenticate:\n"
            "1. Open the following URL in your web browser:\n"
            f"   {login_url}\n"
            "2. Log in to your Upstox account and authorize the application.\n"
            "3. You will be redirected to a URL that may look like 'https://your-redirect-uri/?code=YOUR_CODE'.\n"
            "4. Please copy the value of the 'code' parameter from the URL's address bar.\n"
            "   For example, if the URL is 'http://127.0.0.1:5000/callback?code=abcdef12345', you would copy 'abcdef12345'.\n"
            "Please paste the authorization code here:"
        )

        return message

    def get_profile(self):
        """
        Fetches the user profile from Upstox.
        This is a good way to test if the access token is valid.
        """
        if not self.api_client:
            logger.error("API client not configured. Please authenticate first.")
            return None

        try:
            user_api = upstox_client.UserApi(self.api_client)
            api_response = user_api.get_profile("v2")
            logger.info("Successfully fetched user profile.")
            return api_response
        except upstox_client.ApiException as e:
            logger.error(f"Error fetching profile: {e}")
            return None

    def get_historical_candle_data(self, instrument_key, interval, to_date, from_date):
        """
        Fetches historical candle data from Upstox.

        Args:
            instrument_key (str): The instrument key (e.g., 'NSE_INDEX|Nifty 50').
            interval (str): The candle interval (e.g., '1minute', '5minute', 'day').
            to_date (str): The end date in YYYY-MM-DD format.
            from_date (str): The start date in YYYY-MM-DD format.
        """
        if not self.api_client:
            logger.error("API client not configured. Please authenticate first.")
            return None

        try:
            history_api = upstox_client.HistoryApi(self.api_client)
            api_response = history_api.get_historical_candle_data(
                instrument_key=instrument_key,
                interval=interval,
                to_date=to_date,
                from_date=from_date,
                api_version="v2"
            )
            logger.info(f"Successfully fetched historical data for {instrument_key}.")
            return api_response
        except upstox_client.ApiException as e:
            logger.error(f"Error fetching historical data for {instrument_key}: {e}")
            return None

    def connect_websocket(self, instrument_keys, on_message_callback=None):
        """
        Connects to the Upstox WebSocket for live market data.

        Args:
            instrument_keys (list): A list of instrument keys to subscribe to.
            on_message_callback (function, optional): A callback function to handle incoming messages.
        """
        if not self.access_token:
            logger.error("Cannot connect to WebSocket without an access token. Please authenticate first.")
            return

        # Configure the API client for the streamer
        configuration = upstox_client.Configuration()
        configuration.access_token = self.access_token

        # The WebSocket requires a different API client setup that doesn't use the regular http client
        # We need to get the websocket feed URL first
        try:
            api_instance = upstox_client.WebsocketApi(upstox_client.ApiClient(configuration))
            api_response = api_instance.get_market_data_feed_authorize(api_version="v2")
            feed_url = api_response.data.authorized_redirect_uri
            logger.info("Successfully obtained WebSocket feed URL.")
        except upstox_client.ApiException as e:
            logger.error(f"Error getting WebSocket feed URL: {e}")
            return

        # Create a new configuration for the WebSocket client
        ws_config = upstox_client.Configuration()
        ws_config.api_key['api-key'] = self.api_key # This might be needed depending on the SDK version
        ws_config.access_token = self.access_token

        # Initialize the MarketDataStreamer
        streamer = upstox_client.MarketDataStreamer(
            upstox_client.ApiClient(ws_config),
            instrument_keys,
            "full"
        )

        def on_message(message):
            logger.debug(f"WebSocket message received: {message}")
            if on_message_callback:
                on_message_callback(message)

        def on_open():
            logger.info("WebSocket connection opened.")

        def on_close():
            logger.info("WebSocket connection closed.")

        def on_error(error):
            logger.error(f"WebSocket error: {error}")

        streamer.on("message", on_message)
        streamer.on("open", on_open)
        streamer.on("close", on_close)
        streamer.on("error", on_error)

        logger.info("Connecting to WebSocket...")
        streamer.connect()

    def place_order(self, quantity, product, instrument_token, order_type, transaction_type, validity='DAY', price=0, trigger_price=0):
        """
        Places an order on Upstox.

        Args:
            quantity (int): The number of shares or lots.
            product (str): The product type (e.g., 'D' for delivery, 'I' for intraday).
            instrument_token (str): The instrument key.
            order_type (str): The type of order (e.g., 'MARKET', 'LIMIT').
            transaction_type (str): 'BUY' or 'SELL'.
            validity (str, optional): Order validity. Defaults to 'DAY'.
            price (float, optional): The limit price for LIMIT orders. Defaults to 0.
            trigger_price (float, optional): The trigger price for STOP_LOSS orders. Defaults to 0.
        """
        if not self.api_client:
            logger.error("API client not configured. Please authenticate first.")
            return None

        # Map our standard order types to Upstox's constants
        order_type_map = {
            'MARKET': upstox_client.OrderType.MARKET,
            'LIMIT': upstox_client.OrderType.LIMIT,
            'SL': upstox_client.OrderType.SL,
            'SL-M': upstox_client.OrderType.SL_M
        }
        transaction_type_map = {
            'BUY': upstox_client.TransactionType.BUY,
            'SELL': upstox_client.TransactionType.SELL
        }
        product_type_map = {
            'D': upstox_client.Product.D,
            'I': upstox_client.Product.I,
            'CO': upstox_client.Product.CO,
            'OCO': upstox_client.Product.OCO,
            'BO': upstox_client.Product.BO
        }

        try:
            order_api = upstox_client.OrderApi(self.api_client)
            order_request = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product=product_type_map.get(product, product),
                instrument_token=instrument_token,
                order_type=order_type_map.get(order_type, order_type),
                transaction_type=transaction_type_map.get(transaction_type, transaction_type),
                validity=validity,
                price=price,
                trigger_price=trigger_price,
                disclosed_quantity=0,
                is_amo=False
            )

            api_response = order_api.place_order(body=order_request, api_version="v2")
            logger.info(f"Successfully placed order: {api_response.data.order_id}")
            return api_response.data.order_id
        except upstox_client.ApiException as e:
            logger.error(f"Error placing order for {instrument_token}: {e}")
            return None
