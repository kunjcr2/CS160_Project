# CS160_Project — Sprint 1 Documentation

> **Draft:** This document records the team's current direction during project setup. Architecture, scope, assignments, estimates, and technology choices are provisional and should be updated after the team agrees on them.

**Course:** CS 160 Software Engineering, Section 05  
**Institution:** San José State University, Department of Computer Science  
**Instructor:** Dominic Abucejo  
**Team:** Team 4  
**Project name:** CS160_Project  
**Sprint:** Sprint 1  
**Sprint dates:** September 21–October 4, 2026  
**Status:** In progress — setup and planning stage

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
| Moebius Yang | _TBD_ | Frontend |
| Zohreh Ashtarilarki | [ZohrehAshtarilarki](https://github.com/ZohrehAshtarilarki) | Backend |
| Amarjargal Ayurzana | [Akiko0210](https://github.com/Akiko0210) | Backend |
| Kunj Shah | [kunjcr2](https://github.com/kunjcr2) | AI and voice exploration |

## 2. Survey Report

The completed survey analysis is available in the [survey report](report/SURVEY_REPORT.md). The survey indicates that appointment booking, appointment reminders, medication reminders, multilingual interaction, and explicit confirmation are the strongest product needs.

The survey sample contains 13 caregiver/supporter responses and no direct older-adult responses. All product decisions based on it remain hypotheses until validated with the intended users.

## 3. Sprint 1 Scope and Goals

Sprint 1 is a foundation sprint. No implementation was complete when this draft was created, so the goal is to establish a small, testable vertical slice rather than attempt the full survey-driven product.

### Proposed Sprint 1 deliverables

1. Agree on the architecture, development workflow, and definition of done.
2. Create a React frontend shell with a basic conversation screen.
3. Create a Python backend shell with health and conversation endpoints.
4. Define an initial SQL schema for users, appointments, confirmations, and reminders.
5. Evaluate voice and AI options and record a team decision; keep typed interaction as the fallback.
6. Demonstrate a mocked appointment-request flow with explicit confirmation before booking.
7. Maintain the product backlog, Sprint 1 backlog, and sprint log.

### Explicitly outside Sprint 1

- Production healthcare, FHIR, rideshare, payment, pharmacy, or calendar integrations
- Medical advice or emergency detection
- A production-ready voice pipeline
- Full multilingual support
- Caregiver monitoring features
- Deployment, HIPAA certification, or clinical validation

## 4. Architectural Block and Component Diagrams

The draft architecture uses React, Python, and SQL. Voice/AI providers and the SQL database engine have not been selected. External healthcare services are represented by mock adapters for this sprint.

See the consolidated [system design](design/SYSTEM_DESIGN.md) for the high-level architectural block diagram, component diagram, technology decisions, and system boundaries.

## 5. Sequence Diagrams

See the consolidated [system design](design/SYSTEM_DESIGN.md#sequence-diagrams) for draft sequences covering:

- Appointment request and explicit confirmation
- Failed AI/voice understanding and fallback
- Appointment reminder delivery

Only the appointment-request sequence is proposed for implementation during Sprint 1. The other sequences establish interfaces for later work.

## 6. Class Diagram

See the consolidated [system design](design/SYSTEM_DESIGN.md#class-diagram) for the provisional domain model. It is a design aid and does not imply that all displayed classes will be implemented during Sprint 1.

## 7. Git Source Code

- Repository: [kunjcr2/CS160_Project](https://github.com/kunjcr2/CS160_Project)
- Main branch: [main](https://github.com/kunjcr2/CS160_Project/tree/main)
- Development folders: `Dev/Frontend` and `Dev/Backend`

The team should use feature branches and pull requests once implementation begins. Branch names can follow `frontend/<task>`, `backend/<task>`, `ai/<task>`, or `docs/<task>`.

## 8. Backlog and Sprint Log

Local draft files are included until the team creates the shared Google Sheets:

- [Product backlog](planning/PRODUCT_BACKLOG.csv)
- [Sprint 1 backlog](planning/SPRINT_BACKLOG.csv)
- [Sprint 1 log](planning/SPRINT_LOG.csv)

| Shared document | Link |
| --- | --- |
| Product backlog Google Sheet | _TBD_ |
| Sprint tracking Google Sheet | _TBD_ |

## 9. Sprint Summary

Sprint 1 is still in progress. At the time of this draft, the team had organized the repository and prepared the survey report, but application implementation had not started. The primary risk is beginning development before agreeing on the interface between the React frontend, Python backend, SQL data model, and future voice/AI layer.

The remainder of the sprint should prioritize a working repository structure and one mocked end-to-end appointment flow. A small integrated demonstration is more useful than several disconnected partial features.

This section must be updated at the end of Sprint 1 with completed work, incomplete work, actual hours, blockers, lessons learned, and links to relevant commits or pull requests.

## 10. Plans for Sprint 2

The provisional Sprint 2 goal is to turn the mocked appointment flow into a stable vertical slice and begin reminders. Proposed work:

1. Integrate the React conversation interface with the Python API.
2. Persist users, appointments, and confirmations in the selected SQL database.
3. Implement appointment lookup, proposal, confirmation, and cancellation against a mock provider service.
4. Add appointment reminders with configurable timing.
5. Add automated tests for confirmation and error paths.
6. Begin a voice-input/output prototype after the Sprint 1 technology decision.
7. Conduct usability feedback with at least one intended user if possible.

This plan should be revised using Sprint 1 results and the team's actual capacity.

## 11. Open Decisions

- Voice recognition and text-to-speech provider
- AI model/provider and whether it is needed in the first vertical slice
- Python web framework
- SQL database engine and data-access library
- Authentication approach
- Frontend component and styling approach
- Hosting/deployment platform
- Moebius Yang's GitHub username
- Final task ownership, estimates, and availability
- Google Sheet links
