#!/bin/bash
# Usage: ./script.sh <newer_commit> <earlier_commit>
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <newer_commit> <earlier_commit>"
    exit 1
fi

newer_commit="$1"
earlier_commit="$2"
PROJECT_DESCRIPTOR="codebase A"

# Generate diff between the two commits for .py files
diff_output=$(git diff "$earlier_commit" "$newer_commit" -- '*.py')

# Generate the "starting state" output by listing all .py files from the earlier commit.
# This simulates: 
#   PROJECT_DESCRIPTOR="codebase A"; find . -name "*.py" -not -type l -exec sh -c 'echo "<file path=\"${1}\" project=\"${PROJECT_DESCRIPTOR}\">"; cat "${1}"; echo "</file>"' sh {} \;
starting_state=""

# List all .py files tracked in the earlier commit (using ls-tree to avoid switching branches).
file_list=$(git ls-tree -r --name-only "$earlier_commit" | grep '\.py$')

# Iterate through each file and extract its content from the earlier commit.
while IFS= read -r file; do
    # Get the file content as stored in the commit.
    file_content=$(git show "$earlier_commit:$file")
    starting_state+=$'\n'"<file path=\"$file\" project=\"$PROJECT_DESCRIPTOR\">"$'\n'
    starting_state+="$file_content"$'\n'
    starting_state+="</file>"$'\n'
done <<< "$file_list"

# Output the final template populated with the diff and starting state.
cat <<EOF
we started with <starting state> and made changes, see <diff>. do the changes make things better or worse? what was the intended purpose of the changes? summarize them.:

<diff>
$diff_output
</diff>

<starting state>
$starting_state
</starting state>
EOF

