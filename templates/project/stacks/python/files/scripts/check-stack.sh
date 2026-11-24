# scripts/check.sh から読まれる（run・run_counted・need はそちらにある）。Python の確かめ。
if need python3 "Python 3 を入れる"; then
  if python3 -c 'import pytest' 2>/dev/null; then
    run_counted '([0-9]+) passed' python3 -m pytest -q
  else
    fail=1; echo "✗ 未実行：pytest がありません（pip install -e '.[dev]'）"
  fi
fi
