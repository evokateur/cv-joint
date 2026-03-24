#!/usr/bin/env bash

BASE="/Users/wesley/obsidian-vault/areas/job-search/cv-joint"

find "$BASE" -name "cv.json" | while read -r file; do
    tmp=$(mktemp)
    jq '.summary_of_qualifications = (.summary_of_qualifications | if type == "array" then join(" ") else . end)' "$file" >"$tmp" && mv "$tmp" "$file"
    echo "Patched: $file"
done
