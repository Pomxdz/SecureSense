# Behavioral analysis methodology

The observation unit is one recipient in one campaign, with event-time history and an explicit source. Repeated clicks and duplicate delivery events do not create additional failed people. A successful Email Sent event qualifies the observation for send-based denominators; it does not prove delivery, reading or intent. Simulation submissions use only fictional test information.

## Reproducible rule indicator

Campaign severity is 80 for test-form submission, 40 for a click without submission, 0 for reporting without interaction, and null when no assessable action exists. Submission implies interaction even if click telemetry is missing. Report timing produces separate protective/recovery journeys; it never discounts a preceding interaction.

Indicator = min(100, mean assessable severity + recurrence). Recurrence = 20 × max(0, interaction campaigns − 1) / successfully sent campaigns. Scores and components are rounded to one decimal place. Empty evidence is unassessed, never a safe label. These weights are documented learning task assumptions, not empirical compromise probabilities.

## Automatic model-generated AI indicator

New normalized evidence automatically queues an anonymized Gemini job. Inputs retain category, difficulty, journey, relative click/report timing, evidence coverage and the reproducible comparator. The model returns score, explanation and a suggested training category. Responses must contain a finite numeric 0–100 score, a bounded explanation and an allowed category. Invalid responses never become zero scores. The original observed campaign category determines required training; AI recommendations are advisory.

SQL records each distinct evidence fingerprint, selected model, creation/finish time, attempts, status and accepted output. Pending older snapshots are superseded; source history remains separate. The worker retries failures up to three times. Startup queues existing evidence when configuration changes. Current profiles hide scores tied to stale evidence. AI assessments are experimental and not calibrated probabilities; a temperature setting does not guarantee identical outputs.

Names, email, tracking IDs, submitted form values, IP and user agent are omitted from model inputs. The score can differ from the rules comparator because the model evaluates the structured history. Neither score is reduced merely because training was opened or passed.

## Context uncertainty and quality

Category, persuasion, objective, department and difficulty remain visible. Difficulty is a reviewed rubric label, not a score discount. Tags overlap; associations do not reveal employee motives. Optional reasons are explicitly self-reported. Suspected automation is withheld until review; user-agent patterns are incomplete heuristics.

Rates show numerator/denominator and descriptive Wilson intervals. Repeated participants are correlated, so intervals do not establish causality. Missing click/report times remain unknown. Coverage is limited below three assessable outcomes, moderate for three to five, and broader for six or more; coverage is evidence quantity, not statistical confidence.

## Learning and retests

Assignments are unique to recipient/campaign/category. Each category has an original lesson and five questions. The server grades a pass at four correct answers; attempts persist. A later failed review does not erase an earlier pass. Canceled assignments retain historical attempts but leave the active denominator.

The bridge uses an opaque expiring campaign ticket and tracking ID. It never grants a login or creates telemetry from a GET. After matching authentication, verified click or submission evidence opens the assigned lesson. Missing telemetry waits for ingestion; scanner-like evidence cannot bypass the check. Jigsaw practice is external and unverified.

Retests must occur after a pass and match source, category, difficulty and objective. The first comparable later campaign is the retest and the next is follow-up. Lower observed severity is an improvement observation, not proof that training caused it. No observed action remains uncertain. A passed learning task without a comparable retest appears as pending follow-up.

## GRC evidence

Internal requirements AW-01 through AW-04 link simulation, learning, effectiveness review and privacy/quality evidence to an owner and review date. They support an evidence discussion; no standard certification, full enterprise compliance or real-world effectiveness is inferred. CSV exports neutralize spreadsheet formula prefixes.
