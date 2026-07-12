#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$HOME/HumanVLA"
LOG_FILE="$PROJECT_ROOT/.git/daily-sync.log"
MAX_FILE_SIZE=$((45 * 1024 * 1024))

mkdir -p "$(dirname "$LOG_FILE")"
exec >>"$LOG_FILE" 2>&1

echo
echo "===== $(date '+%F %T') daily sync started ====="

cd "$PROJECT_ROOT"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: $PROJECT_ROOT is not a Git repository."
    exit 1
fi

BRANCH="$(git branch --show-current)"

if [[ -z "$BRANCH" ]]; then
    echo "ERROR: detached HEAD."
    exit 1
fi

# 防止自动脚本直接推送main
if [[ "$BRANCH" == "main" ]]; then
    echo "ERROR: refusing automatic commit on main."
    echo "Switch to openpose-mot or another feature branch."
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI authentication is unavailable."
    exit 1
fi

git add -A

if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
fi

# 检查敏感文件和大文件
while IFS= read -r FILE; do
    [[ -z "$FILE" ]] && continue

    case "$FILE" in
        .env|.env.*|*.pem|*.key|*.p12|*credentials*|*token*|*secret*)
            echo "ERROR: possible sensitive file staged: $FILE"
            exit 1
            ;;
    esac

    if [[ -f "$FILE" ]]; then
        SIZE="$(stat -c '%s' "$FILE")"

        if (( SIZE > MAX_FILE_SIZE )); then
            echo "ERROR: staged file exceeds 45 MiB: $FILE"
            exit 1
        fi
    fi
done < <(git diff --cached --name-only)

# 检查尾随空格、冲突标记等问题
git diff --cached --check

COMMIT_MESSAGE="chore: daily sync $(date +%F)"

git commit -m "$COMMIT_MESSAGE"

# 远程分支存在时先同步
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    git pull --rebase origin "$BRANCH"
fi

git push -u origin "$BRANCH"

echo "Committed and pushed branch: $BRANCH"
echo "===== $(date '+%F %T') daily sync completed ====="
