# opspilot - transcript

Length 144 s.

- **00:00** OpsPilot Control Center. One control room over the other pipelines - planned, checkpointed, approved by people, and unable to exceed its contracts.
- **00:12** Scene 1. The registry: the complete list of actions, each with typed inputs and an effect. No - that is deliberate.
- **00:22** Scene 2. The rules planner orders the steps of publish-cycle by their dependencies. No; it waits for both badge-init and master-propose.
- **00:33** Scene 3. Write steps run; both publish steps stop for approval. No. Approval is a separate action a person takes.
- **00:44** Scene 4. A person approves each publish step; each approval is a token scoped to one step of one run. No. Tokens are scoped to this run.
- **00:56** Scene 5. Resumed, the process stops right after the badge release. interrupted - and the checkpoints so far are saved.
- **01:06** Scene 6. Resumed again: six steps are skipped on verified checkpoints; the last one runs. Its output file still has the hash recorded when it finished, so it is provably done.
- **01:20** Scene 7. A second goal reaches the roster project, whose own checks refuse to approve. No. It stops, records the project's reason, and states the next action.
- **01:34** Scene 8. Six requests OpsPilot refuses, each logged - including erasing the log itself. The database: a trigger aborts any DELETE or UPDATE on it.
- **01:47** Scene 9. A read-only status page and a handoff note. No - it is a static snapshot.
- **01:55** The status page: runs, steps, output hashes, approvals, the event log.
- **02:04** The handoff note for the blocked run.
- **02:10** What this run showed: Publish steps waited for a person. Resume skipped only hash-verified work. A project's own block stopped the run. Unsafe requests refused and logged.

## Terminal output (captured, unedited)

```
== 1. The registry: the only actions OpsPilot can take
  masterrecord.init        write    inputs: workspace:workspace
  masterrecord.propose     write    inputs: workspace:workspace
  openbadge.init           write    inputs: workspace:workspace
  openbadge.release        publish  inputs: workspace:workspace
  regional.init            write    inputs: workspace:workspace
  regional.review          write    inputs: workspace:workspace, quarter:quarter
  regional.approve         publish  inputs: workspace:workspace, quarter:quarter, role:role
  reconcilehub.init        write    inputs: workspace:workspace
  reconcilehub.reconcile   read     inputs: workspace:workspace
  reconcilehub.commit      publish  inputs: workspace:workspace, role:role
  atlas.generate           write    inputs: workspace:workspace
  atlas.publish            publish  inputs: workspace:workspace, role:role
  ledgerguard.init         write    inputs: workspace:workspace
  ledgerguard.daily        write    inputs: workspace:workspace
  environment: {'profile': 'desktop', 'os': 'Windows', 'python': '3.14.2', 'workspace writable': True, 'desktop automation': 'not used by any registered tool'}

== 2. Plan 'publish-cycle' with the rules planner
  1. master-init       masterrecord.init
  2. badge-init        openbadge.init
  3. regional-init     regional.init
  4. master-propose    masterrecord.propose (after master-init)
  5. regional-review   regional.review (after regional-init)
  6. badge-release     openbadge.release (after badge-init, master-propose)
  7. regional-approve  regional.approve (after regional-review)

== 3. Run it: write steps proceed, publish steps wait for a person
    master-init       done               
    badge-init        done               {'learners': 120, 'badges': 305, 'seed': 20261123}
    regional-init     done               16 venues; planted in 2026Q3: {'totals_mismatch': 'HV-NF01', 'missing_contributor': 'HV-EM03', 'wrong_period': 'HV-SB02', 'duplicate_submiss
    master-propose    done               excluded GJF-0017: registry classifies it as retail showroom, which is out of scope for the master
    regional-review   done               built: Studio_2026Q2.xlsx, Outreach_2026Q2.xlsx, Incidents_2026Q2.xlsx, Review_pack_2026Q2.md
    badge-release     awaiting-approval  publishes, so a person must approve it first
    regional-approve  awaiting-approval  publishes, so a person must approve it first
  run publish-cycle-2026-11-24: AWAITING-APPROVAL
  next: a person approves badge-release, regional-approve (`opspilot approve`), then `opspilot run --resume publish-cycle-2026-11-24`

== 4. A person approves the two publish steps
  APR-0001: badge-release approved by the release manager
  APR-0002: regional-approve approved by the program director

== 5. Resume - and the machine stops right after the badge release
  !! process stopped after badge-release; run marked interrupted

== 6. Resume again: verified checkpoints are skipped, the rest finishes
    master-init       done               checkpoint verified by hash; not re-run
    badge-init        done               done earlier in this run; not re-run
    regional-init     done               checkpoint verified by hash; not re-run
    master-propose    done               checkpoint verified by hash; not re-run
    regional-review   done               done earlier in this run; not re-run
    badge-release     done               checkpoint verified by hash; not re-run
    regional-approve  done               approved copies (read-only): v1/
  run publish-cycle-2026-11-24: COMPLETE
  next: nothing; every step is done and checkpointed

== 7. A second goal: the roster project's own checks stop it
    roster-init       done               {'changed_id': 'FC-00031 -> FC-00931 (Quin Brindlecote)', 'missing_id': 'Lark Brindlecote', 'role_drift': 'FC-00013 member -> steward in the
    roster-check      done               note: FC-00005 and FC-00059 share a name; kept as different people (ids differ)
    roster-commit     blocked            exit 1: BLOCKED: 3 case(s) held for review ['2026-11-held-cases.eml']
  run roster-cycle-2026-11-24: BLOCKED
  next: roster-commit: its project's own checks stopped it - read logs/roster-cycle-2026-11-24/roster-commit.log, fix the cause in that project, then `opspilot run --resume roster-cycle-2026-11-24`

== 8. Requests OpsPilot refuses (each one is logged)
  an unregistered command: REFUSED - 'shell.exec' is not a registered tool; there is no general command runner
  a path outside the workspaces: REFUSED - openbadge.init: workspace '../../Windows' is outside workspaces/
  a publish outside a planned, approved run: REFUSED - openbadge.release publishes; it runs only inside a planned run, after a person approves it
  a language-model plan: REFUSED - language-model planning is disabled (set OPSPILOT_LLM=1 to enable the interface)
  approving a step that does not publish: REFUSED - master-init does not publish; it needs no approval
  erasing the event log: REFUSED by the database - event_log is append-only

== 9. Read-only status page
  status.html (35 events, 2 runs); handoff notes in logs/<run>/HANDOFF.md
```
