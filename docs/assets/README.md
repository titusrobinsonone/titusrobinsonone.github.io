# Survey quality → BI export

A reproducible Python portfolio demonstration for Titus Robinson. It shows how a survey CSV can be validated, reconciled and prepared for a reporting dashboard.

**Provenance:** this is new demonstration work created in October 2026. Every response, identifier, score and market-level result in the example is synthetic. It contains no employer, client or real respondent data. The synthetic results illustrate the workflow and do not claim production business performance.

## Run the demonstration

Requires Python 3.10 or later. No third-party packages or API credentials are needed.

```bash
python3 survey_pipeline.py --generate-demo --output out
```

The fixed default seed is `20261028`. Repeating the command with that seed produces the same input records and the same dashboard data. To explore another synthetic realization:

```bash
python3 survey_pipeline.py --generate-demo --seed 42 --output out-seed-42
```

To process an existing compatible CSV:

```bash
python3 survey_pipeline.py --input input.csv --output out
```

The original input is read without modification. The pipeline refuses an output directory that would overwrite its input file. A new `--generate-demo` run replaces the generated example files in the chosen output directory.

## What this demonstrates

1. Read a UTF-8 CSV and check the required columns.
2. Validate and normalize records using explicit rules.
3. Isolate rejected records with a primary reason and source record number.
4. Reconcile input, accepted and rejected row counts.
5. Aggregate defined metrics by market, week and collection channel.
6. Export BI-ready CSVs, a dashboard JSON dataset and an auditable run log.

This demonstration uses local CSV input. It does not connect to Forsta, Outlook or another external API.

## Example input and results

The seeded input has 7,200 valid responses across six markets and twelve weeks, August 3–October 25, 2026. It appends 100 intentional defects so the validation can be inspected.

| Validation result | Rows |
| --- | ---: |
| Input | 7,300 |
| Accepted | 7,200 |
| Duplicate response ID | 48 |
| Missing response ID | 24 |
| Missing or invalid satisfaction score | 18 |
| Invalid duration | 10 |

The accepted dataset contains 6,313 completed responses. Overall completion is 87.68%; CSAT is 76.29%; median completion time is 188 seconds. These are descriptive results from the synthetic input, not measured improvements in an employer's workflow.

## Metric definitions

- **Usable responses:** all rows accepted by the validation rules, including incomplete responses.
- **Completed responses:** accepted rows whose completion flag is true.
- **Completion rate:** completed accepted responses divided by all accepted responses, multiplied by 100.
- **CSAT:** completed accepted responses with a satisfaction score of 4 or 5 divided by all completed accepted responses, multiplied by 100.
- **Median completion time:** median duration, in seconds, among completed accepted responses only.
- **Validation pass rate:** accepted rows divided by input rows, multiplied by 100. The default example is 98.63%.

Rates use record counts, so market totals should be recomputed with the combined denominator rather than by averaging displayed percentages. Weekly grouping uses the Monday of the submission week. Timestamps with an explicit timezone are converted to UTC before deriving the date.

## Source schema and validation

The required header is:

```csv
response_id,market,channel,submitted_at,completed,duration_seconds,satisfaction_score
```

- `response_id`: nonempty synthetic or pseudonymous identifier. The first **valid** occurrence of an ID is accepted; later occurrences are rejected as duplicates. An earlier invalid occurrence does not prevent a later valid record from being accepted.
- `market`: United States, United Kingdom, Canada, Germany, France or Australia.
- `channel`: Web, Mobile or Email.
- `submitted_at`: parseable ISO-8601 date or timestamp.
- `completed`: true/false or 1/0, case-insensitive after whitespace trimming.
- `duration_seconds`: integer between 15 and 1,800 inclusive.
- `satisfaction_score`: integer 1–5 for completed responses. It may be blank for incomplete responses; any supplied score must still be within 1–5.

Each rejected record has one primary reason: the first failed rule. The run log and JSON include a SHA-256 digest of the exact input bytes for traceability. No personal identifiers are required.

## Output files

| File | Purpose |
| --- | --- |
| `survey_raw.csv` | Synthetic input; created only by `--generate-demo` |
| `survey_clean.csv` | Normalized accepted records and Monday week key |
| `survey_rejected.csv` | Rejected records, source record number and primary reason |
| `survey_summary.csv` | Market-level counts, rates and median completion time |
| `portfolio-data.json` | Dashboard records, grouped summaries, metadata and quality counts |
| `pipeline-run.txt` | Actual textual output from the completed pipeline run |

## Validation checks

The accompanying source includes six focused `unittest` checks covering first-valid duplicate handling, metric denominators, seeded row reconciliation, malformed/empty inputs, source preservation and invalid category values.

```bash
python3 -m unittest discover -s tests -v
```

The dashboard and walkthrough should present these as synthetic demonstration results. There is no measured runtime saving or production efficiency claim attached to this new example.

## Live portfolio

[Interactive dashboard](https://titusrobinsonone.github.io/survey.html) · [Python walkthrough](https://titusrobinsonone.github.io/automation/) · [Source repository](https://github.com/titusrobinsonone/titusrobinsonone.github.io)
