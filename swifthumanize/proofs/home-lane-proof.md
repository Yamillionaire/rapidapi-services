# SwiftHumanize home lane proof (2026-11-01)

The same service running on this machine, in the pattern of the
LeadBase and WordBase home instances.

- Units: swifthumanize-home.service (the API) and
  swifthumanize-bridge.service (the engine bridge), both installed
  under the user systemd manager, both enabled and active.
- Address: 127.0.0.1:8115 only. No public door, the standing home
  limit: a public address waits on the user's own named Cloudflare
  tunnel step.
- Gate: every route except /health requires the
  X-SwiftHumanize-Secret header. Verified: POST /score without the
  header returned 401; with it, requests answer normally. The secret
  lives only in swifthumanize-home.env (mode 600, never committed).
- Engine: the real Gemini engine, reached through the local connector
  bridge (home_bridge.py on 127.0.0.1:8903) using the fleet's
  connector credential flow. No key value is stored on this machine.
  Verified end to end through the supervised unit: a stiff test
  sentence scored 60 before and 100 after, engine labeled "gemini",
  output: "We will use everything we have to get this done right.
  You will get the results on time."
- Kill and recover: SIGKILL to the app unit's MainPID; /health
  answered 200 again in 4.24 seconds (RestartSec 3 plus startup).
  Both units active after the check.
- Full proof battery (three samples plus the style_sample case) was
  run against this same code on port 8115 before the units were
  installed; see proof-results.md in this folder.
