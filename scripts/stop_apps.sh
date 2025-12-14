#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping Natural Language SQL Interface and ADW Services...${NC}"

# Kill any running start.sh processes
echo -e "${GREEN}Killing start.sh processes...${NC}"
pkill -f "start.sh" 2>/dev/null

# Kill webhook server
echo -e "${GREEN}Killing webhook server...${NC}"
pkill -f "trigger_webhook.py" 2>/dev/null

# Kill processes on main ports
echo -e "${GREEN}Killing processes on main ports (5173, 8000, 8001)...${NC}"
lsof -ti:5173,8000,8001 | xargs kill -9 2>/dev/null

# Kill processes on isolated ADW ports
echo -e "${GREEN}Killing processes on isolated ADW backend ports (9100-9114)...${NC}"
for port in {9100..9114}; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        kill -9 $pid 2>/dev/null && echo -e "${YELLOW}  Killed process on port $port${NC}"
    fi
done

echo -e "${GREEN}Killing processes on isolated ADW frontend ports (9200-9214)...${NC}"
for port in {9200..9214}; do
    pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        kill -9 $pid 2>/dev/null && echo -e "${YELLOW}  Killed process on port $port${NC}"
    fi
done

# Kill any uvicorn or vite processes that might be hanging
echo -e "${GREEN}Killing any remaining uvicorn processes...${NC}"
pkill -f "uvicorn" 2>/dev/null

echo -e "${GREEN}Killing any remaining vite processes...${NC}"
pkill -f "vite" 2>/dev/null

echo -e "${GREEN}✓ All services stopped successfully!${NC}"