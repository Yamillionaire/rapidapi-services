#!/usr/bin/env bash
# Keep-warm pinger for the twelve RapidAPI competitor services on Render free tier.
# Render grants 750 free instance hours per WORKSPACE per month (shared).
# Twelve always-on services would burn ~8,928h and get ALL services suspended,
# so pings run only inside a daily window: 09:00-10:50 America/New_York.
# Window math: 110min x 12 services x 31 days = 682h worst month, ~68h headroom
# for organic traffic. A spun-down service consumes no hours.
# (Window history: 09:00-16:00 for three services, 09:00-14:00 for four,
# 09:00-13:00 for five, 09:00-12:00 for six (all 2026-10-28),
# 09:00-11:30 for seven, 09:00-11:00 for nine, 09:00-11:00 held for ten
# and eleven (2026-10-29/30), 09:00-10:50 for twelve (2026-10-31,
# DriftCheck added; the window narrows so the worst month stays 682h).)
# NOTE: the URL list below carries all twelve services.
# Usage: keepwarm.sh [--force]   (--force ignores the window, for manual tests)
set -u
LOG="$(dirname "$0")/keepwarm.log"
URLS="https://stablefx-currency-rates.onrender.com/health https://cleanlist-email-verifier.onrender.com/health https://edgar-fundamentals.onrender.com/health https://geobase-cities.onrender.com/health https://cleanextract-articles.onrender.com/health https://swiftrewrite.onrender.com/health https://wordbase-dictionary.onrender.com/health https://newsbase-headlines.onrender.com/health https://swifttranslate-72rx.onrender.com/health https://whoisbase.onrender.com/health https://swiftread.onrender.com/health https://driftcheck.onrender.com/health"

if [ "${1:-}" != "--force" ]; then
  HOUR=$(TZ=America/New_York date +%H)
  MIN=$(TZ=America/New_York date +%M)
  MINS=$((10#$HOUR * 60 + 10#$MIN))
  if [ "$MINS" -lt 540 ] || [ "$MINS" -ge 650 ]; then
    exit 0
  fi
fi

LINE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for u in $URLS; do
  CODE=$(curl -s -o /dev/null -w '%{http_code}:%{time_total}' -m 90 "$u" || echo "ERR:0")
  LINE="$LINE $u=$CODE"
done
echo "$LINE" >> "$LOG"
# keep the log bounded
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
