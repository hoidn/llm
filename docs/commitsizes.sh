#!/bin/bash

# Script to analyze markdown files across the last 10 commits in a git repository

# Check if the current directory is a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "Error: Current directory is not a git repository."
    exit 1
fi

# Get the relative path of current directory from the repo root
REPO_ROOT=$(git rev-parse --show-toplevel)
CURRENT_DIR=$(pwd)
REL_PATH=${CURRENT_DIR#$REPO_ROOT/}

if [ "$CURRENT_DIR" = "$REPO_ROOT" ]; then
    REL_PATH=""
fi

echo "Analyzing markdown files in directory: $REL_PATH"

# First, analyze the current directory and show tracked vs. untracked files
echo "Current directory analysis:"
CURRENT_RESULT=$(PROJECT_DESCRIPTOR="docs"; find . -name "*.md" -not -type l -exec sh -c 'echo "<file path=\"${1}\" project=\"${PROJECT_DESCRIPTOR}\">"; cat "${1}"; echo "</file>"' sh {} \; | wc)
echo "All files (including untracked): $CURRENT_RESULT"

TOTAL_FILES=$(find . -name "*.md" -not -type l | wc -l)
echo "Total files: $TOTAL_FILES"

echo "Untracked markdown files:"
UNTRACKED_FILES_LIST=$(git ls-files --others --exclude-standard . | grep "\.md$")
echo "$UNTRACKED_FILES_LIST"
UNTRACKED_FILES=$(echo "$UNTRACKED_FILES_LIST" | wc -l)
TRACKED_FILES=$((TOTAL_FILES - UNTRACKED_FILES))
echo "Tracked files: $TRACKED_FILES"
echo "Untracked files: $UNTRACKED_FILES"

echo "Note: Commit analysis will only count tracked files that existed in each commit."
echo "----------------------------------------"

# Create a temporary directory for worktrees
TEMP_DIR=$(mktemp -d)
echo "Created temporary directory: $TEMP_DIR"

# Function to clean up temporary directories
cleanup() {
    echo "Cleaning up temporary directories..."
    # Remove all temporary worktrees
    for dir in "$TEMP_DIR"/worktree-*; do
        if [ -d "$dir" ]; then
            git worktree remove --force "$dir" 2>/dev/null
        fi
    done
    # Remove the temporary directory
    rm -rf "$TEMP_DIR"
    echo "Cleanup complete."
}

# Set up trap to ensure cleanup on exit
trap cleanup EXIT

# Get the last 10 commit hashes
COMMITS=$(git log --max-count=10 --pretty=format:"%H")

# Check if we have any commits
if [ -z "$COMMITS" ]; then
    echo "Error: No commits found in this repository."
    exit 1
fi

# Create a results file
RESULTS_FILE="md_file_analysis_results.txt"
echo "Markdown File Analysis Results" > "$RESULTS_FILE"
echo "Directory: $REL_PATH" >> "$RESULTS_FILE"
echo "All files in current directory (including untracked): $CURRENT_RESULT" >> "$RESULTS_FILE"
echo "Untracked markdown files:" >> "$RESULTS_FILE"
echo "$UNTRACKED_FILES_LIST" >> "$RESULTS_FILE"
echo "===============================" >> "$RESULTS_FILE"

# Process each commit
COMMIT_COUNT=0
for COMMIT in $COMMITS; do
    COMMIT_COUNT=$((COMMIT_COUNT + 1))
    
    # Get commit message and date for reference
    COMMIT_INFO=$(git log -1 --pretty=format:"%h - %s (%ci)" "$COMMIT")
    
    echo -e "\nAnalyzing commit ($COMMIT_COUNT/10): $COMMIT_INFO"
    echo -e "\nCommit: $COMMIT_INFO" >> "$RESULTS_FILE"
    
    # Create a worktree for this commit (suppress output)
    WORKTREE_PATH="$TEMP_DIR/worktree-$COMMIT_COUNT"
    
    if ! git worktree add --detach "$WORKTREE_PATH" "$COMMIT" > /dev/null 2>&1; then
        echo "Error: Failed to create worktree for commit $COMMIT. Skipping."
        echo "Error: Failed to create worktree for commit $COMMIT. Skipping." >> "$RESULTS_FILE"
        continue
    fi
    
    # Run the analysis command in the worktree
    if [ -z "$REL_PATH" ]; then
        TARGET_DIR="$WORKTREE_PATH"
    else
        TARGET_DIR="$WORKTREE_PATH/$REL_PATH"
    fi
    
    # Check if the directory exists in this commit
    if [ ! -d "$TARGET_DIR" ]; then
        echo "Directory $REL_PATH does not exist in commit $COMMIT. Skipping."
        echo "Directory $REL_PATH does not exist in commit $COMMIT. Skipping." >> "$RESULTS_FILE"
        git worktree remove --force "$WORKTREE_PATH" > /dev/null 2>&1
        continue
    fi
    
    # Change to the target directory in the worktree
    cd "$TARGET_DIR" || continue
    
    # Count the number of markdown files
    FILE_COUNT=$(find . -name "*.md" -not -type l | wc -l)
    echo "Number of markdown files: $FILE_COUNT" 
    echo "Number of markdown files: $FILE_COUNT" >> "$RESULTS_FILE"
    
    # Run the exact command as specified
    RESULT=$(PROJECT_DESCRIPTOR="docs"; find . -name "*.md" -not -type l -exec sh -c 'echo "<file path=\"${1}\" project=\"${PROJECT_DESCRIPTOR}\">"; cat "${1}"; echo "</file>"' sh {} \; | wc)
    
    # Display and save results
    echo "$RESULT"
    echo "$RESULT" >> "$RESULTS_FILE"
    
    # Go back to original directory
    cd - > /dev/null || exit 1
    
    # Remove the worktree (suppress output)
    git worktree remove --force "$WORKTREE_PATH" > /dev/null 2>&1
done

echo -e "\nAnalysis complete. Results saved to $RESULTS_FILE"
