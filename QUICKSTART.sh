#!/bin/bash

# Alpha Wallet Scout - Quick Start Script
# This script helps you get started quickly with minimal configuration

set -e

echo "🚀 Alpha Wallet Scout - Quick Start"
echo "===================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "✅ .env created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env with your API keys:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - TELEGRAM_CHAT_ID"
    echo "   - ALCHEMY_API_KEY"
    echo "   - HELIUS_API_KEY"
    echo ""
    echo "Run this script again after editing .env"
    exit 0
fi

# Check for required API keys
source .env

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ Error: TELEGRAM_BOT_TOKEN not configured in .env"
    exit 1
fi

if [ -z "$TELEGRAM_CHAT_ID" ] || [ "$TELEGRAM_CHAT_ID" = "your_chat_id_here" ]; then
    echo "❌ Error: TELEGRAM_CHAT_ID not configured in .env"
    exit 1
fi

echo "✅ Configuration validated"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "⚠️  Poetry not found. Installing dependencies with pip..."
    pip install -r requirements.txt 2>/dev/null || echo "Continuing with Docker..."
else
    echo "📦 Installing Python dependencies..."
    poetry install
fi

echo ""
echo "🐳 Starting Docker services..."
docker-compose down -v 2>/dev/null || true
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check if services are up
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services started successfully"
else
    echo "❌ Error: Services failed to start. Check logs with: docker-compose logs"
    exit 1
fi

echo ""
echo "🔍 Running health check..."
sleep 5

HEALTH=$(curl -s http://localhost:8000/health || echo "failed")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    echo "Check logs: docker-compose logs api"
fi

echo ""
echo "═══════════════════════════════════════"
echo "✨ Alpha Wallet Scout is running!"
echo "═══════════════════════════════════════"
echo ""
echo "📊 Services:"
echo "   API:      http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
echo "   Database: localhost:5432"
echo "   Redis:    localhost:6379"
echo ""
echo "📝 Useful commands:"
echo "   View logs:     docker-compose logs -f"
echo "   View worker:   docker-compose logs -f worker"
echo "   Stop:          docker-compose down"
echo "   Restart:       docker-compose restart"
echo ""
echo "🔍 Check status:"
echo "   curl http://localhost:8000/health"
echo "   curl http://localhost:8000/api/v1/watchlist"
echo ""
echo "⏰ Timeline:"
echo "   - First trending tokens: ~5 minutes"
echo "   - First stats: ~1 hour"
echo "   - First alerts: ~2 hours"
echo "   - Full watchlist: ~24 hours"
echo ""
echo "📚 Documentation:"
echo "   README.md - Overview"
echo "   USAGE.md  - Detailed guide"
echo "   PROJECT_STATUS.md - Current status"
echo ""
echo "🎯 Next steps:"
echo "   1. Monitor logs: docker-compose logs -f worker"
echo "   2. Check Telegram for alerts"
echo "   3. Review USAGE.md for tuning thresholds"
echo ""
echo "Happy hunting! 🎣"
