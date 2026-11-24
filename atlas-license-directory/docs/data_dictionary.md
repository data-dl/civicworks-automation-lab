# Data dictionary

All values are synthetic. Sensitivity: none.

| table | column | constraint | meaning |
|---|---|---|---|
| source_file | (source_name, period) | PK | one row per source CSV per period |
| source_file | sha256, row_count, columns, loaded_at | | exactly what was received |
| district | district_id, label | PK, unique | CR Cinderreach, LM Larkmoor, SW Saltwick, TV Thornvale |
| craft | craft_code, label | PK, unique | 12 invented crafts, e.g. GLS Glassblowing |
| guild_member | member_id | PK | `M0042` |
| guild_member | invented_name, raw_name | | cleaned and as-received name |
| guild_member | phone_token, raw_phone | | `555-312-4567` and the original format |
| guild_member | active_state | active / suspended / retired | |
| guild_member | public_opt_in | 0 / 1 | may appear in the public edition |
| studio | studio_id | PK | `S019` |
| studio | district_id, raw_district | FK district (NULL if unknown) | |
| studio | studio_name, venue_token | | |
| endorsement | endorsement_id | PK | `E0007` |
| endorsement | member_id | FK guild_member | |
| endorsement | craft_code, raw_craft | FK craft (NULL if unmapped) | |
| endorsement | valid_from, valid_to | ISO dates | must be real and still valid on the release date |
| placement | placement_id | PK | member-studio-edition |
| placement | (member_id, studio_id, edition_code) | unique | edition_code public / member / inspector |
| placement | approved | 0 / 1 | |
| review_candidate | member_a, member_b, similarity, evidence | | possible duplicate people; never merged |
| directory_release | release_id | PK | the period |
| directory_release | stage | frozen / rendered / verified / published / rolled-back | |
| directory_release | snapshot_hash, approved_by, pdf_count, manifest_hash | | |

Files: `sources/<period>/*.csv`, `qa/<period>/qa_summary.{html,csv,json}`,
`snapshots/<period>/snapshot.sqlite` (read-only), `staging/<period>/*.pdf`,
`published/<period>/{*.pdf, MANIFEST.json, CHANGES.md}`, `published/CURRENT.json`,
`runs/<period>/state.json` (checkpoints) and `manifest-*.json`.
