# USDT Wallet Balance Monitor

A simple Python script that monitors USDT balance in an Ethereum wallet and sends notifications when the balance changes.

## Features

- Monitors USDT balance on Ethereum blockchain
- Sends notifications through ntfy.sh and/or Pushover when balance changes
- Configurable check intervals, retry logic, and notification settings
- Reports monitoring status to Uptime Kuma (optional)
- Generates unique notification topics automatically
- Logs all activities to file and console
- Docker support for easy deployment

## Requirements

If running directly:
- Python 3.6+
- Required Python packages (installed via requirements.txt):
  - requests==2.32.3
  - certifi==2025.1.31
  - charset-normalizer==3.4.1
  - idna==3.10
  - urllib3==2.3.0

If using Docker:
- Docker installed on your system

## Installation

### Option 1: Standard Installation

1. Clone the repository:
```bash
git clone https://github.com/frog158/usdt-watcher.git
cd usdt-watcher
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the script once to generate the default configuration file:
```bash
python wallet_monitor.py
```

4. Edit the configuration file (`wallet_monitor.conf`) to add your Etherscan API key, wallet address, and configure notification settings.

### Option 2: Using Docker

1. Pull the Docker image:
```bash
docker pull frog158/usdt-monitor
```

2. Create the necessary files for persistent storage:
```bash
touch wallet_state.json wallet_monitor.conf wallet_monitor.log
```

3. Run the container once to generate the configuration file:
```bash
docker run --rm \
  -v $(pwd)/wallet_state.json:/app/wallet_state.json \
  -v $(pwd)/wallet_monitor.conf:/app/wallet_monitor.conf \
  -v $(pwd)/wallet_monitor.log:/app/wallet_monitor.log \
  frog158/usdt-monitor
```

4. Edit the generated configuration file (`wallet_monitor.conf`) to add your Etherscan API key, wallet address, and notification settings.

## Configuration

The script will generate a default configuration file (`wallet_monitor.conf`) with the following sections:

### API Section
```ini
[API]
api_key = YOUR_ETHERSCAN_API_KEY
wallet_address = YOUR_WALLET_ADDRESS
usdt_contract = 0xdac17f958d2ee523a2206206994597c13d831ec7
```

- `api_key`: Your Etherscan API key (get it from [Etherscan](https://etherscan.io/apis))
- `wallet_address`: The Ethereum wallet address to monitor
- `usdt_contract`: USDT contract address on Ethereum (default is correct, no need to change)

### Settings Section
```ini
[SETTINGS]
check_interval = 3600
retry_interval = 300
max_retries = 3
log_file = wallet_monitor.log
state_file = wallet_state.json
```

- `check_interval`: How often to check balance (in seconds, default: 1 hour)
- `retry_interval`: Time to wait between retries if API call fails (in seconds)
- `max_retries`: Maximum number of retry attempts for API calls
- `log_file`: Path to log file
- `state_file`: Path to state file (stores previous balance)

### NTFY Section
```ini
[NTFY]
enabled = true
topic_id = YOUR_UNIQUE_TOPIC_ID
message_retry_count = 3
message_retry_delay = 60
```

- `enabled`: Enable/disable ntfy.sh notifications
- `topic_id`: A unique identifier for your ntfy.sh topic (generated automatically if not provided)
- `message_retry_count`: Number of retry attempts for failed notifications
- `message_retry_delay`: Time to wait between retries (in seconds)

### Pushover Section
```ini
[PUSHOVER]
enabled = true
app_token = YOUR_PUSHOVER_APP_TOKEN
user_keys = YOUR_PUSHOVER_USER_KEY
message_retry_count = 3
message_retry_delay = 60
priority = 0
```

- `enabled`: Enable/disable Pushover notifications
- `app_token`: Your Pushover application token
- `user_keys`: Comma-separated list of Pushover user keys
- `message_retry_count`: Number of retry attempts for failed notifications
- `message_retry_delay`: Time to wait between retries (in seconds)
- `priority`: Pushover notification priority (-2 to 2, where 2 is emergency)

### Uptime Kuma Section
```ini
[UPTIME_KUMA]
enabled = true
push_url = https://your-uptime-kuma-instance/api/push/your-monitor-id
message_retry_count = 3
message_retry_delay = 30
```

- `enabled`: Enable/disable Uptime Kuma integration
- `push_url`: Your Uptime Kuma push URL
- `message_retry_count`: Number of retry attempts for failed pings
- `message_retry_delay`: Time to wait between retries (in seconds)

## Usage

### Running with Python

After configuring the script, you can run it:

```bash
python wallet_monitor.py
```

For continuous monitoring, you can use a process manager like systemd, supervisor, or run it in a screen/tmux session.

### Running with Docker

After configuring the script, run the Docker container:

```bash
docker run -d --name usdt-monitor \
  -v $(pwd)/wallet_state.json:/app/wallet_state.json \
  -v $(pwd)/wallet_monitor.conf:/app/wallet_monitor.conf \
  -v $(pwd)/wallet_monitor.log:/app/wallet_monitor.log \
  frog158/usdt-monitor
```

To view logs:
```bash
docker logs -f usdt-monitor
```

To stop the container:
```bash
docker stop usdt-monitor
```

### Setting Up ntfy.sh Notifications

When you run the script for the first time with ntfy.sh enabled, it will generate a unique topic ID and provide a URL for subscribing to notifications. You can:

1. Visit the URL shown in the logs (`https://ntfy.sh/YOUR_TOPIC_ID`)
2. Install the [ntfy app](https://ntfy.sh/app) on your phone
3. Subscribe to your topic
4. Receive push notifications whenever your wallet balance changes

### Setting Up Pushover Notifications

To use Pushover:

1. Create an account at [Pushover](https://pushover.net/)
2. Create an application and get an app token
3. Add your app token and user key to the configuration file

## Running as a Service

### Option 1: Using systemd (Linux)

To run the script as a systemd service:

1. Create a systemd service file:
```bash
sudo nano /etc/systemd/system/wallet-monitor.service
```

2. Add the following content (adjust paths as needed):
```
[Unit]
Description=USDT Wallet Balance Monitor
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/wallet_monitor.py
WorkingDirectory=/path/to/script/directory
Restart=always
User=your-username

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable wallet-monitor.service
sudo systemctl start wallet-monitor.service
```

4. Check the status:
```bash
sudo systemctl status wallet-monitor.service
```

### Option 2: Using Docker with auto-restart

Run the Docker container with auto-restart policy:

```bash
docker run -d --name usdt-monitor \
  --restart unless-stopped \
  -v $(pwd)/wallet_state.json:/app/wallet_state.json \
  -v $(pwd)/wallet_monitor.conf:/app/wallet_monitor.conf \
  -v $(pwd)/wallet_monitor.log:/app/wallet_monitor.log \
  frog158/usdt-monitor
```

This will automatically restart the container if it crashes or if the Docker daemon restarts.

## Building the Docker Image

If you want to build the Docker image yourself instead of using the pre-built one:

1. Clone the repository:
```bash
git clone https://github.com/frog158/usdt-watcher.git
cd usdt-watcher
```

2. Build the Docker image:
```bash
docker build -t usdt-monitor .
```

3. Run your custom-built image:
```bash
docker run -d --name usdt-monitor \
  -v $(pwd)/wallet_state.json:/app/wallet_state.json \
  -v $(pwd)/wallet_monitor.conf:/app/wallet_monitor.conf \
  -v $(pwd)/wallet_monitor.log:/app/wallet_monitor.log \
  usdt-monitor
```

The repository already includes the `Dockerfile` and `requirements.txt` files needed for building.

## Troubleshooting

- **API errors**: Make sure your Etherscan API key is valid and has not reached its request limit
- **Balance not updating**: Verify the wallet address and USDT contract address are correct
- **Notification issues**: Check notification service configuration and connectivity
- **Docker volume issues**: Ensure the directories for mounted volumes exist and have proper permissions
- **Docker container stopping**: Check logs with `docker logs usdt-monitor` to identify any errors

## Security Considerations

- Store the script on a secure system
- Do not share your configuration file as it contains sensitive API keys
- Consider using environment variables for sensitive information

## License

[MIT License](LICENSE)

## Acknowledgements

- [Etherscan API](https://etherscan.io/apis) for blockchain data
- [ntfy.sh](https://ntfy.sh/) for free push notifications
- [Pushover](https://pushover.net/) for reliable push notifications
- [Uptime Kuma](https://github.com/louislam/uptime-kuma) for uptime monitoring
