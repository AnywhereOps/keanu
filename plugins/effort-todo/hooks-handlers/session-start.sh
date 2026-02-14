#!/usr/bin/env bash
# effort-todo session start hook
# Reads TODO.md, parses cool/warm/hot sections, injects effort-aware context

TODO_FILE="TODO.md"

# If no TODO.md exists, output nothing
if [ ! -f "$TODO_FILE" ]; then
    echo '{"additionalContext": ""}'
    exit 0
fi

# Count tasks per section
count_tasks() {
    local section="$1"
    local file="$2"
    local in_section=0
    local total=0
    local done=0

    while IFS= read -r line; do
        if echo "$line" | grep -qi "^## .*${section}"; then
            in_section=1
            continue
        fi
        if [ $in_section -eq 1 ] && echo "$line" | grep -q "^## "; then
            break
        fi
        if [ $in_section -eq 1 ]; then
            if echo "$line" | grep -q "^\- \[ \]"; then
                total=$((total + 1))
            fi
            if echo "$line" | grep -q "^\- \[x\]"; then
                done=$((done + 1))
            fi
        fi
    done < "$file"

    echo "${total}:${done}"
}

# Gather task descriptions as a single escaped line
get_tasks() {
    local section="$1"
    local file="$2"
    local in_section=0
    local result=""

    while IFS= read -r line; do
        if echo "$line" | grep -qi "^## .*${section}"; then
            in_section=1
            continue
        fi
        if [ $in_section -eq 1 ] && echo "$line" | grep -q "^## "; then
            break
        fi
        if [ $in_section -eq 1 ] && echo "$line" | grep -q "^\- \[ \]"; then
            task=$(echo "$line" | sed 's/^- \[ \] //')
            # Escape special JSON characters
            task=$(echo "$task" | sed 's/\\/\\\\/g; s/"/\\"/g')
            result+="\\n  - ${task}"
        fi
    done < "$file"

    echo "$result"
}

# Parse each section
cool_counts=$(count_tasks "COOL" "$TODO_FILE")
warm_counts=$(count_tasks "WARM" "$TODO_FILE")
hot_counts=$(count_tasks "HOT" "$TODO_FILE")

cool_remaining=$(echo "$cool_counts" | cut -d: -f1)
cool_done=$(echo "$cool_counts" | cut -d: -f2)
warm_remaining=$(echo "$warm_counts" | cut -d: -f1)
warm_done=$(echo "$warm_counts" | cut -d: -f2)
hot_remaining=$(echo "$hot_counts" | cut -d: -f1)
hot_done=$(echo "$hot_counts" | cut -d: -f2)

cool_tasks=$(get_tasks "COOL" "$TODO_FILE")
warm_tasks=$(get_tasks "WARM" "$TODO_FILE")
hot_tasks=$(get_tasks "HOT" "$TODO_FILE")

# Build context as properly escaped JSON string
context="TODO.md effort levels:"
context+="\\nCOOL (5-15 min): ${cool_remaining} remaining, ${cool_done} done"
context+="${cool_tasks}"
context+="\\nWARM (20-45 min): ${warm_remaining} remaining, ${warm_done} done"
context+="${warm_tasks}"
context+="\\nHOT (1-2 hours): ${hot_remaining} remaining, ${hot_done} done"
context+="${hot_tasks}"
context+="\\n\\nAsk the user how they are feeling, then suggest 2-3 tasks from the matching effort level. If they do not say, offer one from each level as options."

# Output valid JSON
printf '{"additionalContext": "%s"}' "$context"
