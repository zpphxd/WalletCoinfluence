#!/bin/bash

# Setup script for Ollama LLM models

echo "🤖 Setting up Ollama LLM for Alpha Wallet Scout"
echo "================================================"
echo ""

# Check if Ollama container is running
if ! docker ps | grep -q wallet_scout_ollama; then
    echo "❌ Ollama container not running. Start it first with:"
    echo "   docker-compose up -d ollama"
    exit 1
fi

echo "✅ Ollama container is running"
echo ""

# Pull recommended models
echo "📥 Pulling recommended models (this may take a while)..."
echo ""

# Llama 3.2 (3B) - Fast, good for analysis
echo "1️⃣  Pulling Llama 3.2 (3B) - Fast & efficient..."
docker exec wallet_scout_ollama ollama pull llama3.2:latest

# Phi-3 (3.8B) - Great for structured output
echo ""
echo "2️⃣  Pulling Phi-3 (3.8B) - Excellent for JSON responses..."
docker exec wallet_scout_ollama ollama pull phi3:latest

# Qwen 2.5 (3B) - Alternative option
echo ""
echo "3️⃣  Pulling Qwen 2.5 (3B) - Alternative lightweight model..."
docker exec wallet_scout_ollama ollama pull qwen2.5:3b

echo ""
echo "✅ Models installed!"
echo ""
echo "📊 Available models:"
docker exec wallet_scout_ollama ollama list

echo ""
echo "🎯 Recommended model for signal analysis: phi3:latest"
echo ""
echo "To test the LLM:"
echo "  docker exec -it wallet_scout_ollama ollama run phi3"
echo ""
echo "To use in Python:"
echo "  from src.analytics.llm_analyzer import LLMSignalAnalyzer"
echo "  analyzer = LLMSignalAnalyzer(model='phi3:latest')"
echo ""
echo "Done! 🚀"
