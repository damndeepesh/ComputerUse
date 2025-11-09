#!/bin/bash

# Script to clean all workflows and optionally clear database entries
# Usage: ./clean_workflows.sh [--all] [--no-confirm]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
CLEAR_ALL=false
NO_CONFIRM=false

for arg in "$@"; do
    case $arg in
        --all)
            CLEAR_ALL=true
            shift
            ;;
        --no-confirm)
            NO_CONFIRM=true
            shift
            ;;
        *)
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Database paths
DB_PATH="data/workflows.db"
BACKEND_DB_PATH="backend/data/workflows.db"

# Data directories
SCREENSHOTS_DIR="data/screenshots"
RECORDINGS_DIR="data/recordings"
TRANSCRIPTS_DIR="data/transcripts"
BACKEND_SCREENSHOTS="backend/data/screenshots"
BACKEND_RECORDINGS="backend/data/recordings"
BACKEND_TRANSCRIPTS="backend/data/transcripts"

echo -e "${YELLOW}🧹 Workflow Cleanup Script${NC}"
echo "=================================="
echo ""

# Function to check if database exists and get count
get_workflow_count() {
    local db_path="$1"
    if [ -f "$db_path" ]; then
        sqlite3 "$db_path" "SELECT COUNT(*) FROM workflows;" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Count workflows
COUNT1=$(get_workflow_count "$DB_PATH")
COUNT2=$(get_workflow_count "$BACKEND_DB_PATH")
TOTAL_COUNT=$((COUNT1 + COUNT2))

if [ "$TOTAL_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No workflows found in database(s)${NC}"
    exit 0
fi

echo -e "Found ${YELLOW}$TOTAL_COUNT${NC} workflow(s) to delete"
echo ""

if [ "$CLEAR_ALL" = true ]; then
    echo -e "${RED}⚠️  FULL CLEANUP MODE${NC}"
    echo "This will delete:"
    echo "  • All workflows from database"
    echo "  • All screenshots"
    echo "  • All recordings"
    echo "  • All transcripts"
    echo ""
fi

# Confirmation prompt
if [ "$NO_CONFIRM" = false ]; then
    if [ "$CLEAR_ALL" = true ]; then
        read -p "Are you sure you want to delete EVERYTHING? (yes/no): " confirm
    else
        read -p "Delete all workflows from database? (yes/no): " confirm
    fi
    
    if [ "$confirm" != "yes" ]; then
        echo -e "${YELLOW}Cancelled.${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}🗑️  Starting cleanup...${NC}"
echo ""

# Clean main database
if [ -f "$DB_PATH" ]; then
    COUNT=$(get_workflow_count "$DB_PATH")
    if [ "$COUNT" -gt 0 ]; then
        echo -e "Clearing ${COUNT} workflow(s) from ${DB_PATH}..."
        sqlite3 "$DB_PATH" "DELETE FROM workflows;" 2>/dev/null || {
            echo -e "${RED}❌ Error clearing database: $DB_PATH${NC}"
            exit 1
        }
        echo -e "${GREEN}✅ Cleared ${COUNT} workflow(s)${NC}"
    fi
fi

# Clean backend database
if [ -f "$BACKEND_DB_PATH" ]; then
    COUNT=$(get_workflow_count "$BACKEND_DB_PATH")
    if [ "$COUNT" -gt 0 ]; then
        echo -e "Clearing ${COUNT} workflow(s) from ${BACKEND_DB_PATH}..."
        sqlite3 "$BACKEND_DB_PATH" "DELETE FROM workflows;" 2>/dev/null || {
            echo -e "${RED}❌ Error clearing database: $BACKEND_DB_PATH${NC}"
            exit 1
        }
        echo -e "${GREEN}✅ Cleared ${COUNT} workflow(s)${NC}"
    fi
fi

# Clean data files if --all flag is set
if [ "$CLEAR_ALL" = true ]; then
    echo ""
    echo -e "${YELLOW}Cleaning data files...${NC}"
    echo ""
    
    # Clean screenshots
    echo -e "${YELLOW}📸 Cleaning screenshots...${NC}"
    for screenshot_dir in "$SCREENSHOTS_DIR" "$BACKEND_SCREENSHOTS"; do
        if [ -d "$screenshot_dir" ]; then
            # Use absolute path
            abs_path=$(cd "$SCRIPT_DIR" && cd "$screenshot_dir" 2>/dev/null && pwd 2>/dev/null || echo "")
            if [ -n "$abs_path" ] && [ -d "$abs_path" ]; then
                file_count=$(find "$abs_path" -type f -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
                if [ "$file_count" -gt 0 ]; then
                    echo -e "  Found ${YELLOW}${file_count}${NC} screenshot(s) in ${abs_path}"
                    echo -e "  Deleting..."
                    find "$abs_path" -type f -name "*.png" -delete 2>/dev/null
                    # Verify deletion
                    remaining=$(find "$abs_path" -type f -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$remaining" -eq 0 ]; then
                        echo -e "  ${GREEN}✅ Deleted ${file_count} screenshot(s)${NC}"
                    else
                        echo -e "  ${YELLOW}⚠️  Warning: ${remaining} file(s) still remain${NC}"
                    fi
                else
                    echo -e "  No screenshot files found in ${abs_path}"
                fi
            else
                echo -e "  ${YELLOW}⚠️  Could not resolve path: ${screenshot_dir}${NC}"
            fi
        else
            echo -e "  ${YELLOW}⚠️  Directory does not exist: ${screenshot_dir}${NC}"
        fi
    done
    echo ""
    
    # Clean recordings
    echo -e "${YELLOW}🎙️  Cleaning recordings...${NC}"
    for recording_dir in "$RECORDINGS_DIR" "$BACKEND_RECORDINGS"; do
        if [ -d "$recording_dir" ]; then
            # Use absolute path
            abs_path=$(cd "$SCRIPT_DIR" && cd "$recording_dir" 2>/dev/null && pwd 2>/dev/null || echo "")
            if [ -n "$abs_path" ] && [ -d "$abs_path" ]; then
                file_count=$(find "$abs_path" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \) 2>/dev/null | wc -l | tr -d ' ')
                if [ "$file_count" -gt 0 ]; then
                    echo -e "  Found ${YELLOW}${file_count}${NC} recording(s) in ${abs_path}"
                    echo -e "  Deleting..."
                    find "$abs_path" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \) -delete 2>/dev/null
                    # Verify deletion
                    remaining=$(find "$abs_path" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \) 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$remaining" -eq 0 ]; then
                        echo -e "  ${GREEN}✅ Deleted ${file_count} recording(s)${NC}"
                    else
                        echo -e "  ${YELLOW}⚠️  Warning: ${remaining} file(s) still remain${NC}"
                    fi
                else
                    echo -e "  No recording files found in ${abs_path}"
                fi
            else
                echo -e "  ${YELLOW}⚠️  Could not resolve path: ${recording_dir}${NC}"
            fi
        else
            echo -e "  ${YELLOW}⚠️  Directory does not exist: ${recording_dir}${NC}"
        fi
    done
    echo ""
    
    # Clean transcripts
    echo -e "${YELLOW}📝 Cleaning transcripts...${NC}"
    for transcript_dir in "$TRANSCRIPTS_DIR" "$BACKEND_TRANSCRIPTS"; do
        if [ -d "$transcript_dir" ]; then
            # Use absolute path
            abs_path=$(cd "$SCRIPT_DIR" && cd "$transcript_dir" 2>/dev/null && pwd 2>/dev/null || echo "")
            if [ -n "$abs_path" ] && [ -d "$abs_path" ]; then
                file_count=$(find "$abs_path" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
                if [ "$file_count" -gt 0 ]; then
                    echo -e "  Found ${YELLOW}${file_count}${NC} transcript(s) in ${abs_path}"
                    echo -e "  Deleting..."
                    find "$abs_path" -type f -name "*.json" -delete 2>/dev/null
                    # Verify deletion
                    remaining=$(find "$abs_path" -type f -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$remaining" -eq 0 ]; then
                        echo -e "  ${GREEN}✅ Deleted ${file_count} transcript(s)${NC}"
                    else
                        echo -e "  ${YELLOW}⚠️  Warning: ${remaining} file(s) still remain${NC}"
                    fi
                else
                    echo -e "  No transcript files found in ${abs_path}"
                fi
            else
                echo -e "  ${YELLOW}⚠️  Could not resolve path: ${transcript_dir}${NC}"
            fi
        else
            echo -e "  ${YELLOW}⚠️  Directory does not exist: ${transcript_dir}${NC}"
        fi
    done
    echo ""
fi

echo ""
echo -e "${GREEN}✨ Cleanup completed!${NC}"

# Verify cleanup
FINAL_COUNT1=$(get_workflow_count "$DB_PATH")
FINAL_COUNT2=$(get_workflow_count "$BACKEND_DB_PATH")
FINAL_TOTAL=$((FINAL_COUNT1 + FINAL_COUNT2))

if [ "$FINAL_TOTAL" -eq 0 ]; then
    echo -e "${GREEN}✅ Verification: All workflows deleted${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: ${FINAL_TOTAL} workflow(s) still remain${NC}"
fi

