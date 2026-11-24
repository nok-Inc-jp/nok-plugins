# scripts/check.sh から読まれる（run・run_counted・need はそちらにある）。Rust の確かめ。
if need cargo "rustup で入れる（https://rustup.rs）"; then
  run cargo fmt --all -- --check
  run cargo clippy --all-targets -- -D warnings
  run_counted 'test result: ok\. ([0-9]+) passed' cargo test
fi
