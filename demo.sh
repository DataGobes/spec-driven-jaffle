#!/usr/bin/env bash
# Runs the full spec-driven flow: validate → generate → build → show results.
set -euo pipefail
cd "$(dirname "$0")"
export DBT_PROFILES_DIR=.

step() { printf "\n\033[1;36m▶ %s\033[0m\n" "$1"; }

step "1. Validate specs against platform conventions"
python tools/specgen.py validate

step "2. Generate contracts and tests from the specs"
python tools/specgen.py generate

step "3. Build and verify against real data"
dbt build --quiet
echo "All models built and all tests passed."

step "4. Result: dim_customer_value by tier"
python -c "
import duckdb
c = duckdb.connect('jaffle.duckdb', read_only=True)
print(c.sql('''select value_tier, count(*) as customers, sum(lifetime_revenue) as revenue
               from main.dim_customer_value group by 1 order by revenue desc'''))"
