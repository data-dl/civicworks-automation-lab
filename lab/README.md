# CivicWorks Lab

A local app for running the eight CivicWorks pipelines one scene at a time and learning how they work.

```bash
python start.py             # from the repository root: sets everything up and opens the Lab
python -m civicworks_lab    # or, once installed: opens http://127.0.0.1:8870
```

- **Guided run** starts a pipeline's real demo in step mode. Before each scene it explains what is about
  to happen and asks you to predict the result; after the scene it shows the output, the exact rows and
  cells that changed (`rowdiff.py`), and every record the output names traced back to its row. While the
  run is paused you can **change the data**: edit any input CSV or run SQL against the run's database,
  then run the next scene and see how the pipeline reacts.
- **Experiments** (`experiments.py`, defined in `learn/experiments.yaml`) apply one preset change to the real
  inputs after scene 1 and run a normal run beside it; the page shows only the lines of output that differ.
  Every edit must hit something - an edit that matches nothing is an error, never a silent pass.
- **Query the data** is a SQL console on each pipeline's database with example questions that each teach
  one idea. Writes are allowed: it is a sandbox copy that belongs to that run.
- Click any file to open it in the page: spreadsheets (with their formulas), Word reports, PDF pages with
  bookmarks, JSON, email drafts, and SQLite databases drawn as a data model you can browse.
- **Big ideas, glossary, interview prep and flashcards** come from the plain-language files in `learn/`,
  the same source the documentation site uses.
- **Quick run** runs every demo start to finish and lists what each produced.

The Lab binds to 127.0.0.1 only, can start only the registered demo commands, and reads and writes files
only inside its own run folders under `build/lab-runs/`. Tables that store file paths are shown relative
to the run, so no machine's folder names appear on screen.
