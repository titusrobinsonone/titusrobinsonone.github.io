# Experiment Decision Studio

Portfolio owner and maintainer: **Titus Robinson**. Independent, AI-assisted portfolio implementation, created October 2026. All bundled inputs and results are synthetic.

A positive lift can be small, uncertain or caused by broken telemetry. A conversion gain can also come with unacceptable product errors.

## Run

Python 3.10+; no third-party packages.

```bash
python src/experiment_studio.py --output output
python -m unittest discover -s src -p 'test_portfolio_projects.py' -v
```

Use `--input docs/assets/experiment-users.csv` to run the included source CSV. Keep output separate from input. The Python and SQL files can also be adapted to your own inputs; check their schema and validation rules first.

## Method

- Analyze one user-level observation per variant in a fixed-horizon synthetic experiment, with conversion as the primary metric and product errors as a guardrail.
- Check expected 50/50 allocation with a chi-square sample-ratio test before interpreting the treatment effect.
- Use a two-sided 95% interval for the conversion difference and a one-sided 95% upper bound for error-rate harm. Compare them with explicit practical thresholds.

## Example finding

In the balanced example, conversion increases by 0.85 percentage points, but the interval’s lower bound does not establish the default 0.20-point practical lift. A separate scenario is stopped for product errors, and another is blocked for missing treatment telemetry.

## Limitations

These are synthetic, independent-user, fixed-horizon examples. Normal approximations require adequate successes and failures, which the code checks. Threshold changes in this demo are sensitivity analysis; a real experiment should specify decision rules before launch. Device slices are descriptive and have no multiple-comparison-adjusted inference. This is not a sequential-testing engine.

## Links

- [Interactive case study](https://titusrobinsonone.github.io/project.html?id=experiment)
- [Full portfolio repository](https://github.com/titusrobinsonone/titusrobinsonone.github.io)

## Method references

- [Sample-ratio mismatch: Microsoft Research](https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/)
- [Two-proportion intervals: NIST](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/diffprop.htm)
