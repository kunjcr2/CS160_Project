# Project Description Document

**Working product name:** *(pick one — e.g. "Vera", "Mila", "Companion")*

**Course:** CS 160 Software Engineering, Section 05 · Fall 2026
**Instructor:** Dominic Abucejo
**Institution:** San José State University, Department of Computer Science
**Team:** _____ · **Members:** _____
**Sprint:** N-2 / N-1 (Week 3) — Prototype Planning & Survey
**Document version:** 0.1 — draft for survey input

---

## 1. Problem Statement

The last three years of AI product design have overwhelmingly targeted people who are already comfortable with software. ChatGPT and Claude present a blank text box, small type, dense settings menus, and an interaction model that assumes you know what to type and can type it quickly. For an 80-year-old with arthritis, cataracts, and no mental model of a "chat interface," that door is closed.

The consequence is not just missing out on a chatbot. It is compounding exclusion. Health systems keep moving intake, scheduling, and messaging into patient portals. Transportation moved into apps. Travel booking moved into apps. Each migration removes a phone number that used to work and replaces it with an interface that assumes fluency the user doesn't have. The user's options narrow to (a) call and wait on hold, (b) ask a family member, or (c) give up.

Option (c) is common, and it is expensive. Missed and unbooked follow-up appointments delay treatment. Skipped physical therapy sessions extend recovery. Abandoned medication regimens land people back in the hospital. And every time an older adult has to ask an adult child to make an appointment for them, it reinforces a sense of diminished capability — which the loneliness literature consistently links to worse health outcomes independent of the underlying illness.

> **Note for the team:** the claim "elderly die not because of illness but because of loneliness" is too strong to write in a graded report. The defensible version is that social isolation is associated with substantially elevated all-cause mortality risk — comparable in effect size to well-known risk factors like smoking — per Holt-Lunstad et al.'s meta-analyses. Cite something real here. Sommerville is fine with a product vision built on an assumption, but a report that overstates a health statistic will get marked down.

**The friction we are actually attacking:**

| Friction | What it looks like today |
|---|---|
| Scheduling | Portal login → password reset → find department → parse a calendar grid |
| Appointment recall | A paper card that gets lost; a portal notification that is never seen |
| Reaching the doctor | Secure-message inbox buried three taps deep in an app |
| Getting there | Rideshare app requires account, payment setup, live map reading |
| Medication | Pill organizer + memory; no confirmation anyone else can see |
| Everything else | Increasingly app-only, increasingly closed |

---

## 2. Product Vision

**FOR** older adults who live independently but find current apps and patient portals unusable,
**WHO** need to manage healthcare and daily logistics without depending on a family member for every task,
**OUR PRODUCT** is a proactive voice assistant
**THAT** handles appointments, medications, messages to care providers, transportation, and everyday errands entirely through conversation, and checks in on its own rather than waiting to be summoned,
**UNLIKE** general-purpose assistants that are reactive, text-first, and unconnected to the user's actual care providers,
**OUR PRODUCT** is built around a single conversation the user never has to navigate, with a family-facing companion view for the person who would otherwise be making these calls.

*(This is Sommerville's vision template from Ch. 3 — worth using verbatim in the report since it's the format the professor is teaching.)*

---

## 3. Personas

Sommerville, Ch. 3: personas should read as short character sketches, not requirement lists. Three here — the primary user, a secondary user with different needs, and the caregiver who is usually the one who buys and installs the thing.

### Persona 1 — Margaret, 78 (primary user)

Margaret taught fourth grade for thirty-one years and has lived in the same Rohnert Park house since 1987. Her husband died four years ago. She has moderate arthritis in both hands, wears reading glasses, and describes her hearing as "fine, if people don't mumble." She takes four medications, two of them twice daily, and sees a cardiologist quarterly and a physical therapist for a knee.

Her son set up an iPhone for her. She uses it for phone calls, and for photos of her grandchildren, and for nothing else. She has a patient portal account; she has never successfully logged into it twice in a row, because the password resets and the reset email goes to an address her son created. When she needs to change an appointment she calls the office and waits, usually eleven or twelve minutes, and she has started deciding some appointments aren't worth the eleven minutes.

She is not afraid of technology. She is tired of being made to feel stupid by it. She talks to her television remote already, without much success, and would talk to a device that talked back if it didn't require her to learn a vocabulary first.

### Persona 2 — David, 71 (secondary user)

David retired from a county planning department where he used email daily for twenty years, so he is more comfortable with software than Margaret — he can navigate a website if the buttons are big enough. His wife died last spring. He has early-stage hearing loss in his right ear and has started avoiding phone calls because he mishears things and finds it humiliating to ask people to repeat themselves.

What he wants most is to visit his grandchildren in Austin twice a year. He has tried to book the flights himself three times and abandoned it each time at the seat-selection screen. He also drinks more than he did a year ago and has started letting whole days pass without speaking to another person, which he has not mentioned to his daughter.

David is the argument for the companion and check-in features. He does not need help with appointments. He needs a reason to talk before noon.

### Persona 3 — Priya, 44 (caregiver / buyer)

Priya is David's daughter. She lives in Seattle, works full time, and is the family's designated technology person, which means she is the one who fields the call when the portal locks him out. She has set up and abandoned two other "senior tech" products because they required her father to learn something, and he didn't.

She wants to know that his medications were taken and that he made it to his cardiology follow-up. She does *not* want a surveillance dashboard, and she would be uncomfortable reading transcripts of his conversations. The line she cares about is between *knowing he's okay* and *monitoring him.*

Priya matters because she is almost certainly the person who buys, installs, and configures this. If the setup requires her father's participation, it never happens.

---

## 4. Feature List

Fifteen candidate features. The assignment expects us to over-generate and then cut based on survey data, so several of these are deliberately speculative — the survey exists to kill some of them.

Effort ratings are relative to a one-semester course project with the integrations mocked (see §7).

### Group A — Core interaction

| ID | Feature | What it does | Effort | Status |
|---|---|---|---|---|
| **F1** | Voice conversation engine | Wake word plus always-available speech in/speech out. Tolerates slow speech, pauses, self-correction, and regional accents. No command syntax to memorize. | High | **Must have** |
| **F2** | Confirm-and-undo | Before anything irreversible (booking, canceling, sending), the assistant repeats it back in plain language and waits for a yes. Every completed action is undoable by saying "undo that." | Medium | **Must have** |
| **F3** | Large-print companion screen | An optional tablet/TV view showing the current conversation and today's schedule in very large type. Read-only — never required to complete a task. | Medium | Survey |

### Group B — Healthcare

| ID | Feature | What it does | Effort | Status |
|---|---|---|---|---|
| **F4** | Appointment booking | "I need to see Dr. Chen sometime next week." Assistant finds openings, proposes two or three in natural language, books the chosen one. | High | Survey |
| **F5** | Appointment lookup & reminders | "What do I have this week?" Plus proactive reminders at configurable intervals (day before, morning of, one hour before). | Low | Survey |
| **F6** | Message the care team | Dictate a non-urgent question to a doctor or nurse; assistant transcribes, reads it back, sends it, and reads the reply aloud when it arrives. | Medium | Survey |
| **F7** | Prescription refill | "I'm almost out of my blood pressure pill." Assistant identifies the prescription and submits the refill request to the pharmacy on file. | Medium | Survey |
| **F8** | Medication reminders & adherence | Scheduled spoken reminders; user confirms verbally; a simple taken/missed record. Optional escalation to caregiver after N consecutive misses. | Low | Survey |

### Group C — Daily logistics

| ID | Feature | What it does | Effort | Status |
|---|---|---|---|---|
| **F9** | Ride booking | "I need a ride to my appointment Thursday." Assistant books a rideshare timed to the appointment, tells the user when the car is arriving, and describes the vehicle. | Medium | Survey |
| **F10** | Travel booking | Flights and hotels by conversation — David's Austin trip without the seat-selection screen. | High | Survey |
| **F11** | Daily briefing | A short spoken morning summary: weather, today's schedule, medication times, two or three news items, calibrated to be informative rather than alarming. | Low | Survey |

### Group D — Companionship

| ID | Feature | What it does | Effort | Status |
|---|---|---|---|---|
| **F12** | Proactive check-ins | The assistant initiates conversation on a schedule and adapts to patterns — notices the user hasn't spoken today and opens a conversation rather than waiting. | Medium | Survey |
| **F13** | Open conversation & games | Unstructured talk, trivia, word games, reminiscence prompts, help looking things up. The "keep up with the world" function. | Medium | Survey |

### Group E — Safety & family

| ID | Feature | What it does | Effort | Status |
|---|---|---|---|---|
| **F14** | Caregiver companion view | A separate app for a designated family member: upcoming appointments, medication adherence summary, alerts. Explicitly excludes conversation transcripts. | Medium | Survey |
| **F15** | Emergency escalation | "Call my daughter." Also detects sustained non-response and escalates through a contact chain. Deliberately *not* fall detection — that needs hardware and clinical validation we don't have. | High | Survey |

**Target after survey:** cut to 6–8 features. F1 and F2 are not up for cutting — F1 is the product and F2 is the thing that makes a voice interface trustworthy enough to hand a real appointment to.

---

## 5. Functional Requirements

Written to be testable. Numbered by feature group for traceability back to §4.

### Core interaction (F1–F3)

| ID | Requirement |
|---|---|
| FR-1.1 | The system shall activate on a configurable wake word without requiring a button press. |
| FR-1.2 | The system shall accept a spoken request and respond audibly within 3 seconds under normal network conditions. |
| FR-1.3 | The system shall permit pauses of up to 5 seconds mid-utterance without treating the turn as complete. |
| FR-1.4 | The system shall allow the user to interrupt and correct itself mid-request ("no, wait, I meant Tuesday") and apply the correction to the pending request. |
| FR-1.5 | The system shall ask a clarifying question rather than guess when the confidence of an interpretation falls below a configured threshold. |
| FR-1.6 | The system shall support adjustable speech rate and volume by voice command ("speak slower"). |
| FR-2.1 | The system shall read back the full details of any booking, cancellation, message, or purchase and require explicit spoken confirmation before executing it. |
| FR-2.2 | The system shall support an "undo" command that reverses the most recent completed action where the external service permits reversal. |
| FR-2.3 | The system shall report failure in plain language and offer an alternative path (including a phone number to call) when an action cannot be completed. |
| FR-3.1 | The system shall optionally render the active conversation and today's schedule on a paired display at a minimum 24pt equivalent type size. |
| FR-3.2 | The system shall remain fully functional with the display disabled or absent. |

### Healthcare (F4–F8)

| ID | Requirement |
|---|---|
| FR-4.1 | The system shall retrieve available appointment slots for a named provider or specialty within a user-specified date range. |
| FR-4.2 | The system shall present no more than three appointment options per turn, spoken in natural language rather than read as a list of timestamps. |
| FR-4.3 | The system shall book a selected appointment and confirm the booking aloud with date, time, provider, and location. |
| FR-4.4 | The system shall cancel or reschedule an existing appointment on request, subject to FR-2.1. |
| FR-5.1 | The system shall list the user's upcoming appointments on request. |
| FR-5.2 | The system shall issue proactive spoken reminders at user-configurable intervals before each appointment. |
| FR-5.3 | The system shall include transportation status in an appointment reminder when a ride has been booked for it (see FR-9.2). |
| FR-6.1 | The system shall record a dictated message, read the transcription back for confirmation, and transmit it to the specified provider. |
| FR-6.2 | The system shall notify the user when a provider reply is received and read it aloud on request. |
| FR-6.3 | The system shall detect language indicating a medical emergency and instruct the user to call 911 instead of sending a message. |
| FR-7.1 | The system shall list the user's active prescriptions on request. |
| FR-7.2 | The system shall submit a refill request to the pharmacy of record and confirm submission aloud. |
| FR-8.1 | The system shall issue a spoken medication reminder at each scheduled dose time. |
| FR-8.2 | The system shall record a verbal confirmation of a dose as taken. |
| FR-8.3 | The system shall re-prompt once after a configurable interval if no confirmation is received, and record the dose as missed thereafter. |
| FR-8.4 | The system shall notify the designated caregiver after a configurable number of consecutive missed doses, if that notification is enabled. |

### Daily logistics (F9–F11)

| ID | Requirement |
|---|---|
| FR-9.1 | The system shall request a rideshare to a spoken destination and confirm pickup time, cost estimate, and destination before booking. |
| FR-9.2 | The system shall schedule a ride to arrive at a configurable buffer before an appointment when the user requests transportation for that appointment. |
| FR-9.3 | The system shall announce driver arrival with vehicle make, color, and license plate. |
| FR-10.1 | The system shall search flights by spoken origin, destination, and approximate date, and present no more than three options per turn. |
| FR-10.2 | The system shall complete a flight or hotel booking using a stored payment method, subject to FR-2.1. |
| FR-11.1 | The system shall deliver a spoken daily briefing at a user-configured time containing weather, schedule, medication times, and a configurable number of news items. |
| FR-11.2 | The system shall allow the user to skip or extend any section of the briefing by voice. |

### Companionship (F12–F13)

| ID | Requirement |
|---|---|
| FR-12.1 | The system shall initiate conversation at user-configured times. |
| FR-12.2 | The system shall initiate a check-in when no interaction has occurred for a configurable period. |
| FR-12.3 | The system shall allow the user to suppress check-ins for a stated duration ("leave me alone until tomorrow"). |
| FR-13.1 | The system shall support open-ended conversation on general topics. |
| FR-13.2 | The system shall offer at least three conversational games or activities on request. |
| FR-13.3 | The system shall decline to give medical, legal, or financial advice and redirect to the appropriate human professional. |

### Safety & family (F14–F15)

| ID | Requirement |
|---|---|
| FR-14.1 | The system shall provide a caregiver view listing upcoming appointments, medication adherence over a configurable window, and active alerts. |
| FR-14.2 | The system shall **not** expose conversation content or transcripts in the caregiver view. |
| FR-14.3 | The system shall require the primary user's consent before granting a caregiver access, and allow the primary user to revoke that access by voice. |
| FR-14.4 | The system shall inform the primary user, in speech, each time a caregiver notification is sent. |
| FR-15.1 | The system shall place a call to a named emergency contact on spoken request. |
| FR-15.2 | The system shall escalate through an ordered contact list when the user does not respond to a configurable number of consecutive check-ins. |

### Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Speech recognition shall achieve ≥90% word accuracy on speech from users aged 70+, including slowed speech and mild dysarthria. |
| NFR-2 | Spoken response latency shall not exceed 3 seconds at the 95th percentile. |
| NFR-3 | All health data at rest and in transit shall be encrypted; the system shall be designed to a HIPAA-aligned handling standard. |
| NFR-4 | The paired display shall meet WCAG 2.2 AA, with a documented exception path where AA conflicts with the large-type requirement. |
| NFR-5 | The system shall be available 99.5% of the time, measured monthly. |
| NFR-6 | Audio recordings shall be retained no longer than needed to complete the request, with retention period disclosed to the user in speech at setup. |
| NFR-7 | The system shall contain no dark patterns: no upsell during a health interaction, no artificial urgency, no engagement-maximizing behavior in check-ins. |
| NFR-8 | Setup shall be completable by a remote caregiver without the primary user's participation. |

---

## 6. Assumptions

1. The user has reliable home Wi-Fi and a power outlet in the room where the device lives.
2. The user's providers are on a portal system with an accessible API (see §7 — this is our biggest assumption and it is doing a lot of work).
3. A family member or caregiver is available for initial setup.
4. The user can hear and speak well enough for voice interaction, possibly with a hearing aid. Users who cannot are out of scope for v1 and this should be stated explicitly rather than glossed.
5. We can recruit 15–25 real respondents in one week — adults 60+ and family caregivers — primarily through team members' own networks and local senior centers. This is the assumption most likely to break, and it breaks on schedule rather than on design. Start recruiting the day the survey is drafted, not the day it's finished.

---

## 7. Scope Reality Check

Worth putting a version of this in the report, because the professor will ask and it's better to have named the constraint ourselves.

Real integrations behind F4–F7 mean Epic/Cerner FHIR APIs, which require a health-system partnership, a security review, and a BAA. That is not a semester. Same story for Uber's API (partner approval) and airline GDS access (contracts).

So the buildable version is:

- A **mock provider service** implementing the FHIR resources we need (`Appointment`, `Slot`, `Practitioner`, `MedicationRequest`, `Communication`) with realistic latency and failure modes. Building against the real FHIR resource shapes is the part that makes it credible engineering rather than a puppet show.
- **Sandbox APIs** where they exist. Uber and several travel APIs have sandboxes; use them and say so.
- A **seeded demo dataset** — Margaret's four medications, her cardiologist, her PT — so the demo has a real story running through it.

Framed as microservices (Ch. 6, Week 7–8) this maps cleanly: appointment service, medication service, messaging service, transport service, conversation orchestrator. That alignment with the course sequence is worth making explicit in the architecture document in Sprint N-1.

---

## 8. Open Questions for the Survey

The survey in the companion document goes to two groups — adults 60+ and the family members who support them — and is built to answer these:

1. Is the friction real and measurable? Do older adults report actually delaying or skipping care because scheduling it was too much trouble?
2. Which of F4–F15 would they use, in their own words, and which three matter most?
3. Where is the trust ceiling? Will they let a voice assistant book a real appointment? Spend money?
4. Is the companionship half (F12, F13) welcome, or does an unprompted conversation read as intrusive?
5. Does the caregiver view (F14) read as reassurance or as surveillance — and do the two groups answer that differently?
6. If we can only ship six or seven features, which ones?

**Question 5 is the one to watch.** The person being supported and the person doing the supporting have genuinely different interests here, and if the survey surfaces that disagreement we should report it as a finding rather than average it away. A product that resolves it explicitly — granular consent, transcript exclusion, notification transparency — is a better product and a better report.