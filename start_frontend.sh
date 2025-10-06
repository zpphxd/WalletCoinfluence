#!/bin/bash
# Start Alpha Wallet Scout Frontend + Backend

echo "🚀 Starting Alpha Wallet Scout Dashboard..."
echo ""

# Start FastAPI backend in background
echo "📡 Starting API backend on http://localhost:8000"
cd "/Users/zachpowers/Wallet Signal"
/Applications/Docker.app/Contents/Resources/bin/docker exec wallet_scout_worker python3 /app/src/api/main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend dev server
echo "🎨 Starting frontend on http://localhost:3000"
cd "/Users/zachpowers/Wallet Signal/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Dashboard running!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user to stop
wait
