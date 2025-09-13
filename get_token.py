import sys
from brokers.upstox import UpstoxBroker
from logger import logger

def complete_authentication(auth_code):
    """
    Exchanges the authorization code for an access token and verifies it.
    """
    logger.info(f"Attempting to get access token with auth code: {auth_code}")
    broker = UpstoxBroker()

    try:
        broker.set_access_token(auth_code)
        logger.info(f"Access token set. Broker access token: {broker.access_token}")

        if broker.access_token:
            print("\nSuccessfully obtained access token!")
            print("Verifying token by fetching user profile...")

            profile = broker.get_profile()
            if profile:
                print("\nAuthentication successful! User profile fetched:")
                print(f"  User Name: {profile.data.user_name}")
                print(f"  User ID: {profile.data.user_id}")
                print(f"  Exchanges: {profile.data.exchanges}")
                print("\nUpstox broker integration is now authenticated.")
            else:
                print("\nFailed to fetch profile. The access token might be invalid or expired.")
        else:
            print("\nFailed to obtain access token.")

    except Exception as e:
        logger.error(f"An error occurred during token exchange: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    # The authorization code provided by the user.
    # In a real application, this would not be hardcoded.
    auth_code_from_user = "yXE-Hv"

    if not auth_code_from_user:
        print("Error: Authorization code is missing.")
        sys.exit(1)

    complete_authentication(auth_code_from_user)
