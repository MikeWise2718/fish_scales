#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check if ADW ID is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: ADW ID required${NC}"
    echo "Usage: $0 <ADW_ID> [--keep-branch]"
    echo "Example: $0 ADW-123                # Deletes worktree and branch"
    echo "         $0 ADW-123 --keep-branch   # Deletes worktree only"
    exit 1
fi

ADW_ID=$1
DELETE_BRANCH=true

# Check for --keep-branch flag
if [ "$2" == "--keep-branch" ]; then
    DELETE_BRANCH=false
fi

echo -e "${BLUE}Purging worktree for ${ADW_ID}...${NC}"
echo ""

# Get worktree path
WORKTREE_PATH="trees/${ADW_ID}"

# Check if worktree exists
if [ ! -d "$WORKTREE_PATH" ]; then
    echo -e "${YELLOW}Warning: Worktree directory not found at $WORKTREE_PATH${NC}"
else
    echo -e "${GREEN}Found worktree at: $WORKTREE_PATH${NC}"
fi

# Get branch name from worktree (if it exists in git)
BRANCH_NAME=$(git worktree list --porcelain | grep -A1 "worktree.*${WORKTREE_PATH}" | grep "branch" | cut -d' ' -f2 | sed 's|refs/heads/||')

# If we couldn't get it from worktree list, try to infer from ADW ID
if [ -z "$BRANCH_NAME" ]; then
    # Look for branches that contain the ADW ID (convert to lowercase for branch search)
    ADW_ID_LOWER=$(echo "$ADW_ID" | tr '[:upper:]' '[:lower:]')
    POSSIBLE_BRANCHES=$(git branch -a | grep -i "adw-${ADW_ID_LOWER}" | sed 's/^[* ]*//' | grep -v "remotes/")
    
    if [ ! -z "$POSSIBLE_BRANCHES" ]; then
        # If we found exactly one match, use it
        BRANCH_COUNT=$(echo "$POSSIBLE_BRANCHES" | wc -l | tr -d ' ')
        if [ "$BRANCH_COUNT" -eq "1" ]; then
            BRANCH_NAME=$(echo "$POSSIBLE_BRANCHES" | head -1)
            echo -e "${YELLOW}Inferred branch from ADW ID: $BRANCH_NAME${NC}"
        else
            echo -e "${YELLOW}Found multiple branches containing ADW ID:${NC}"
            echo "$POSSIBLE_BRANCHES" | sed 's/^/  /'
            echo -e "${YELLOW}Will not delete any branch (ambiguous)${NC}"
            DELETE_BRANCH=false
        fi
    else
        echo -e "${YELLOW}Warning: Could not determine branch name${NC}"
    fi
else
    echo -e "${GREEN}Associated branch: $BRANCH_NAME${NC}"
fi

# Kill any processes using ports for this ADW
echo ""
echo -e "${GREEN}Checking for processes on ADW ports...${NC}"

# Calculate ports (same hash-based logic as Python)
hash_value=$(echo -n "$ADW_ID" | md5sum | cut -c1-8)
port_offset=$((0x${hash_value} % 15))
backend_port=$((9100 + port_offset))
frontend_port=$((9200 + port_offset))

# Kill backend process
backend_pid=$(lsof -ti:$backend_port 2>/dev/null)
if [ ! -z "$backend_pid" ]; then
    kill -9 $backend_pid 2>/dev/null
    echo -e "${YELLOW}  Killed process on backend port $backend_port${NC}"
else
    echo -e "${GREEN}  No process on backend port $backend_port${NC}"
fi

# Kill frontend process
frontend_pid=$(lsof -ti:$frontend_port 2>/dev/null)
if [ ! -z "$frontend_pid" ]; then
    kill -9 $frontend_pid 2>/dev/null
    echo -e "${YELLOW}  Killed process on frontend port $frontend_port${NC}"
else
    echo -e "${GREEN}  No process on frontend port $frontend_port${NC}"
fi

# Remove worktree
echo ""
echo -e "${GREEN}Removing worktree...${NC}"
if git worktree list | grep -q "$WORKTREE_PATH"; then
    git worktree remove -f "$WORKTREE_PATH" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Worktree removed from git${NC}"
    else
        echo -e "${RED}  Failed to remove worktree from git${NC}"
        # Try to prune if remove failed
        git worktree prune
    fi
else
    echo -e "${YELLOW}  Worktree not registered in git${NC}"
fi

# Remove directory if it still exists
if [ -d "$WORKTREE_PATH" ]; then
    rm -rf "$WORKTREE_PATH"
    echo -e "${GREEN}  ✓ Worktree directory removed${NC}"
fi

# Handle branch deletion
if [ "$DELETE_BRANCH" == "true" ] && [ ! -z "$BRANCH_NAME" ]; then
    echo ""
    echo -e "${GREEN}Deleting branch: $BRANCH_NAME${NC}"
    
    # Check if we're currently on this branch
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" == "$BRANCH_NAME" ]; then
        echo -e "${YELLOW}  Switching to main branch first...${NC}"
        git checkout main
    fi
    
    # Delete local branch
    git branch -D "$BRANCH_NAME" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Local branch deleted${NC}"
    else
        echo -e "${YELLOW}  Could not delete local branch (may not exist)${NC}"
    fi
    
    # Ask about remote branch
    echo -e "${YELLOW}  Note: Remote branch not deleted. To delete it, run:${NC}"
    echo -e "${BLUE}    git push origin --delete $BRANCH_NAME${NC}"
fi

# Clean up any stale worktree entries
git worktree prune

echo ""
echo -e "${GREEN}✓ Purge complete for ${ADW_ID}${NC}"

# Show summary
echo ""
echo -e "${BLUE}Summary:${NC}"
echo -e "  ADW ID: ${ADW_ID}"
echo -e "  Worktree path: ${WORKTREE_PATH}"
[ ! -z "$BRANCH_NAME" ] && echo -e "  Branch: ${BRANCH_NAME}"
echo -e "  Backend port: ${backend_port}"
echo -e "  Frontend port: ${frontend_port}"