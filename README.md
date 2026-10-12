# Mercari Watcher

An automated watcher that checks Mercari Japan for new Hysteric Glamour listings and sends an instant phone notification when something new appears.

## How It Works

1. A scheduled **GitHub Actions** workflow runs the Python script
2. The script searches Mercari Japan for the configured keywords
3. New listings (not seen in previous runs) are detected
4. A push notification is sent through **ntfy.sh**

## Tech Stack

- Python
- GitHub Actions (scheduler and runner)
- ntfy.sh (push notifications)

## Setup

### 1. Fork or clone

```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>
pip install -r requirements.txt
```

### 2. Configure

Edit the search settings at the top of `<script name>.py`:

```python
KEYWORDS = ["<keyword 1>", "<keyword 2>"]
NTFY_TOPIC = "<your-private-topic-name>"
```

### 3. Add secrets

In GitHub: Settings → Secrets and variables → Actions, add:

| Secret | Value |
|---|---|
| `NTFY_TOPIC` | Your ntfy topic name |

### 4. Subscribe on your phone

Install the ntfy app and subscribe to your topic name.

### 5. Enable the workflow

Go to the **Actions** tab and enable the workflow. It runs on the schedule defined in `.github/workflows/<workflow>.yml`.

## Run Manually

```bash
python <script name>.py
```

## Known Issues

- Listing thumbnails don't display correctly in notifications

## License

Personal project.
