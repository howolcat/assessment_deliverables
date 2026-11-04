#!/usr/bin/env bash
# reports/*.md 와 README.md 안의 상대경로 링크가 실제로 존재하는지 확인
cd "$(dirname "$0")"
missing=0
for f in *.md; do
  grep -oE "\]\(([^)#: ]+)\)" "$f" | sed -E 's/^\]\(//; s/\)$//' | while read -r p; do
    [ -e "$p" ] || { echo "없음: $f → $p"; }
  done
done
cd ..
grep -oE "\]\((reports/[^)]+)\)" README.md | sed -E 's/^\]\(//; s/\)$//' | while read -r p; do
  [ -e "$p" ] || echo "없음: README.md → $p"
done
echo "점검 끝 (위에 '없음'이 없으면 모든 링크 정상)"
