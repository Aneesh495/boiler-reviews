# Section scheduling and calendar contract

The academic planner first chooses course terms. Section scheduling then chooses one observed section option per planned course in that term. A section may contain multiple meeting intervals, including a linked lecture/lab bundle. `capacity` and `capacity_observed_at` are catalog observations, not a reservation promise.

Meeting intervals use half-open `[start, end)` minutes, ISO weekday values, and an explicit IANA timezone. Back-to-back classes at 10:00 and 11:00 do not conflict. Multi-day sections are represented by multiple intervals. Asynchronous sections have no recurring meetings. A section with missing/unknown meeting information is not treated as conflicting, but the result carries an unknown-meeting warning and never claims a guaranteed conflict-free schedule.

The independent schedule validator checks term membership, blocked times, every pair of selected meetings, and the same boundary semantics. Calendar export emits one VEVENT per known interval with a stable UID, timezone-qualified DTSTART/DTEND, and a weekly RRULE bounded by the term date range. Unknown meeting intervals are omitted from export rather than inventing times.
