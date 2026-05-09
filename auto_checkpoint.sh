#!/bin/bash

REPO="$HOME/jarvis1-1"
REMOTE="origin"

cd "$REPO" || exit 1

if [ "$1" == "save" ] || [ -z "$1" ]; then

  if [[ -z $(git status --porcelain) ]]; then
    echo ">> Nothing to save"
    exit 0
  fi

  MSG="${2:-checkpoint: $(date '+%H:%M %b %d')}"
  BRANCH=$(git branch --show-current)

  git add -A
  git commit -m "$MSG"
  git push "$REMOTE" "$BRANCH"

  echo "✅ Saved: $MSG"
  exit 0
fi

if [ "$1" == "feature" ]; then
  BRANCH_NAME="feature/$2"

  git checkout -b "$BRANCH_NAME"
  git push -u origin "$BRANCH_NAME"

  echo "✅ Feature branch: $BRANCH_NAME"
  exit 0
fi

if [ "$1" == "merge" ]; then
  CURRENT=$(git branch --show-current)

  git checkout main
  git merge "$CURRENT"
  git push origin main

  echo "✅ Merged $CURRENT → main"
  exit 0
fi

if [ "$1" == "report" ]; then
  git status
  git log --oneline -10
  exit 0
fi

echo "Usage: save | feature <name> | merge | report"
