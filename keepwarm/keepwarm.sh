#!/usr/bin/env bash
# Keep-warm pinger for the eighteen RapidAPI competitor services on Render free tier.
# Render grants 750 free instance hours per WORKSPACE per month (shared).
# Eighteen always-on services would burn ~13,392h and get ALL services suspended,
# so pings run only inside a daily window: 09:00-10:10 America/New_York.
# Window math: 70min x 18 services x 31 days = 651h worst month, ~99h headroom
# for organic traffic. A spun-down service consumes no hours.
# (Window history: 09:00-16:00 for three services, 09:00-14:00 for four,
# 09:00-13:00 for five, 09:00-12:00 for six (all 2026-10-28),
# 09:00-11:30 for seven, 09:00-11:00 for nine, 09:00-11:00 held for ten
# and eleven (2026-10-29/30), 09:00-10:50 for twelve (2026-10-31,
# DriftCheck added), 09:00-10:40 for thirteen (2026-10-31, XBase added),
# 09:00-10:30 for fourteen (2026-10-31, FactBase added), 09:00-10:25 for
# fifteen (2026-10-31, DesignBase added), 09:00-10:20 for sixteen
# (2026-10-31, ActorBase added), 09:00-10:15 for seventeen
# (2026-10-31, SwiftRender added), 09:00-10:10 for eighteen
# (2026-11-01, SwiftHumanize added; the window narrows so the worst
# month stays under the cap).)
# NOTE: the URL list below carries all eighteen services.
# Usage: keepwarm.sh [--force]   (--force ignores the window, for manual tests)
set -u
LOG="$(dirname "$0")/keepwarm.log"
URLS="https://stablefx-currency-rates.onrender.com/health https://cleanlist-email-verifier.onrender.com/health https://edgar-fundamentals.onrender.com/health https://geobase-cities.onrender.com/health https://cleanextract-articles.onrender.com/health https://swiftrewrite.onrender.com/health https://wordbase-dictionary.onrender.com/health https://newsbase-headlines.onrender.com/health https://swifttranslate-72rx.onrender.com/health https://whoisbase.onrender.com/health https://swiftread.onrender.com/health https://driftcheck.onrender.com/health https://xbase.onrender.com/health https://factbase.onrender.com/health https://designbase.onrender.com/health https://actorbase.onrender.com/health https://swiftrender-yqqd.onrender.com/health https://swifthumanize.onrender.com/health"

if [ "${1:-}" != "--force" ]; then
  HOUR=$(TZ=America/New_York date +%H)
  MIN=$(TZ=America/New_York date +%M)
  MINS=$((10#$HOUR * 60 + 10#$MIN))
  if [ "$MINS" -lt 540 ] || [ "$MINS" -ge 610 ]; then
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
