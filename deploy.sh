#!/bin/bash
# Production Deployment Script
# Usage: ./deploy.sh [production|staging]

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  BookFinance Production Deployment${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ── Pre-flight Checks ──────────────────────────────────────────────
echo -e "${YELLOW}📋 Running pre-flight checks...${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Install with: curl -fsSL https://get.docker.com | sudo sh"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Please edit .env with your production values before continuing${NC}"
        echo -e "${YELLOW}⚠️  Run this script again after editing${NC}"
        exit 1
    else
        echo -e "${RED}❌ .env.example not found${NC}"
        exit 1
    fi
fi

# Check if Caddyfile has correct domain
if grep -q "your-domain.com" Caddyfile; then
    echo -e "${RED}❌ Caddyfile still contains 'your-domain.com' placeholder${NC}"
    echo "Please update Caddyfile with your actual domain"
    exit 1
fi

echo -e "${GREEN}✅ Pre-flight checks passed${NC}"
echo ""

# ── Git Operations ────────────────────────────────────────────────
echo -e "${YELLOW}📦 Pulling latest code...${NC}"
git pull origin main || git pull origin master
echo -e "${GREEN}✅ Code updated${NC}"
echo ""

# ── Build & Deploy ────────────────────────────────────────────────
echo -e "${YELLOW}🔨 Building and deploying services...${NC}"

if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
else
    COMPOSE_FILE="docker-compose.yml"
fi

# Stop existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker compose -f $COMPOSE_FILE down --remove-orphans || true
echo ""

# Pull latest images
echo -e "${YELLOW}📥 Pulling latest images...${NC}"
docker compose -f $COMPOSE_FILE pull || true
echo ""

# Build and start
echo -e "${YELLOW}🚀 Building and starting services...${NC}"
docker compose -f $COMPOSE_FILE up -d --build
echo ""

# ── Health Checks ─────────────────────────────────────────────────
echo -e "${YELLOW}🏥 Running health checks...${NC}"

wait_for_service() {
    local service_name=$1
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        local status=$(docker compose -f $COMPOSE_FILE ps --format json $service_name 2>/dev/null | grep -o '"running"' || echo "not_running")
        if [ "$status" = '"running"' ]; then
            echo -e "${GREEN}✅ $service_name is running${NC}"
            return 0
        fi
        echo -e "${YELLOW}⏳ Waiting for $service_name... ($attempt/$max_attempts)${NC}"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start${NC}"
    return 1
}

wait_for_service "postgres"
wait_for_service "redis"
wait_for_service "backend"
wait_for_service "frontend"

echo ""

# ── Post-Deployment Checks ────────────────────────────────────────
echo -e "${YELLOW}🔍 Verifying deployment...${NC}"

# Check if backend API is accessible
sleep 10
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health 2>/dev/null || echo "000")

if [ "$BACKEND_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Backend API is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Backend API returned $BACKEND_STATUS (may still be starting)${NC}"
fi

# Show container status
echo ""
echo -e "${BLUE}📊 Container Status:${NC}"
docker compose -f $COMPOSE_FILE ps

echo ""

# ── Summary ───────────────────────────────────────────────────────
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend API: http://localhost:8080"
echo "📍 WebSocket: ws://localhost:8081/ws"
echo "📍 Strategy API: http://localhost:8000"
echo ""
echo "📝 View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "🔄 Restart: docker compose -f $COMPOSE_FILE restart"
echo "🛑 Stop: docker compose -f $COMPOSE_FILE down"
echo ""
echo -e "${YELLOW}⚠️  Remember to:${NC}"
echo "   1. Set up SSL (if using custom domain)"
echo "   2. Configure firewall (only ports 80, 443 open)"
echo "   3. Set up automated backups"
echo "   4. Change default admin password"
echo ""
echo -e "${GREEN}🎉 Your production deployment is ready!${NC}"
