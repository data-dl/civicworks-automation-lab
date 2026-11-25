# CivicWorks Lab

A local app for understanding the eight CivicWorks pipelines by using them - and breaking them.

```bash
python start.py             # from the repository root: sets everything up and opens the Lab
python -m civicworks_lab    # or, once installed: opens http://127.0.0.1:8870
```

Each pipeline has five tabs:

- **The flow** - the pipeline's steps in a row. Click a step for what it does in plain words, the real code it
  runs (read from the repository, `flows.py` + `learn/flows.yaml`) and the database rule it relies on, explained
  part by part. One step per pipeline has a **safeguard switch**: the Lab runs the real pipeline with that
  protection off (`CIVICWORKS_SAFEGUARD_OFF`, see `runkit.guard`) beside a normal run, and shows only what changed.
- **Guided run** - the real demo, paused before each scene: predict, run, then see the output, the exact rows
  and cells that changed (`rowdiff.py`) and each named record traced to its row. While paused you can change the
  data yourself - edit an input CSV or run SQL - and watch the next scene react.
- **Try it** - one-click experiments that change the input data (`experiments.py`, `learn/experiments.yaml`).
- **Query the data** - a SQL console on the run's database, with example questions that each teach one idea.
- **Go deeper** - design decisions, failure handling, inputs and outputs, rules, questions, video.

**Public or private.** Everything above is public: a recorded version is on the website and the code is on
GitHub. **My prep** is private: interview notes, questions by role and a worksheet for mapping each pipeline to
your own work. It is read from a `civicworks-prep` folder next to the repository (or `CIVICWORKS_PREP`), and what
you type is saved there - never in the repository.

The Lab binds to 127.0.0.1 only, can start only the registered demo commands, reads and writes files only inside
its own run folders under `build/lab-runs/`, and shows paths relative to the run or the repository.
