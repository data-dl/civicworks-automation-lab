"""What each video says: the one-line problem, a plain explanation per demo scene, which real outputs to
show, and the closing points. The terminal text itself is never scripted - it is captured from a real
run of the project's demo command."""

SCRIPTS = {
    "openbadge": {
        "dir": "openbadge-registry-publisher",
        "title": "OpenBadge Registry Publisher",
        "problem": ("Publishing a public data file so that bad records and bad uploads never reach the people "
                    "who import it."),
        "scenes": {
            1: "Every learner, badge and date comes from a fixed seed, so the same academy can be rebuilt exactly.",
            2: "The registry is written as a dated file, fetched back over HTTP and matched by hash. Only then does "
               "'latest' point to it.",
            3: "Two bad records are planted. The release is blocked, each finding names the record, and nothing "
               "is published.",
            4: "The data is fixed, but the upload is cut off half way. The hash check catches it, so consumers stay "
               "on the last good release and a ticket opens.",
            5: "The rerun publishes. The outside catalogue imports a day later: pending, then accepted, tracked "
               "apart from the technical result.",
            6: "Rollback refuses the release that never verified and returns to the last one that did, after "
               "checking it over HTTP.",
            7: "Every attempt stays on record, including the blocked and failed ones.",
        },
        "artifacts": [
            ("text", "site/latest.json", "The pointer consumers read: which release, its hash and record count."),
            ("text", "tickets/T001-R0003-verify-failed.md", "The correction ticket opened by the cut-off upload."),
            ("json_head", "runs/R0004/manifest.json", "Every release leaves a manifest: stages, hashes, seed, "
                                                      "versions and the verdict."),
        ],
        "close": ["Bad records blocked with the record named", "A damaged upload never became 'latest'",
                  "Rollback only to a release proven good", "Every attempt on record"],
    },
    "regional": {
        "dir": "regional-programs-analytics",
        "title": "Regional Programs Analytics",
        "problem": "Quarterly Excel reports for an arts network that refuse to be approved while the data is "
                   "incomplete or wrong.",
        "scenes": {
            1: "Sixteen invented venues send a CSV every quarter. This quarter's files carry five planted problems.",
            2: "Last quarter is clean: checks pass, the program director approves, and the workbooks are frozen "
               "read-only.",
            3: "This quarter builds draft workbooks but approval is blocked: two venues missing, one total that "
               "does not add up. A wrong-quarter file and a second version are handled and noted.",
            4: "The late and corrected files arrive. Rerun: everything reconciles and the quarter is approved. "
               "A real attendance swing is flagged for commentary.",
            5: "Approving again replaces nothing. A revision would need --new-version and would sit beside v1.",
            6: "Approved workbooks and draft emails. Nothing is sent; the outbox holds drafts for a person.",
        },
        "artifacts": [
            ("excel", "approved/2026Q3/v1/Studio_2026Q3.xlsx|Summary", "The approved Summary tab: every figure is a "
                                                                       "formula over the venue rows, with the chart."),
            ("excel", "approved/2026Q3/v1/Studio_2026Q3.xlsx|Quarter Comparison", "Like-for-like comparison with "
                                                                                  "last quarter."),
            ("excel", "approved/2026Q3/v1/Incidents_2026Q3.xlsx|Incidents", "The incident workbook, reportable "
                                                                            "incidents highlighted."),
            ("text", "outbox/2026Q3/2026Q3-program-director.eml", "A distribution draft - marked NOT SENT."),
        ],
        "close": ["Missing venues and bad totals blocked approval", "Wrong-quarter and duplicate files handled, "
                  "not counted twice", "Approved quarters frozen and hashed", "Distribution is draft-only"],
    },
    "safesite": {
        "dir": "safesite-compliance-cycle",
        "title": "SafeSite Compliance Cycle",
        "problem": "A quarterly safety-return cycle: reminders, checks, escalations and two Word reports, with "
                   "nothing sent and no final overwritten.",
        "scenes": {
            1: "Twelve invented facilities and four coordinators. Returns are due 15 December; the calendar sets "
               "the reminder dates.",
            2: "Two weeks out, six returns arrive. Three are refused with the exact reason; correction requests and "
               "first reminders are drafted.",
            3: "Three days out, the corrections come back and pass. Running the same day again drafts nothing new.",
            4: "Past the deadline, two facilities are overdue. Escalations copy the safety lead, and final reports "
               "are refused while returns are missing.",
            5: "The late returns arrive and are marked late. The safety lead approves; a second approval "
               "overwrites nothing.",
            6: "Working drafts, QA material, approved finals and the outbox are kept in separate folders.",
        },
        "artifacts": [
            ("word", "final/2026Q4/workshop_2026Q4_FINAL.docx|1", "The Workshop & Studio report, approved."),
            ("word", "final/2026Q4/depot_2026Q4_FINAL.docx|1", "The Warehouse & Depot variant is organised around "
                                                                "open actions."),
            ("text", "outbox/2026Q4/2026Q4-F03-correction-F03_v1.eml", "A correction request: the exact problem, "
                                                                        "drafted, never sent."),
            ("text", "qa/2026Q4/QA_pack_2026Q4.md", "The QA pack: every return, its file hash and its reminders."),
        ],
        "close": ["Each bad return refused with its reason", "Reminders never duplicated, never sent",
                  "No final until every return was in", "An approved final is never overwritten"],
    },
    "masterrecord": {
        "dir": "masterrecord-steward",
        "title": "MasterRecord Steward",
        "problem": "Master records fed by three systems that disagree: decide what the evidence justifies, hold "
                   "the rest for a person, change nothing else.",
        "scenes": {
            1: "A guild master workbook with history and reference rows at row 500, and three feeds that disagree.",
            2: "Each field is resolved by a precedence matrix. Five changes are justified; four cases are held "
               "because no rule can settle them; one workshop is out of scope.",
            3: "The registrar approves the changes and settles two holds with a reason. Two stay open.",
            4: "A dry run shows exactly which cells would change.",
            5: "Apply: a verified backup, the decided cells written, a new dated Changes tab, and a check that "
               "every other cell is unchanged.",
            6: "The same decisions again change nothing: each decision is recorded once by its hash.",
            7: "Next run, only the two undecided holds come back. Settled questions stay settled.",
        },
        "artifacts": [
            ("excel", "review/Review_queue_2026-11.xlsx|Holds - decide", "The review queue: each hold with the "
                                                                         "evidence from every source."),
            ("excel", "master/Guild_Workshop_Master.xlsx|Changes 2026-11-23", "The new Changes tab: old value, "
                                                                              "new value, decision, role, reason."),
            ("text", "review/decisions_2026-11_signed.csv", "The registrar's decisions file."),
        ],
        "close": ["Authority wins; disagreements are held, never guessed", "Unknown is kept apart from ineligible",
                  "Only approved cells changed; history and row 500 intact", "Applying twice changes nothing"],
    },
    "reconcilehub": {
        "dir": "reconcilehub",
        "title": "ReconcileHub",
        "problem": "Monthly access-roster reconciliation that never merges two people on a guess.",
        "scenes": {
            1: "Three inputs: the door-access system's roster, last month's approvals, new registrations, with "
               "the usual mess planted.",
            2: "Exact id matches are decided automatically. An id change, a row with no id and a likely duplicate "
               "registration are held with a suggestion.",
            3: "Approval is refused while cases are held, and a note to the space admins is drafted.",
            4: "A reviewer records same-person for each. Only now do they become rename and fix-id actions.",
            5: "Approved: a hashed roster snapshot, an import workbook and a change report.",
            6: "Same inputs and decisions again: identical hash, nothing new written.",
            7: "A late registration after approval is refused unless superseded with a reason; v2 sits beside v1.",
        },
        "artifacts": [
            ("excel", "exports/2026-11/Access_import_2026-11_v1.xlsx|Import", "The import workbook: one row per "
                                                                              "action, with the reason."),
            ("text", "exports/2026-11/Change_report_2026-11_v1.md", "The change report, reviewed cases included."),
            ("text", "outbox/2026-11/2026-11-held-cases.eml", "The draft to space admins while cases were held."),
        ],
        "close": ["Ids normalised, originals kept", "Near-matches suggested, never merged",
                  "Approval blocked until people decided", "Re-runs idempotent; changes need a reason"],
    },
    "opspilot": {
        "dir": "opspilot-control-center",
        "title": "OpsPilot Control Center",
        "problem": "One control room for the other pipelines that cannot do more than its contracts allow.",
        "scenes": {
            1: "The registry is the complete list of actions: typed inputs and an effect class. There is no "
               "'run any command'.",
            2: "The rules planner orders the steps by what each one waits for.",
            3: "Write steps run. Both publish steps stop: they need a person's approval.",
            4: "A person approves each publish step; each approval is a token scoped to one step of one run.",
            5: "Resumed, the process stops right after the badge release. The run is marked interrupted.",
            6: "Resumed again: six steps are skipped because their outputs still hash the same; the last one "
               "runs. Complete.",
            7: "A second goal reaches the roster project, whose own checks refuse to approve. OpsPilot stops and "
               "says what to do next.",
            8: "Requests it refuses, each logged: an unknown command, a path outside its folders, an unapproved "
               "publish, a language-model plan, and erasing history.",
            9: "A read-only status page and a handoff note for whoever picks the run up.",
        },
        "artifacts": [
            ("html", "status.html", "The status page: runs, steps, output hashes, approvals, the event log."),
            ("text", "logs/roster-cycle-2026-11-23/HANDOFF.md", "The handoff note for the blocked run."),
        ],
        "close": ["Publish steps waited for a person", "Resume skipped only hash-verified work",
                  "A project's own block stopped the run", "Unregistered and unsafe requests refused and logged"],
    },
}
