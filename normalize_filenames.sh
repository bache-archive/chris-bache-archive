#!/usr/bin/env bash
# Usage:
#   cd /path/to/repo/sources
#   bash ../normalize_filenames.sh           # dry run (prints changes only)
#   APPLY=1 bash ../normalize_filenames.sh   # actually rename files

set -euo pipefail

DRY_RUN=1
[[ "${APPLY:-0}" == "1" ]] && DRY_RUN=0

shopt -s nullglob
cd "$(dirname "${BASH_SOURCE[0]}")/sources"

echo "Working in: $(pwd)"
echo "Mode: $([[ $DRY_RUN -eq 1 ]] && echo DRY-RUN || echo APPLY)"
echo

changed=0
skipped=0
conflicts=0
unchanged=0

for f in *.md; do
  orig="$f"

  # Compute new name with perl (Unicode-aware)
  new="$(perl -CS -pe '
    # Normalize dashes (en/em) to plain hyphen
    s/\x{2013}|\x{2014}/-/g;

    # Ampersand -> and
    s/&/and/g;

    # Smart quotes to ASCII
    s/[“”]/"/g; s/[‘’]/'\''/g;

    # Ellipsis
    s/\x{2026}/.../g;

    # Underscore -> hyphen
    s/_/-/g;

    # Remove commas/colons (ugly in URLs)
    s/[,:]//g;

    # Parentheses -> hyphens (safer)
    s/[()]/-/g;

    # Collapse and trim spaces before turning into hyphens
    s/ +/ /g;
    s/^\s+//; s/\s+$//;

    # Spaces to hyphens
    s/ /-/g;

    # Collapse multiple hyphens
    s/-+/-/g;

    # Tidy trailing hyphen before extension
    s/-\.md$/.md/;

    # Lowercase
    $_ = lc $_;

    # Normalize extension
    s/\.(markdown|mdown)$/.md/;
  ' <<<"$orig")"

  if [[ "$orig" == "$new" ]]; then
    (( unchanged++ ))
    continue
  fi

  # If target exists, warn and skip (avoid overwrite)
  if [[ -e "$new" ]]; then
    echo "CONFLICT: '$orig' -> '$new'   (target exists, skipping)"
    (( conflicts++ ))
    continue
  fi

  echo "'$orig' -> '$new'"
  (( changed++ ))
  if [[ $DRY_RUN -eq 0 ]]; then
    mv -i -- "$orig" "$new" || { echo "SKIP: could not rename '$orig'"; (( skipped++ )); }
  fi
done

echo
echo "Summary:"
echo "  changed:   $changed"
echo "  unchanged: $unchanged"
echo "  conflicts: $conflicts"
echo "  skipped:   $skipped"
echo
[[ $DRY_RUN -eq 1 ]] && echo "Dry run complete. To apply changes: APPLY=1 bash ../normalize_filenames.sh"
