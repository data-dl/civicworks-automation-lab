"""Which real outputs each video shows, and its closing points. Everything else a video says - the
problem, the scene explanations, the results - comes from learn/pipelines/*.yaml, the same plain-language
source the Lab and the documentation site use. The terminal text is never scripted: it is captured from
a real run of the project's demo command.

kind: excel (file|sheet), word (file|page), pdf (file|page), html (file), text (file), json_head (file)
"""

SCRIPTS = {
    "atlas": {
        "artifacts": [
            ("pdf", "published/2026-11/LM-member.pdf|2", "The contents page: every entry is a link, and every page number was planned before drawing."),
            ("pdf", "published/2026-11/LM-member.pdf|3", "A craft section: each listing printed from the frozen snapshot."),
            ("html", "qa/2026-11/qa_summary.html", "The QA summary: every finding with its rule, records and fix."),
            ("text", "published/2026-12/CHANGES.md", "December compared with November: what was added and withdrawn."),
        ],
        "close": ["Six bad records blocked, each one named", "Nothing printed before a named sign-off",
                  "A crash mid-print resumed without redoing work", "Every PDF verified; rollback re-hashes first"],
    },
    "openbadge": {
        "artifacts": [
            ("text", "site/latest.json", "The pointer consumers read: which release, its hash and record count."),
            ("text", "tickets/T001-R0003-verify-failed.md", "The correction ticket opened by the cut-off upload."),
            ("json_head", "runs/R0004/manifest.json", "Every release leaves a manifest: stages, hashes, seed, versions, verdict."),
        ],
        "close": ["Bad records blocked with the record named", "A damaged upload never became 'latest'",
                  "Rollback only to a release proven good", "Every attempt on record"],
    },
    "regional": {
        "artifacts": [
            ("excel", "approved/2026Q3/v1/Studio_2026Q3.xlsx|Summary", "The approved Summary tab: every figure is a formula over the venue rows."),
            ("excel", "approved/2026Q3/v1/Studio_2026Q3.xlsx|Quarter Comparison", "Like-for-like comparison with last quarter."),
            ("text", "outbox/2026Q3/2026Q3-program-director.eml", "A distribution draft - marked NOT SENT."),
        ],
        "close": ["Missing venues and bad totals blocked approval", "Wrong-quarter and duplicate files never counted twice",
                  "Approved quarters frozen and hashed", "Distribution is draft-only"],
    },
    "ledgerguard": {
        "artifacts": [
            ("html", "archive/2026-11-25/dashboard.html", "The dashboard on the day the export columns changed: quarantined, with the reason."),
            ("excel", "current/exceptions.xlsx|Summary", "The exception workbook: each job, rows expected and found, exceptions."),
            ("text", "archive/2026-11-24/MANIFEST.json", "An archived day's manifest: every file's fingerprint, checked before any restore."),
        ],
        "close": ["An empty or reshaped export never counted as success", "Yesterday's good file kept, clearly marked stale",
                  "Every day archived with fingerprints", "A tampered archive is refused"],
    },
    "safesite": {
        "artifacts": [
            ("word", "final/2026Q4/workshop_2026Q4_FINAL.docx|1", "The Workshop and Studio report, approved."),
            ("word", "final/2026Q4/depot_2026Q4_FINAL.docx|1", "The Warehouse and Depot variant is organised around open actions."),
            ("text", "outbox/2026Q4/2026Q4-F03-correction-F03_v1.eml", "A correction request: the exact problem, drafted, never sent."),
        ],
        "close": ["Each bad return refused with its reason", "Reminders never duplicated, never sent",
                  "No final until every return was in", "An approved final is never overwritten"],
    },
    "masterrecord": {
        "artifacts": [
            ("excel", "review/Review_queue_2026-11.xlsx|Holds - decide", "The review queue: each hold with the evidence from every source."),
            ("excel", "master/Guild_Workshop_Master.xlsx|Changes 2026-11-23", "The new Changes tab: old value, new value, decision, role, reason."),
        ],
        "close": ["Authority wins; disagreements are held, never guessed", "Unknown kept apart from ineligible",
                  "Only approved cells changed; history intact", "Applying twice changes nothing"],
    },
    "reconcilehub": {
        "artifacts": [
            ("excel", "exports/2026-11/Access_import_2026-11_v1.xlsx|Import", "The import workbook: one row per action, with the reason."),
            ("text", "exports/2026-11/Change_report_2026-11_v1.md", "The change report, reviewed cases included."),
        ],
        "close": ["Ids normalised, originals kept", "Near-matches suggested, never merged",
                  "Approval blocked until people decided", "Re-runs idempotent; changes need a reason"],
    },
    "opspilot": {
        "artifacts": [
            ("html", "status.html", "The status page: runs, steps, output hashes, approvals, the event log."),
            ("text", "logs/roster-cycle-*/HANDOFF.md", "The handoff note for the blocked run."),
        ],
        "close": ["Publish steps waited for a person", "Resume skipped only hash-verified work",
                  "A project's own block stopped the run", "Unsafe requests refused and logged"],
    },
}
