# CivicWorks Lab

A local app for running the eight CivicWorks pipelines one scene at a time and learning how they work.

```bash
pip install -e ./lab        # after installing the eight projects
python -m civicworks_lab    # opens http://127.0.0.1:8870 in your browser
```

- **Guided run** starts a pipeline's real demo in step mode. Before each scene it explains what is about
  to happen and asks you to predict the result; after the scene it shows the output, what happened, and
  every file and database table that changed. Click any file to open it in the page: spreadsheets (with
  their formulas), Word reports, PDF pages with bookmarks, JSON, email drafts, and SQLite databases drawn
  as a data model you can browse.
- **Big ideas, glossary, interview prep and flashcards** come from the plain-language files in `learn/`,
  the same source the documentation site uses.
- **Quick run** runs every demo start to finish and lists what each produced.

The Lab binds to 127.0.0.1 only, can start only the registered demo commands, and reads files only
inside its own run folders under `build/lab-runs/`.
