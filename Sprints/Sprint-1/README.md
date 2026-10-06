# CS160_Project — Sprint 1 Documentation

> **End-of-sprint draft:** The completed work, task hours, and finish dates below are provisional and should be confirmed by each team member before submission.

**Course:** CS 160 Software Engineering, Section 05  
**Institution:** San José State University, Department of Computer Science  
**Instructor:** Dominic Abucejo  
**Team:** Team 4  
**Project name:** CS160_Project  
**Sprint:** Sprint 1  
**Sprint dates:** September 21–October 4, 2026  
**Status:** End-of-sprint review — planning and specification completed; implementation carries into Sprint 2

## Table of Contents

1. [Team and GitHub Profiles](#1-team-and-github-profiles)
2. [Survey Report](#2-survey-report)
3. [Sprint 1 Scope and Goals](#3-sprint-1-scope-and-goals)
4. [Architectural Block and Component Diagrams](#4-architectural-block-and-component-diagrams)
5. [Sequence Diagrams](#5-sequence-diagrams)
6. [Class Diagram](#6-class-diagram)
7. [Git Source Code](#7-git-source-code)
8. [Backlog and Sprint Log](#8-backlog-and-sprint-log)
9. [Sprint Summary](#9-sprint-summary)
10. [Plans for Sprint 2](#10-plans-for-sprint-2)
11. [Open Decisions](#11-open-decisions)

## 1. Team and GitHub Profiles

Assignments are provisional until confirmed by the whole team.

| Team member | GitHub username | Draft responsibility |
| --- | --- | --- |
| Moebius Yang | [momoyang0828](https://github.com/momoyang0828) | Frontend |
| Zohreh Ashtarilarki | [ZohrehAshtarilarki](https://github.com/ZohrehAshtarilarki) | Backend |
| Amarjargal Ayurzana | [Akiko0210](https://github.com/Akiko0210) | Backend |
| Kunj Shah | [kunjcr2](https://github.com/kunjcr2) | AI and voice exploration |

## 2. Survey Report

The completed survey analysis is included in the [Sprint 1 activities report](report/Team%20Project%20Sprint%20%231%20Activities.pdf). The survey indicates that appointment booking, appointment reminders, medication reminders, multilingual interaction, and explicit confirmation are the strongest product needs.

The survey sample contains 13 caregiver/supporter responses and no direct older-adult responses. All product decisions based on it remain hypotheses until validated with the intended users.

## 3. Sprint 1 Scope and Goals

Sprint 1 is a planning and specification sprint. The goal is to finalize the product direction, document the system design, organize the shared repository, and prepare the team to begin implementation.

### Sprint 1 deliverables

1. Finalize the seven core features using the survey results.
2. Define the project scope and supporting system requirements.
3. Complete the architectural block, component, sequence, and class diagrams.
4. Select React, Python with FastAPI, PostgreSQL, OpenAI Whisper for speech-to-text, OpenAI TTS for speech output, and the OpenAI API for AI features.
5. Create the product backlog, Sprint 1 backlog, task assignments, and sprint log.
6. Organize the shared GitHub repository and Sprint 1 documentation.
7. Record the sprint outcome and prepare the Sprint 2 implementation plan.

### Explicitly outside Sprint 1

- Production healthcare, FHIR, rideshare, payment, pharmacy, or calendar integrations
- Medical advice or emergency detection
- A production-ready voice pipeline
- Full multilingual support
- Caregiver monitoring features
- Deployment, HIPAA certification, or clinical validation

## 4. Architectural Block and Component Diagrams

The selected stack uses React, Python with FastAPI, PostgreSQL, OpenAI Whisper for speech-to-text, OpenAI TTS for speech output, and the OpenAI API for AI features. External healthcare services are represented by mock adapters during early development.

The high-level architectural block diagram and component diagram are included in the [Sprint 1 activities report](report/Team%20Project%20Sprint%20%231%20Activities.pdf).

## 5. Sequence Diagrams

The sequence diagrams in the [Sprint 1 activities report](report/Team%20Project%20Sprint%20%231%20Activities.pdf) cover:

- Appointment request and explicit confirmation
- Failed AI/voice understanding and fallback
- Appointment reminder delivery

Only the appointment-request sequence is proposed for implementation during Sprint 1. The other sequences establish interfaces for later work.

## 6. Class Diagram

The class diagram is included in the [Sprint 1 activities report](report/Team%20Project%20Sprint%20%231%20Activities.pdf). It is a design aid and does not imply that all displayed classes will be implemented during Sprint 1.

## 7. Git Source Code

- Repository: [kunjcr2/CS160_Project](https://github.com/kunjcr2/CS160_Project)
- Main branch: [main](https://github.com/kunjcr2/CS160_Project/tree/main)
- Development folders: `Dev/Frontend` and `Dev/Backend`

The team should use feature branches and pull requests once implementation begins. Branch names can follow `frontend/<task>`, `backend/<task>`, `ai/<task>`, or `docs/<task>`.

## 8. Backlog and Sprint Log

All tracking is kept in the team's shared Google Sheet, **Team 4 Backlogs**:

- [Team 4 Backlogs spreadsheet](https://docs.google.com/spreadsheets/d/1PyE_Iw9B7tvLMdN2w4PInKtuA1yfTM7f881EL9eztDg/edit)

Sprint 1 uses these tabs:

| Tab | What it contains |
| --- | --- |
| [Product Backlog](https://docs.google.com/spreadsheets/d/1PyE_Iw9B7tvLMdN2w4PInKtuA1yfTM7f881EL9eztDg/edit?gid=0#gid=0) | The full list of features and supporting work, with priority, estimate points, target sprint, and status. This is a living list that is updated every sprint. |
| [Sprint 1 Backlog](https://docs.google.com/spreadsheets/d/1PyE_Iw9B7tvLMdN2w4PInKtuA1yfTM7f881EL9eztDg/edit?gid=616597569#gid=616597569) | Each Sprint 1 task with its assignee, estimated and actual hours, date assigned, target date, date finished, status, and acceptance evidence. |
| [Sprint 1 Log](https://docs.google.com/spreadsheets/d/1PyE_Iw9B7tvLMdN2w4PInKtuA1yfTM7f881EL9eztDg/edit?gid=427637020#gid=427637020) | A day-by-day record of the work performed, hours, status, blockers or decisions, and evidence. |

Each sprint gets its own backlog and log tab, as the course requires.

## 9. Sprint Summary

Sprint 1 completed the planning and specification work needed to begin development. The team reviewed 13 caregiver/supporter survey responses, selected seven core product features, defined the initial scope, completed the architecture and design diagrams, created the product and sprint backlogs, assigned work across the four team members, selected the initial technology stack, and organized the shared GitHub repository.

Application implementation was not completed during Sprint 1 and will carry into Sprint 2. The React frontend, FastAPI backend, PostgreSQL schema, mocked appointment workflow, automated tests, and voice pipeline still need to be built. The survey also did not include direct responses from older adults, so the feature decisions remain hypotheses that should be validated with intended users.

What went well was the use of survey evidence to narrow the product scope and the creation of a shared architecture before implementation. The main blockers were limited time, missing direct older-adult feedback, and the need to finalize the technology stack. In Sprint 2, the team should record work in the sprint log as it happens, use feature branches and pull requests, and focus on one small end-to-end appointment flow before expanding to other features.

Sprint 1 effort, task assignments, finish dates, status, and blockers are maintained in the shared Google Sheet. Each member must confirm their information there before submission. Relevant repository history is available through the [project commits](https://github.com/kunjcr2/CS160_Project/commits/main/).

## 10. Plans for Sprint 2

The provisional Sprint 2 goal is to turn the mocked appointment flow into a stable vertical slice and begin reminders. Proposed work:

1. Create the React conversation interface and connect it to the Python/FastAPI API.
2. Create the PostgreSQL schema and persist users, appointments, and confirmations.
3. Implement appointment lookup, proposal, confirmation, and cancellation against a mock provider service.
4. Add appointment reminders with configurable timing.
5. Add automated tests for confirmation and error paths.
6. Prototype voice input with OpenAI Whisper and speech output with OpenAI TTS.
7. Conduct usability feedback with at least one intended user if possible.

This plan should be revised using Sprint 1 results and the team's actual capacity.

## 11. Open Decisions

- PostgreSQL driver, ORM, and migration tool
- OpenAI model choices and request limits for the first vertical slice
- Authentication approach
- Frontend component and styling approach
- Hosting/deployment platform
- Final actual hours, completion dates, and blockers after team review in the shared Google Sheet
