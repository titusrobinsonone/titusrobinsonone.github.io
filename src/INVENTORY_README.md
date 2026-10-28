# Demand & Inventory Lab

Portfolio owner and maintainer: **Titus Robinson**. Independent, AI-assisted portfolio implementation, created October 2026. All bundled inputs and results are synthetic.

Stockouts lose sales, but excess stock ties up cash. A forecast accuracy score alone does not tell an operations team which replenishment policy to use.

## Run

Python 3.10+; no third-party packages.

```bash
python src/inventory_lab.py --output output
python -m unittest discover -s src -p 'test_portfolio_projects.py' -v
```

Use `--input docs/assets/inventory-demand.csv` to run the included source CSV. Keep output separate from input. The Python and SQL files can also be adapted to your own inputs; check their schema and validation rules first.

## Method

- Generate 224 days of transparent synthetic demand for 12 SKUs, including weekly patterns, intermittent demand and a temporary promotion.
- Use the first 84 days as warm-up. Compare rolling-mean and weekday-aware forecasts on the next 140 days, using only observations available at each decision.
- Simulate daily receipts, sales, lost demand and new orders across three lead times and four safety buffers. Reconcile every unit of stock.

## Example finding

At a seven-day lead time and a 1.645 buffer, the seasonal policy has lower forecast error, but holds more inventory. Both achieve about 99.6% unit fill. The decision depends on the service and working-capital trade-off, not forecast accuracy alone.

## Limitations

Synthetic demand is fully observed, including lost demand. Real sales data may be censored by stockouts. Lead times and unit economics are fixed, replenishment capacity is unlimited, and the safety multiplier is a heuristic rather than a guaranteed service level. Holding cost plus lost margin is an illustrative decision cost, not a complete profit model. The test set describes trade-offs; it does not establish a universally optimal policy.

## Links

- [Interactive case study](https://titusrobinsonone.github.io/project.html?id=inventory)
- [Full portfolio repository](https://github.com/titusrobinsonone/titusrobinsonone.github.io)

## Method references

- [Forecast evaluation: rolling origin](https://otexts.com/fpp3/toolbox.html)
