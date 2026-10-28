# Subscription Revenue Forensics

Portfolio owner and maintainer: **Titus Robinson**. Independent, AI-assisted portfolio implementation, created October 2026. All bundled inputs and results are synthetic.

A single recurring-revenue total can hide churn, contraction and reactivation. Duplicate events can also inflate reporting unless the transformation is auditable.

## Run

Python 3.10+; no third-party packages.

```bash
python src/revenue_forensics.py --output output
python -m unittest discover -s src -p 'test_portfolio_projects.py' -v
```

Use `--input docs/assets/revenue-events.csv` to run the included source CSV. Keep output separate from input. The Python and SQL files can also be adapted to your own inputs; check their schema and validation rules first.

## Method

- Validate 985 synthetic contract-change events and isolate 22 exceptions, including duplicate IDs, negative amounts and missing customer IDs.
- Build a customer-month spine in SQLite. Carry the latest contracted amount forward and use window functions to classify each movement.
- Reconcile opening MRR plus new business, reactivation and expansion, less contraction and churn, to closing MRR. Track customer retention by original acquisition cohort.

## Example finding

The September 2026 example closes at $69,891 in monthly recurring revenue. Its $2,703 net increase includes reactivation and expansion as well as churn and contraction. All 42 month-by-segment bridges reconcile to the cent.

## Limitations

This model represents end-of-month contracted MRR, not cash collections or accounting revenue recognition. It assumes one currency, a stable customer segment and full-month effective changes. It excludes proration, discounts, foreign exchange and multi-contract accounts. Cohort retention can rise after reactivation; it is active-customer retention, not continuous survival.

## Links

- [Interactive case study](https://titusrobinsonone.github.io/project.html?id=revenue)
- [Full portfolio repository](https://github.com/titusrobinsonone/titusrobinsonone.github.io)
