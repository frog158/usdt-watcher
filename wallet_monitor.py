import requests
import time
import logging
import configparser
import os
import sys
import json
from datetime import datetime, timedelta
import http.client
import urllib.parse
import uuid
import signal


running = True

def handle_sigterm(signum, frame):
    global running
    print(f"[{datetime.now().isoformat()}] 🛑 Received stop signal ({signum})")
    running = False

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

# Set up logging
def setup_logging(log_file):
    logger = logging.getLogger('wallet_monitor')
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Log format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Read configuration
def read_config(config_file):
    if not os.path.exists(config_file):
        create_default_config(config_file)

    config = configparser.ConfigParser()
    config.read(config_file)

    return config

# Create default configuration
def create_default_config(config_file):
    config = configparser.ConfigParser()
    config['API'] = {
        'api_key': 'YOUR_ETHERSCAN_API_KEY',
        'wallet_address': 'YOUR_WALLET_ADDRESS',
        'usdt_contract': '0xdac17f958d2ee523a2206206994597c13d831ec7'  # USDT contract on Ethereum
    }

    config['SETTINGS'] = {
        'check_interval': '3600',  # seconds (1 hour)
        'retry_interval': '300',   # seconds (5 minutes)
        'max_retries': '3',
        'log_file': 'wallet_monitor.log',
        'state_file': 'wallet_state.json',
        'topic_id': str(uuid.uuid4())  # Generate a unique topic ID
    }

    config['NFTYSH'] = {
        'enabled': 'true',
        'topic_id': 'YOUR_UNIQUE_TOPIC_ID',  # Will be replaced with generated UUID if not set
        'message_retry_count': '3',
        'message_retry_delay': '60'  # seconds
    }

    config['PUSHOVER'] = {
        'enabled': 'true',
        'app_token': 'YOUR_PUSHOVER_APP_TOKEN',
        'user_keys': 'YOUR_PUSHOVER_USER_KEY',  # Comma-separated list of user keys
        'message_retry_count': '3',
        'message_retry_delay': '60',  # seconds
        'priority': '0'  # -2 to 2, where 2 is emergency
    }

    config['UPTIME_KUMA'] = {
        'enabled': 'true',
        'push_url': 'https://your-uptime-kuma-instance/api/push/your-monitor-id',
        'message_retry_count': '3',
        'message_retry_delay': '30'  # seconds
    }

    with open(config_file, 'w') as f:
        config.write(f)

    print(f"Default configuration file created: {config_file}")
    print("Please edit it to include your API keys, wallet address, and notification settings.")
    sys.exit(0)

# Get USDT balance
def get_usdt_balance(wallet_address, contract_address, api_key, logger):
    url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "tokenbalance",
        "contractaddress": contract_address,
        "address": wallet_address,
        "tag": "latest",
        "apikey": api_key
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] == "1":
            # USDT has 6 decimal places
            balance = int(data["result"]) / 10**6
            logger.info(f"Current USDT balance: {balance}")
            return balance
        else:
            error_msg = data['message'] if 'message' in data else 'Unknown API error'
            logger.error(f"API Error: {error_msg}")
            raise Exception(f"Etherscan API error: {error_msg}")
    except Exception as e:
        logger.error(f"Error requesting API: {str(e)}")
        raise

# Send ntfy.sh notification with retries
def send_ntfy_notification(topic_id, title, message, retry_count, retry_delay, logger):
    url = f"https://ntfy.sh/{topic_id}"

    headers = {
        "Title": title,
        "Priority": "default"
    }

    for attempt in range(retry_count + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                data=message.encode(encoding='utf-8')
            )

            if response.status_code == 200:
                logger.info(f"ntfy.sh notification sent successfully to topic {topic_id}")
                break
            else:
                error_msg = f"Status code: {response.status_code}"
                logger.error(f"Failed to send ntfy.sh notification: {error_msg}")

                if attempt < retry_count:
                    logger.info(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to send ntfy.sh notification after {retry_count} retries")
        except Exception as e:
            logger.error(f"Error sending ntfy.sh notification: {str(e)}")

            if attempt < retry_count:
                logger.info(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to send ntfy.sh notification after {retry_count} retries")

# Send Pushover message with retries
def send_pushover_message(app_token, user_keys, title, message, priority, retry_count, retry_delay, logger):
    # Split user_keys string into a list
    user_key_list = [key.strip() for key in user_keys.split(',')]

    for user_key in user_key_list:
        for attempt in range(retry_count + 1):
            try:
                conn = http.client.HTTPSConnection("api.pushover.net:443")

                params = {
                    "token": app_token,
                    "user": user_key,
                    "title": title,
                    "message": message,
                    "priority": priority,
                }

                conn.request(
                    "POST",
                    "/1/messages.json",
                    urllib.parse.urlencode(params),
                    {"Content-type": "application/x-www-form-urlencoded"}
                )

                response = conn.getresponse()
                result = json.loads(response.read().decode("utf-8"))

                if response.status == 200 and result.get("status") == 1:
                    logger.info(f"Pushover notification sent to user {user_key[:5]}...")
                    break
                else:
                    error_msg = result.get("errors", ["Unknown error"])[0] if "errors" in result else "Unknown error"
                    logger.error(f"Failed to send Pushover message: {error_msg}")

                    if attempt < retry_count:
                        logger.info(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to send Pushover message after {retry_count} retries")
            except Exception as e:
                logger.error(f"Error sending Pushover message: {str(e)}")

                if attempt < retry_count:
                    logger.info(f"Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to send Pushover message after {retry_count} retries")

# Send ping to Uptime Kuma
def send_uptime_kuma_ping(push_url, status, msg, ping_value, retry_count, retry_delay, logger):
    # Add status and message parameters to the URL
    url = f"{push_url}?status={status}&msg={urllib.parse.quote(msg)}&ping={ping_value}"

    for attempt in range(retry_count + 1):
        try:
            response = requests.get(url)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"Successfully sent ping to Uptime Kuma: {status}")
                    break
                else:
                    logger.error(f"Failed to send ping to Uptime Kuma: {result.get('msg', 'Unknown error')}")
            else:
                logger.error(f"Failed to send ping to Uptime Kuma. Status code: {response.status_code}")

            if attempt < retry_count:
                logger.info(f"Retrying Uptime Kuma ping in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to send Uptime Kuma ping after {retry_count} retries")

        except Exception as e:
            logger.error(f"Error sending Uptime Kuma ping: {str(e)}")

            if attempt < retry_count:
                logger.info(f"Retrying Uptime Kuma ping in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_count})")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to send Uptime Kuma ping after {retry_count} retries")

# Load saved state
def load_state(state_file, logger):
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading state file: {str(e)}")
            # Return default state on error
            return {"previous_balance": None, "last_check": None}
    else:
        logger.info(f"State file not found. Creating new state.")
        # Create empty state file
        empty_state = {"previous_balance": None, "last_check": None}
        try:
            with open(state_file, 'w') as f:
                json.dump(empty_state, f)
            logger.info(f"Empty state file created at {state_file}")
        except Exception as e:
            logger.error(f"Error creating initial state file: {str(e)}")

        return empty_state

# Save state
def save_state(state_file, state, logger):
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f)
        logger.debug("State saved successfully")
    except Exception as e:
        logger.error(f"Error saving state: {str(e)}")

# Main function
def main():
    config_file = "wallet_monitor.conf"
    config = read_config(config_file)

    # Settings from config
    api_key = config['API']['api_key']
    wallet_address = config['API']['wallet_address']
    usdt_contract = config['API']['usdt_contract']

    check_interval = int(config['SETTINGS']['check_interval'])
    retry_interval = int(config['SETTINGS']['retry_interval'])
    max_retries = int(config['SETTINGS']['max_retries'])
    log_file = config['SETTINGS']['log_file']
    state_file = config['SETTINGS']['state_file']

    # Set up logging first, before doing anything else with the logger
    logger = setup_logging(log_file)

    # ntfy.sh settings
    ntfy_enabled = config['NFTYSH'].getboolean('enabled', fallback=True)
    ntfy_topic_id = config['NFTYSH']['topic_id']
    ntfy_retry_count = int(config['NFTYSH']['message_retry_count'])
    ntfy_retry_delay = int(config['NFTYSH']['message_retry_delay'])

    # If topic_id is still the default, generate a new one
    if ntfy_topic_id == 'YOUR_UNIQUE_TOPIC_ID':
        ntfy_topic_id = str(uuid.uuid4())
        config['NTFY']['topic_id'] = ntfy_topic_id
        with open(config_file, 'w') as f:
            config.write(f)
        logger.info(f"Generated new ntfy.sh topic ID: {ntfy_topic_id}")

    # Pushover settings
    pushover_enabled = config['PUSHOVER'].getboolean('enabled', fallback=True)
    pushover_app_token = config['PUSHOVER']['app_token']
    pushover_user_keys = config['PUSHOVER']['user_keys']
    pushover_retry_count = int(config['PUSHOVER']['message_retry_count'])
    pushover_retry_delay = int(config['PUSHOVER']['message_retry_delay'])
    pushover_priority = int(config['PUSHOVER']['priority'])

    # Uptime Kuma settings
    uptime_kuma_enabled = config['UPTIME_KUMA'].getboolean('enabled', fallback=True)
    uptime_kuma_push_url = config['UPTIME_KUMA']['push_url']
    uptime_kuma_retry_count = int(config['UPTIME_KUMA']['message_retry_count'])
    uptime_kuma_retry_delay = int(config['UPTIME_KUMA']['message_retry_delay'])

    # Check for default values
    if api_key == 'YOUR_ETHERSCAN_API_KEY' or wallet_address == 'YOUR_WALLET_ADDRESS':
        logger.error("Please specify your API key and wallet address in the configuration file.")
        sys.exit(1)

    # Check notification configuration
    if pushover_enabled and pushover_app_token == 'YOUR_PUSHOVER_APP_TOKEN':
        logger.error("Please specify your Pushover app token in the configuration file or disable Pushover notifications.")
        sys.exit(1)

    if uptime_kuma_enabled and uptime_kuma_push_url == 'https://your-uptime-kuma-instance/api/push/your-monitor-id':
        logger.error("Please specify your Uptime Kuma push URL in the configuration file or disable Uptime Kuma integration.")
        sys.exit(1)

    # Ensure at least one notification method is properly configured
    if not (ntfy_enabled or pushover_enabled):
        logger.warning("No notification methods are enabled. You will not receive alerts for balance changes.")

    if ntfy_enabled:
        logger.info(f"ntfy.sh notifications are enabled. Topic ID: {ntfy_topic_id}")
        logger.info(f"Subscribe to notifications at: https://ntfy.sh/{ntfy_topic_id}")

    if pushover_enabled:
        logger.info("Pushover notifications are enabled")

    if uptime_kuma_enabled:
        logger.info("Uptime Kuma integration is enabled")

    # Load previous state
    try:
        state = load_state(state_file, logger)
        previous_balance = state.get("previous_balance")

        if previous_balance is not None:
            logger.info(f"Loaded previous balance: {previous_balance}")
        else:
            logger.info("No previous balance found in state file.")
    except Exception as e:
        logger.error(f"Error initializing state: {str(e)}")
        previous_balance = None
        state = {"previous_balance": None, "last_check": None}

    while running:
        retry_count = 0
        balance = None
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        error_message = None

        # Attempt to get balance with retries on errors
        while balance is None and retry_count <= max_retries:
            if retry_count > 0:
                logger.info(f"Retry attempt {retry_count}/{max_retries} in {retry_interval} seconds...")
                time.sleep(retry_interval)

            try:
                balance = get_usdt_balance(wallet_address, usdt_contract, api_key, logger)
                error_message = None  # Clear error message if successful
            except Exception as e:
                error_message = str(e)
                balance = None

            retry_count += 1

        # Send ping to Uptime Kuma based on the result
        if uptime_kuma_enabled:
            if balance is not None:
                # Successful check - UP status
                msg = "Balance check successful"
                send_uptime_kuma_ping(
                    uptime_kuma_push_url,
                    "up",
                    msg,
                    str(balance),
                    uptime_kuma_retry_count,
                    uptime_kuma_retry_delay,
                    logger
                )
            else:
                # Failed check - DOWN status
                msg = f"Balance check failed: {error_message or 'Unknown error'}"
                send_uptime_kuma_ping(
                    uptime_kuma_push_url,
                    "down",
                    msg,
                    "0",
                    uptime_kuma_retry_count,
                    uptime_kuma_retry_delay,
                    logger
                )

        # Check for balance changes and send notifications
        if balance is not None:
            # Update state
            state["last_check"] = current_time
            state["previous_balance"] = balance

            # Save state even if balance hasn't changed
            save_state(state_file, state, logger)

            if previous_balance is not None and balance != previous_balance:
                logger.info(f"USDT balance changed: {previous_balance} -> {balance}")

                # ntfy.sh notification
                if ntfy_enabled:
                    ntfy_title = "USDT Balance Change Alert"
                    ntfy_message = (
                        f"Previous: {previous_balance} USDT\n"
                        f"Current: {balance} USDT\n"
                        f"Change: {balance - previous_balance} USDT\n"
                        f"Time: {current_time}"
                    )
                    send_ntfy_notification(
                        ntfy_topic_id,
                        ntfy_title,
                        ntfy_message,
                        ntfy_retry_count,
                        ntfy_retry_delay,
                        logger
                    )

                # Pushover notification
                if pushover_enabled:
                    pushover_title = "USDT Balance Change Alert"
                    pushover_message = (
                        f"Previous: {previous_balance} USDT\n"
                        f"Current: {balance} USDT\n"
                        f"Change: {balance - previous_balance} USDT\n"
                        f"Time: {current_time}"
                    )
                    send_pushover_message(
                        pushover_app_token,
                        pushover_user_keys,
                        pushover_title,
                        pushover_message,
                        pushover_priority,
                        pushover_retry_count,
                        pushover_retry_delay,
                        logger
                    )

            previous_balance = balance
        else:
            logger.error(f"Failed to get balance after {max_retries} attempts")

        # Wait until next check
        next_check_time = (datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')
        logger.info(f"Next check at {next_check_time}")
        for _ in range(check_interval):
            if not running:
                break
            time.sleep(1)
    logger.info(f"[{datetime.now().isoformat()}] 👋 Clean exit.")
    sys.exit(0)

if __name__ == "__main__":
    main()
