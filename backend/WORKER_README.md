# Running the Background Worker

## Start the Worker

In a separate terminal from your main API server:

```bash
cd backend
python worker.py
```

The worker will:
- Connect to Redis
- Create consumer group `confirmation_workers` if it doesn't exist
- Listen for messages on stream `bookings:confirmations`
- Send WhatsApp confirmations via Twilio

## Development Mode

If Twilio credentials are not configured, the worker will log messages to console instead of sending them.

## Production Deployment

For production, run the worker as a separate process/service:

**Docker Compose:**
```yaml
worker:
  build: ./backend
  command: python worker.py
  environment:
    - REDIS_URL=redis://redis:6379/0
    - TWILIO_ACCOUNT_SID=...
    - TWILIO_AUTH_TOKEN=...
  depends_on:
    - redis
```

**Systemd Service:**
```ini
[Unit]
Description=ZoomCars Booking Confirmation Worker
After=redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/usr/bin/python3 worker.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Monitoring

Check Redis stream status:
```bash
# Number of pending messages
redis-cli XLEN bookings:confirmations

# Consumer group info
redis-cli XINFO GROUPS bookings:confirmations
```
