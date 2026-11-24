# scripts/check.sh から読まれる（run・run_counted・need はそちらにある）。Node.js の確かめ。
if need node "Node.js 22 以上を入れる" && need npm "Node.js に付いてくる"; then
  run_counted '# pass ([0-9]+)' npm test --silent
fi
