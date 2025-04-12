(
  echo "<results>"
  echo "  <pytest-output>"
  pytest "$@"
  echo "  </pytest-output>"
  for path in "$@"; do
    if [ -d "$path" ]; then
      # It's a directory, process each .py file inside
      echo "  <module path=\"$path\">"
      for file in "$path"/*.py; do
        if [ -f "$file" ]; then
          echo "    <file path=\"$file\">"
          cat "$file"
          echo "    </file>"
        fi
      done
      echo "  </module>"
    elif [ -f "$path" ]; then
      # It's a file, process it directly
      echo "  <module path=\"$path\">"
      cat "$path"
      echo "  </module>"
    fi
  done
  echo "</results>"
) > aggregated_output.xml
