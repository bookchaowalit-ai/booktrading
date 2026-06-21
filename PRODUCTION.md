# Production Deployment Guide

## 🚀 Deploying to Production

This guide covers deploying BookFinance to a production server.

---

## Prerequisites

- Ubuntu 22.04+ server (or similar Linux distribution)
- Docker & Docker Compose installed
- Domain name pointing to your server IP
- At least 2GB RAM, 2 CPU cores, 20GB disk

---

## Step 1: Server Setup

```bash
# SSH into your server
ssh user@your-server-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install Docker Compose (usually included with Docker)
docker compose version

# Clone your repository
cd /opt
sudo mkdir bookfinance
sudo chown $USER:$USER bookfinance
cd bookfinance
git clone https://github.com/your-username/bookfinance.git .
```

---

## Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your production values
nano .env
```

### Required Environment Variables

```bash
# Database
DB_PASSWORD=your-secure-database-password
DB_USER=trading
DB_NAME=trading_bot

# Redis
REDIS_PASSWORD=your-secure-redis-password

# Security (32+ characters)
ENCRYPTION_KEY=your-32-character-encryption-key-here-make-it-random!

# Admin Account
FIRST_ADMIN_EMAIL=admin@your-domain.com
FIRST_ADMIN_PASSWORD=secure-admin-password
FIRST_ADMIN_NAME=Admin

# Frontend URL (your domain)
FRONTEND_URL=https://your-domain.com

# Exchange API Keys (fill in your actual keys)
EXCHANGE_PROVIDER=binance_th
BINANCE_TH_API_KEY=your-binance-th-api-key
BINANCE_TH_API_SECRET=your-binance-th-api-secret

# Optional: Other exchanges
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_USE_TESTNET=false
BITKUB_API_KEY=
BITKUB_API_SECRET=
BITKUB_USE_TESTNET=false

# Real Trading Configuration
REAL_SYMBOLS=BTCTHB               # Symbol for real trading (Binance TH)
DISABLE_PAPER_BOT=true            # Disable paper bot to reduce log noise
AUTH_TOKEN=                       # Leave empty for dev, set for production auth
```

---

## Step 3: Update Caddyfile

Edit `Caddyfile` and replace `your-domain.com` with your actual domain:

```bash
nano Caddyfile
# Replace all instances of your-domain.com with your actual domain
```

---

## Step 4: Deploy

```bash
# Build and start all services
docker compose -f docker-compose.prod.yml up -d --build

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Check if services are healthy
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.Status}}"
```

---

## Step 5: Verify Deployment

```bash
# Check if frontend is accessible
curl -I https://your-domain.com

# Check if API is working
curl https://your-domain.com/api/health

# Check WebSocket connection
wscat -c wss://your-domain.com/ws

# View all service logs
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f strategy
```

---

## Step 6: Setup Automated Backups

```bash
# Create backup script
sudo nano /opt/bookfinance/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/bookfinance/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup PostgreSQL
docker exec bookfinance-postgres pg_dump -U trading trading_bot | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup Redis
docker exec bookfinance-redis redis-cli -a $REDIS_PASSWORD --no-auth-warning BGSAVE
sleep 5
docker cp bookfinance-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
sudo chmod +x /opt/bookfinance/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /opt/bookfinance/backup.sh >> /opt/bookfinance/backup.log 2>&1
```

---

## Step 7: Setup Monitoring

```bash
# Install htop for system monitoring
sudo apt install -y htop

# Check disk usage
df -h

# Check memory usage
free -h

# Monitor Docker containers
docker stats
```

### Daily Report & Snapshots

The strategy API provides a daily report endpoint for audit:

```bash
# Get daily report (inside container)
curl http://localhost:8000/api/report/daily?symbol=BTCTHB
```

To automate snapshot cadence (every 5 hours):

```bash
# Add to crontab
crontab -e
# Add: 0 */5 * * * cd /opt/bookfinance && docker compose exec -T strategy python3 /app/scripts/snapshot_report.py >> /var/log/bookfinance-snapshot.log 2>&1
```

Snapshots are saved to `strategy/reports/grid-bot/` inside the container.

### Backfill Trade Journal

If trade_journal entries are missing (e.g., orders created before journal system):

```bash
# Copy script to container
docker compose cp strategy/scripts/backfill_journal.py strategy:/app/scripts/

# Run backfill
docker compose exec strategy python3 /app/scripts/backfill_journal.py
```

---

## Updating the Application

```bash
# Pull latest changes
cd /opt/bookfinance
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Verify
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

---

## Troubleshooting

### Service won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs frontend

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Database connection issues

```bash
# Check if PostgreSQL is running
docker exec bookfinance-postgres pg_isready -U trading

# Check database logs
docker compose -f docker-compose.prod.yml logs postgres
```

### SSL/TLS issues

```bash
# Check Caddy logs
docker compose -f docker-compose.prod.yml logs caddy

# Force certificate renewal
docker exec bookfinance-caddy caddy reload
```

---

## Security Checklist

- [ ] Changed all default passwords
- [ ] Set strong ENCRYPTION_KEY (32+ chars)
- [ ] Configured firewall (only ports 80, 443 open)
- [ ] SSL certificate working (https://your-domain.com)
- [ ] Admin password changed from default
- [ ] API keys stored securely (not in git)
- [ ] Automated backups configured
- [ ] Monitoring setup

---

## Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for Let's Encrypt)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Verify
sudo ufw status
```

---

## Support

If you encounter issues:

1. Check logs: `docker compose -f docker-compose.prod.yml logs -f`
2. Verify environment variables are set correctly
3. Ensure domain DNS is pointing to your server
4. Check firewall rules allow ports 80/443

---

**Your production deployment is now ready!** 🎉

Access your app at: `https://your-domain.com`
