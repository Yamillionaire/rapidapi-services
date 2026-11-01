# SwiftHumanize proof results

Run against http://127.0.0.1:8115. Engine results, preservation checks,
and heuristic scores recorded exactly as returned.

## Operator honest read (2026-11-01)

- Sample 1 (generic AI paragraph): reads like a person wrote it. Plain
  openers, uneven sentence lengths, zero stock phrases. It keeps one
  content triplet (workflows, productivity, performance) because those
  are the paragraph's actual claims, not padding.
- Sample 2 (business email): the strongest result. It reads like a
  real manager's email: short, direct, every date, time, room, name,
  and project preserved exactly.
- Sample 3 (assistant style): natural summary voice; the edit lands a
  short sentence ("Results are positive across the board.") in a run
  of even statements, which is what the rhythm rule is for. The opener
  "Here is a summary of the key points." survives; people write that
  too, so it stays.
- Style sample: the blunt sample voice carries over (short declaratives,
  active voice, "We will let the client know today." for "notified
  through the appropriate channels in a timely manner"). Note the
  heuristic quirk: matching a short-sentence voice lowers the
  uniformity subscore even though the result sounds more human. The
  score is a pattern reading, not a verdict, and this case shows why.
- Run-to-run variance: sample 1 scored 96 and 85 on two runs of the
  same input (temperature-based engine). Both outputs read human; the
  number moves more than the quality does.
- Proof iteration caught two real defects before this final run:
  thinking tokens silently truncated every long output mid-sentence
  (fixed with thinkingBudget 0, a larger output budget, and a
  MAX_TOKENS retry), and the preservation checker caught the truncated
  numbers before any human read them.

## sample-1-generic-ai-paragraph

Kind: generic AI-sounding paragraph (composed for this test). Tone: keep. Strength: standard. Engine: gemini.

Original:

In today's fast-paced world, effective communication plays a crucial role in achieving success. Moreover, it is important to note that successful teams leverage a comprehensive range of tools, strategies, and techniques to foster collaboration. Furthermore, by utilizing cutting-edge technology, organizations can streamline their workflows, enhance their productivity, and elevate their overall performance. This seamless integration serves as a testament to the transformative power of innovation in the modern workplace.

Score before: 37 (strong AI patterns); tell phrases 17; em-dashes 0; sentence CV 0.146.

Humanized:

Effective communication drives success. Successful teams use a full range of tools and strategies to collaborate, while new technology helps organizations streamline workflows, boost productivity, and improve performance. This kind of smooth integration shows how innovation can transform the workplace.

Score after: 85 (reads human); tell phrases 1; em-dashes 0; sentence CV 0.616.

Checks: {"no_em_dash_in_output": true, "score_improved": true, "names_preserved": true, "numbers_preserved": true, "quotes_preserved": true}

## sample-2-business-email

Kind: short business email in stiff AI style. Tone: professional. Strength: standard. Engine: gemini.

Original:

Dear Team, I hope this email finds you well. I am writing to inform you that our quarterly meeting has been rescheduled to March 14 at 2:30 PM in Conference Room B. Additionally, please be advised that the deadline for the Harrison project report has been extended to March 21. It is important to note that attendance is mandatory, and all team members are required to review the attached documents, complete the assigned tasks, and prepare their updates prior to the meeting. Thank you for your continued dedication and commitment to excellence. Best regards, Dana Whitfield

Score before: 88 (reads human); tell phrases 2; em-dashes 0; sentence CV 0.594.

Humanized:

Dear Team, 

Our quarterly meeting is moving to March 14 at 2:30 PM in Conference Room B. We also pushed the Harrison project report deadline to March 21. 

Attendance is mandatory. Please review the attached documents, complete your assigned tasks, and prepare your updates before we meet. 

Thanks for your hard work.

Best,
Dana Whitfield

Score after: 100 (reads human); tell phrases 0; em-dashes 0; sentence CV 0.651.

Checks: {"no_em_dash_in_output": true, "score_improved": true, "names_preserved": true, "numbers_preserved": true, "quotes_preserved": true}

## sample-3-assistant-style

Kind: paragraph in typical assistant style. Tone: keep. Strength: standard. Engine: gemini.

Original:

Here is a summary of the key points. The report covers three main areas: revenue growth, customer retention, and operational efficiency. Revenue grew by 12 percent in the fourth quarter, which is a strong result. Customer retention improved as well, rising to 94 percent. Operational efficiency also improved, with processing time reduced by 8 minutes per order. Overall, the results are positive across all three areas, and the outlook for the next quarter remains strong. Let me know if you would like me to expand on any of these points.

Score before: 80 (mostly human, some AI patterns); tell phrases 0; em-dashes 0; sentence CV 0.247.

Humanized:

Here is a summary of the key points. The report covers revenue growth, customer retention, and operational efficiency. Fourth-quarter revenue grew by 12 percent. Customer retention also improved, rising to 94 percent, while operational efficiency gains cut order processing time by 8 minutes. Results are positive across the board. The outlook for next quarter remains strong, so let me know if you would like me to expand on any of these points.

Score after: 100 (reads human); tell phrases 0; em-dashes 0; sentence CV 0.531.

Checks: {"no_em_dash_in_output": true, "score_improved": true, "names_preserved": true, "numbers_preserved": true, "quotes_preserved": true}

## style-sample-voice-match

Kind: style_sample path: plain company note rewritten toward a blunt, short-sentence voice. Tone: keep. Strength: standard. Engine: gemini.

Style sample:

Look, the numbers do not lie. We shipped late. Twice. Nobody is happy about it, least of all me. So we fix the schedule, we tell the client the truth, and we do not let it happen a third time. Simple as that.

Original:

It is important to note that the delivery timeline for the Patterson order has been adjusted. Moreover, the revised schedule indicates that the shipment will arrive on November 9 rather than November 4, and the client will be notified of this change through the appropriate channels in a timely manner.

Score before: 76 (mostly human, some AI patterns); tell phrases 2; em-dashes 0; sentence CV 0.36.

Humanized:

We pushed back the delivery date for the Patterson order. The shipment arrives November 9 instead of November 4. We will let the client know today.

Score after: 80 (mostly human, some AI patterns); tell phrases 0; em-dashes 0; sentence CV 0.144.

Checks: {"no_em_dash_in_output": true, "score_improved": true, "names_preserved": true, "numbers_preserved": true, "quotes_preserved": true}
