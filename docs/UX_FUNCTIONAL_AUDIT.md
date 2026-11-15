# Clinic Dial UX and functional audit

Reviewed 15 November 2026. This is an audit of the current working tree, including the existing uncommitted implementation.

**Assessment: a functional prototype with a coherent visual foundation, but not ready for real clinic operations.** The basic owner CRM and manual booking path work with an in-memory API. Durable storage, reliable calendar behavior, and the visitor booking journey remain release blockers. Several capabilities marked “Working” in `STATUS.md` are partial implementations.

## Verification and limits

| Check | Result |
| --- | --- |
| Existing API `/healthz`, dashboard, visitor server | HTTP 200 |
| Existing API CORS for `http://127.0.0.1:3002` | Preflight accepted |
| Backend suite, excluding gated live speech test | **57 passed** |
| Dashboard TypeScript | **Passed** (`tsc --noEmit --incremental false`) |
| Production dashboard build | **Passed**, all 16 static pages generated; built in a temporary copy to preserve the running development server |
| Dashboard lint | **Failed:** `eslint: command not found`; the script exists but the dependency/configuration is missing |
| Desktop browser | Inspected all 12 workspace routes and the signed-out page at 1440px |
| Mobile browser | Inspected login, overview, services, and calendar at 375 × 812 |
| Manual booking | Created a synthetic appointment through the UI; a duplicate booking displayed “Overlapping appointment exists” |
| Visitor | Synthetic clinic loaded, session/WebSocket connected, typed turn returned a mock response |
| Database integration | Not verified against a live database. Importing the Postgres adapter failed before a connection could be attempted |
| Live integrations | No real Google authorization, Supabase signup/recovery email, Gnani/Evon call, or Lumen website form submission performed |

Authenticated browser checks used a synthetic Supabase-shaped session and a separate local API with isolated in-memory fixtures. They verify the real UI and backend application paths, **not live Supabase authentication or database persistence**. No real clinic records were changed. Screenshots contain synthetic data only.

The current backend environment has no `DATABASE_URL`, Google credentials, or `LLM_BASE_URL`; a Gnani key is configured. Configuration presence does not establish that a provider works.

## Release blockers

### 1. Postgres persistence is not operational — P0

**Reproduced:** importing `PostgresClinicStore` raises `ImportError: cannot import name 'HandoverRecord' from 'app.services.clinic_store'`. That record is defined in `booking_records.py`. Setting `DATABASE_URL` selects this broken import on the first store-dependent request.

There is a second, broader problem: the adapter inherits nearly all mutations from the in-memory store. Customers, integration keys, enquiries, services, opening hours, appointments, transcripts, handovers, and audit events do not have corresponding SQL write implementations. In an isolated probe that worked around the import only and instrumented `_exec`, creating a service, customer, availability window, and appointment produced **zero SQL writes**.

The adapter also loads a process-local snapshot on startup. Booking conflict checks use a Python lock and dictionary; the migration has no overlap exclusion constraint. These checks cannot establish correctness across workers. Clinic/member creation uses separate commits, and swallowed loader errors can leave partial state.

**Develop:** a transactional database-backed repository for all records; database-enforced overlap prevention and idempotency; explicit migration failures; rollback-safe writes; restart and multiple-worker integration tests. Fail clearly or visibly label demo storage when durability is unavailable.

Evidence: [Postgres adapter](../backend/app/services/postgres_store.py), [store selection](../backend/app/services/clinic_store.py), [booking mutations](../backend/app/services/booking_records.py), [appointment schema](../supabase/migrations/20261114180000_voice_and_booking.sql).

### 2. The receptionist can confirm a failed booking — P0

**Reproduced with an injected model response:** a `create_appointment` tool call was rejected, but the spoken/displayed response remained “I'm an AI receptionist. Your appointment is confirmed.” The pipeline executes tools after generating a response and then returns the original model text without reconciling it with the results. It also never feeds tool results back into the model to explain services, availability, or failures.

The browser checks `tool.name`, whereas the server sends `tool`. Thus the frontend's explicit booking/handover confirmation branches do not run for the actual payload shape.

**Develop:** a bounded tool-result conversation loop, result-aware confirmation messages, a shared event contract, and failed-tool response tests. A booking confirmation must require a committed appointment ID and show the actual date, time, service, and clinic timezone.

Evidence: [voice pipeline](../backend/app/services/voice_pipeline.py), [visitor event handling](../apps/voice-client/app.js). [Current mock visitor screenshot](ux-audit-2026-11-15/visitor.png).

### 3. Visitor identity and booking ownership are unfinished — P0 before live visitor bookings

**Reproduced at the tool boundary:** an unverified visitor session could reschedule a known appointment within the same clinic. The tool checks clinic membership of the appointment, but does not verify that the visitor owns it.

The new-patient journey also has no supported way to collect contact details, create/find the customer, and bind that customer to the visitor session. `create_appointment` requires a customer UUID that the visitor flow does not supply. Escalation can create a handover without usable contact details.

**Develop:** visitor contact capture and consent, patient lookup/create, verified session-to-patient binding, booking review, and identity verification for changes to existing bookings. Enforce ownership in the backend, independent of model instructions. Include a callback contact in actionable handovers.

Evidence: [public session creation](../backend/app/services/visitor_sessions.py), [booking/reschedule tools](../backend/app/services/voice_tools.py).

### 4. Calendar mixes browser and clinic timezones — P0

**Browser reproduction:** clinic timezone `Asia/Kolkata`; appointment **16 Nov 2026, 10:00 IST**. With browser timezone `America/Los_Angeles`, opening its details prefills **15 Nov 2026, 20:30** under “New start (Asia/Kolkata)”. Saving that unchanged value would interpret the browser time as India time and move the booking by 13.5 hours.

Day grouping and hour placement also use browser-local `Date` getters, while the details use clinic time. The backend's timezone tests do not cover this UI behavior.

**Develop:** consistent clinic-time formatting, grouping, input conversion, and current-day calculation. Test with differing browser/clinic timezones and daylight-saving boundaries. Keep an unchanged reschedule submission unchanged.

Evidence: [calendar implementation](../apps/dashboard/components/calendar-workspace.tsx), [reproduction screenshot](ux-audit-2026-11-15/calendar-wrong-timezone.png).

### 5. Google Calendar reports a connection without authorization — P0 before enabling Google

**Reproduced in isolation with dummy configured credentials:** passing a fabricated state containing a clinic UUID and an empty authorization code returned `connected`. The callback does not verify a stored OAuth state or exchange the code; it stores `stub:` as the refresh token and changes clinic scheduling mode.

This is more than a missing credential. Adding credentials will not make the feature functional. Busy-time reads, event creation/update/cancellation, retries, disconnect, and reconciliation are absent.

**Develop:** verified, expiring OAuth state bound to the initiating owner; real code exchange and protected refresh-token storage; calendar selection; busy-time checks; event reconciliation and honest sync status. Keep this unavailable until implemented. Clinic Dial-only scheduling can remain the initial release mode.

Evidence: [calendar connection service](../backend/app/services/calendar_connection.py).

## UX and product development backlog

| Priority | Gap and current behavior | Required development |
| --- | --- | --- |
| P1 | **Mobile navigation consumes the screen.** At 375 × 812, the sidebar is 777px tall before page content begins. Calendar day columns are about 39px wide. | Compact header with a navigation drawer; default mobile calendar to agenda/day; usable appointment tap targets. [Mobile navigation](ux-audit-2026-11-15/overview-mobile.png), [calendar](ux-audit-2026-11-15/calendar-mobile-scrolled.png). |
| P1 | **Opening hours are add-only.** Owners cannot correct/remove a window, mark a holiday, or close a day. Onboarding saves five weekdays sequentially, so failure can partially apply hours. | Editable weekly schedule, delete/replace windows, overlap validation, exception dates, and atomic save. |
| P1 | **Service catalogue is add-only.** Price input asks owners to enter paise. Draft approval uses browser prompts; existing imported names are not editable in the review UI. | Edit/archive services; enter currency in rupees; a proper draft edit/review form with duration, price, category, source, and merge controls. |
| P1 | **Clinic settings are read-only.** The profile form disappears after the onboarding step completes, leaving no normal UI to correct name/timezone. | Persisted clinic profile editor, contact details, timezone management, and clear save feedback. |
| P1 | **Enquiries are a list, not a follow-up workflow.** No search, filters, status, notes, assignment, or follow-up due date. | Enquiry detail and lifecycle: new → contacted → booked/closed; linked patient, notes, next action, and search/pagination. |
| P1 | **Patients cannot be added or edited manually.** A new clinic must obtain a website enquiry before it can book a patient. Profiles show enquiry history but no appointment timeline. | Add/edit patient, quick-create during booking, appointment/conversation history, and duplicate resolution. |
| P1 | **Booking requires guessing a datetime.** The patient “Create appointment” link navigates to Calendar but leaves the drawer closed. A new future booking leaves the grid on the original week. | Open a prefilled booking drawer directly; show available slots; validate before submission; move the calendar to the saved booking. [Successful booking](ux-audit-2026-11-15/booking-created.png), [conflict state](ux-audit-2026-11-15/booking-conflict.png). |
| P1 | **Calendar can hide records.** Day/week only render 08:00–19:59; month renders three events without a “more” affordance; month arrows add/subtract 28 days. | Derive visible hours from clinic availability; show overflow counts; navigate actual calendar months; add completed/no-show status if required for operations. |
| P1 | **Receptionist settings do not control the receptionist.** Greeting/language/approved information are saved under one browser-local key, unscoped to the clinic, and never sent to the backend. | Clinic-scoped settings API, persisted configuration, real pipeline consumption, a preview, and readiness checks. |
| P1 | **Receptionist status is unreliable.** UI expects `mode` or `live`, but `/v1/voice/status` returns configuration flags. It therefore falls back to demo mode regardless of those flags. | A shared readiness response separating demo, unavailable, configured, and verified live states. |
| P1 | **Onboarding has dead ends.** “Review imported services” only receives its link after completion. Receptionist settings do not complete the receptionist step. Rejecting/merging the last draft does not run the completion logic. | Actionable links on incomplete steps, ability to revisit completed steps, consistent completion updates, and a final booking-readiness check. |
| P1 | **Auth state needs hardening.** Signup with email confirmation throws a success message as an error. A failed profile fetch signs the owner out. The overview redirect does not exclude password recovery. | Confirmation-success screen/resend; retain valid sessions during API outages; dedicated recovery routing and a live recovery test. Recovery email behavior was not verified in this audit. |
| P1 | **Errors are not consistently accessible.** The reproduced booking conflict had no alert/live region. New auth/workspace error paragraphs usually omit `role="alert"`; async errors can coexist with a loading message. | Shared error, success, loading, and retry components; field-level validation; focus management when opening drawers. |
| P1 | **Visitor links are tied to localhost.** The owner link hardcodes port 3002 and the visitor API defaults to localhost. | Environment-configured public URLs and deployable owner/visitor/API configuration. |
| P2 | **Website import is basic.** It fetches one page and turns H2/H3 headings into candidates; duration/price/description are not extracted. Repeat import adds drafts. Backend merge marks status without merging service data. | Structured extraction, explicit page selection, deduplication, editable previews, real merge semantics, and import failure/retry guidance. |
| P2 | **Overview is not a reliable setup indicator.** “Opening hours” completion is inferred from whether appointments exist. Upcoming count is only the five displayed items. | Derive readiness from configuration; separate full totals from previews; link enquiry/appointment rows to details. |
| P2 | **Operational feedback is sparse.** Activity shows internal event names. Refresh is manual across most new pages; long lists lack navigation/search. | Human-readable activity, appropriate polling or subscriptions, pagination, filters, and consistent date formatting. |

## Voice milestone still needs implementation

The microphone is deliberately disabled with “Speak (coming soon)”. Text is sent as a mock transcript inside an audio message, rather than through a supported live text path. In live mode the transcript override only applies to `MockSttClient`, so configuring live STT would not make this text input a working alternative. The visitor player also assumes WAV while the server reports an audio content type that it ignores.

Develop microphone capture/streaming, utterance boundaries, permission-denied states, stop/reconnect handling, a proper text channel, correct audio decoding, and actual Gnani/Evon integration. Then test English/Hindi/Telugu with real conversations. The current generic mock response is useful for plumbing checks, but is not a working natural-language booking demo.

## Recommended delivery order and acceptance gates

1. **Make the core trustworthy.** Repair persistence and transactions, fix clinic-time handling, enforce visitor ownership, and prevent failed-tool confirmations. Disable incomplete external connections. Gate: data survives restart, concurrent bookings cannot overlap, unchanged reschedule stays unchanged, and rejected tools never announce success.
2. **Complete an owner-operated MVP.** Editable clinic/services/hours, manual patients, enquiry follow-up, guided available-slot booking, and mobile navigation. Gate: a fresh clinic can configure itself and create/reschedule/cancel a booking entirely through the UI without a website enquiry prerequisite.
3. **Complete visitor reception.** Persist receptionist configuration, collect/verify visitor details, consume real tool results, provide booking review/confirmation and actionable handovers. Gate: a new visitor can book, the owner sees the same booking, and only the verified patient can change it.
4. **Connect external services.** Real Google Calendar and live Gnani/Evon, provider errors/retries, deployment URLs. Gate: prove the journey with actual providers, including an outage and a busy external-calendar slot.
5. **Automate release checks and align documentation.** Install/configure ESLint; add browser tests for the above journeys; run Postgres restart/concurrency tests in CI. Keep `STATUS.md` and app READMEs aligned with what is actually verified.

Staff invitations, billing, Outlook, and advanced analytics can remain later work; they are not prerequisites for the owner-operated POC defined in the PRD.

## What is already useful

The visual language is restrained and consistent, the sign-in page has a clear primary action, and the inspected login/mobile pages do not horizontally overflow. The routed navigation and basic empty states work. Website-ingest API tests cover deduplication and clinic isolation; the isolated owner UI displays the resulting patient/enquiry and can create a booking with conflict rejection. Existing backend tests also cover cancellation, appointment availability, conversation consent, and tenant isolation.

These are useful foundations. The development priority is completing and validating the real user journeys and durable state, rather than expanding the number of screens.
