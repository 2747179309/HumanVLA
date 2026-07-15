#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${HUMANVLA_REPO:-$HOME/HumanVLA}"
BASE_BRANCH="${BASE_BRANCH:-main}"
PR_DRAFT="${PR_DRAFT:-true}"
MAX_FILE_BYTES=95000000

LOG_FILE="$REPO_DIR/.git/daily-sync.log"
LOCK_FILE="$REPO_DIR/.git/daily-sync.lock"

mkdir -p "$(dirname "$LOG_FILE")"

# 防止同一时间重复运行。
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "Another daily sync process is already running."
    exit 0
fi

exec >>"$LOG_FILE" 2>&1

echo
echo "============================================================"
echo "HumanVLA daily sync started: $(date --iso-8601=seconds)"
echo "User: $(id -un)"
echo "HOME: $HOME"
echo "Repository: $REPO_DIR"

cd "$REPO_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: $REPO_DIR is not a Git repository."
    exit 1
fi

branch="$(git symbolic-ref --quiet --short HEAD || true)"

if [[ -z "$branch" ]]; then
    echo "ERROR: detached HEAD; refusing automatic submission."
    exit 2
fi

case "$branch" in
    main|master)
        echo "ERROR: automatic commits are forbidden on '$branch'."
        echo "Please switch to a feature branch."
        exit 3
        ;;
esac

echo "Current branch: $branch"

remote_url="$(git remote get-url origin)"

case "$remote_url" in
    https://github.com/*)
        github_repo="${remote_url#https://github.com/}"
        ;;
    git@github.com:*)
        github_repo="${remote_url#git@github.com:}"
        ;;
    ssh://git@github.com/*)
        github_repo="${remote_url#ssh://git@github.com/}"
        ;;
    *)
        echo "ERROR: Unsupported GitHub remote URL: $remote_url"
        exit 4
        ;;
esac

github_repo="${github_repo%.git}"

echo "GitHub repository: $github_repo"
echo "Base branch: $BASE_BRANCH"

# GitHub CLI必须已提前登录，定时任务不能交互登录。
if ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI is not authenticated."
    echo "Run: gh auth login && gh auth setup-git"
    exit 5
fi

# 在改动Git索引前检查网络和权限。
git ls-remote --exit-code origin >/dev/null
git fetch origin "$BASE_BRANCH" --quiet

# 暂存所有未被.gitignore忽略的修改。
git add -A

# 阻止意外提交原始视频、ROS bag和数据库。
blocked_files="$(
    git diff --cached --name-only |
    grep -Ei '\.(mp4|mkv|avi|mov|bag|db3)$' || true
)"

if [[ -n "$blocked_files" ]]; then
    echo "ERROR: Blocked file types are staged:"
    echo "$blocked_files"
    echo "Please update .gitignore or unstage these files."
    exit 6
fi

# 阻止接近GitHub普通文件限制的大文件。
large_file_found=0

while IFS= read -r -d '' file; do
    [[ -f "$file" ]] || continue

    size="$(stat -c '%s' "$file")"

    if (( size > MAX_FILE_BYTES )); then
        echo "ERROR: Staged file is too large:"
        echo "  $file ($size bytes)"
        large_file_found=1
    fi
done < <(
    git diff --cached \
        --name-only \
        --diff-filter=ACMRT \
        -z
)

if (( large_file_found != 0 )); then
    exit 7
fi

# 检查空白错误和未解决的冲突标记。
if ! git diff --cached --check; then
    echo "ERROR: git diff --cached --check failed."
    exit 8
fi

created_commit=false

if git diff --cached --quiet; then
    echo "No new changes to commit."
else
    commit_message="chore: daily sync $(date '+%Y-%m-%d %H:%M')"

    git commit -m "$commit_message"
    created_commit=true

    echo "Created commit: $(git rev-parse --short HEAD)"
fi

# 即使今天没有新提交，也推送之前可能未推送的本地提交。
git push -u origin "$branch"

local_head="$(git rev-parse HEAD)"
remote_head="$(
    git ls-remote origin "refs/heads/$branch" |
    awk '{print $1}'
)"

echo "Local HEAD:  $local_head"
echo "Remote HEAD: $remote_head"

if [[ "$local_head" != "$remote_head" ]]; then
    echo "ERROR: Local and remote HEAD do not match."
    exit 9
fi

# 只有当前分支相对于main确实存在提交时，才创建PR。
ahead_count="$(
    git rev-list --count "origin/$BASE_BRANCH..HEAD"
)"

echo "Commits ahead of origin/$BASE_BRANCH: $ahead_count"

if (( ahead_count == 0 )); then
    echo "No commits ahead of $BASE_BRANCH; no pull request is required."
    echo "Daily sync completed: $(date --iso-8601=seconds)"
    exit 0
fi

# 检查该分支是否已有开放PR。
existing_pr_url="$(
    gh pr list \
        --repo "$github_repo" \
        --base "$BASE_BRANCH" \
        --head "$branch" \
        --state open \
        --limit 1 \
        --json url \
        --jq '.[0].url // ""'
)"

if [[ -n "$existing_pr_url" ]]; then
    echo "Existing pull request: $existing_pr_url"
    echo "The pushed commit has automatically updated this PR."
else
    body_file="$(mktemp)"
    trap 'rm -f "${body_file:-}"' EXIT

    cat >"$body_file" <<BODY
## Automated development pull request

This pull request tracks ongoing work from:

- **Head branch:** \`$branch\`
- **Base branch:** \`$BASE_BRANCH\`
- **Repository:** \`$github_repo\`

### Latest synchronized commit

- Commit: \`$(git rev-parse --short HEAD)\`
- Time: \`$(date --iso-8601=seconds)\`
- Automatic daily commit created: \`$created_commit\`

### Workflow

New daily commits pushed to \`$branch\` will automatically update this pull request.

This pull request should be reviewed and marked ready only after the current research task passes Claude and manual acceptance.
BODY

    title="HumanVLA: ${branch//-/ }"

    create_args=(
        pr create
        --repo "$github_repo"
        --base "$BASE_BRANCH"
        --head "$branch"
        --title "$title"
        --body-file "$body_file"
    )

    if [[ "$PR_DRAFT" == "true" ]]; then
        create_args+=(--draft)
    fi

    new_pr_url="$(gh "${create_args[@]}")"

    echo "Created pull request: $new_pr_url"
fi

echo "Daily sync and PR check completed: $(date --iso-8601=seconds)"
