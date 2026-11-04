# Salary Survey Data Quality & Open-Text Pipeline

**Real-world data.** The 2021 Ask a Manager Salary Survey: 26,232 self-reported responses from a public Google Form, republished by the [TidyTuesday](https://github.com/rfordatascience/tidytuesday/tree/master/data/2021/2021-05-18) project. Respondents typed most answers as free text, so the data has the problems real survey operations teams handle every week.

[Case study report](https://titusrobinsonone.github.io/salary-qa.html) · [Pipeline](salary_survey_qa.py) · [Report builder](make_salary_report.py) · [Tests](tests/test_salary_survey_qa.py)

## Business question

Can this survey be trusted for pay benchmarking, and can it be shared without exposing respondents?

## Run it

```bash
python src/salary_survey_qa.py --input data/ask_a_manager_2021.csv --output out/salary_qa
python src/make_salary_report.py --run out/salary_qa      # rebuilds docs/salary-qa.html
python -m unittest discover -s src/tests -v
```

Standard library only, Python 3.10+. A full run takes about 2–3 seconds.

## What the pipeline does

1. **Schema check and source preservation.** Fails loudly if a column is missing, never edits the input file, and puts every row in exactly one of `clean.csv` or `rejected.csv`.
2. **Standardization.**
   - Salary text becomes numbers ("55,000", "$72k").
   - Free-text currencies are resolved, and the combined "AUD/NZD" option is split by the respondent's country.
   - 241 country spellings collapse to 91 countries, using aliases, the first country mentioned, typo matching, flag emoji and U.S. states typed as a country.
3. **Rule-based QA with severities.** Rejects are kept to things that make a row unusable for pay analysis. Everything else is a warning, so an analyst decides.

   | Severity | Rules |
   |---|---|
   | Reject | Duplicate submissions; unresolved currency; zero salary; salary under US$1,000 a year (typed in thousands or as hourly pay); over US$5M |
   | Warn | Field experience exceeding total experience; experience impossible for the age band; missing, multiple or invalid U.S. states; currency-country conflicts; robust outliers (log salary, MAD z > 4 within currency) |

4. **Privacy.**
   - **Regex PII redaction:** emails, phones, SSNs, URLs and handles in free-text fields are replaced with labels such as `[URL]`.
   - **Quasi-identifier check (k-anonymity):** counts the rows whose combination of job title, city, industry and age band is shared by fewer than 5 people. It then repeats the count at two coarser release levels.
5. **Open-ended coding.** A 13-code, market-research style codeframe for "additional context on income". One answer can get several codes. A topic that is only mentioned in negated form ("no overtime") is coded `<topic> (none)`.
6. **Impact.** Raw vs. cleaned salary statistics for the same population (everyone paid in USD), plus U.S. medians by industry.

## Results (full run)

- 26,232 rows in: 25,956 clean and 276 rejected. Every row reconciles.
- Rejects include 148 duplicate submissions and 78 salaries typed in thousands or as hourly pay.
- Raw mean salary for USD-paid respondents is **$96,659**, distorted by entries up to $102,000,000. After cleaning and excluding outliers it is **$90,948**, 5.9% lower. The median is $79,000 both ways.
- **Privacy:** the regex scan found only 3 URLs, because the form asked for no direct identifiers. But 99.4% of rows are in groups smaller than 5 on title + city + industry + age:
  - dropping city still leaves 79.8%
  - releasing only industry + age band + country cuts it to 9.8%

  Anonymous survey data still needs generalization before sharing at row level.
- **Open-ended answers:** 2,834 answers; 78.4% receive at least one code. Bonus (935) and equity (474) dominate.

## How the coding was checked

The codeframe went through two rounds, the way a coding team works:

1. A first pass, then a hand review of 100 random code assignments, which found 91 correct.
2. The errors showed clear patterns: negations, "merit bonus" coded as a raise, "hours per week" coded as hourly pay, and a union "contract" coded as contract work. After fixing those, a **fresh** random sample of 100 (seed 2026) was reviewed: **92 correct**.

Every verdict and the reason for each miss are in [`docs/assets/salary-qa/codeframe_audit.csv`](../docs/assets/salary-qa/codeframe_audit.csv). The 21.6% of answers left uncoded are mostly topics for the next codeframe round: salary schedules, summer pay, reimbursements and after-tax figures.

## Limitations

- **Not a population estimate.** Respondents are self-selected readers of one blog. Results don't describe the labor market.
- **Currency conversion is approximate.** It uses 2021 average rates and only feeds the plausibility rules. Headline salary numbers use USD-paid respondents.
- **Coding is rule-based.** It's transparent and testable, but it misses paraphrases. An LLM or embedding pass could raise coverage, as long as it's checked against the same hand-reviewed sample.
- **k-anonymity is an indicator, not a guarantee.** It doesn't cover attribute disclosure or linkage with outside data.

Author: **Titus Robinson** (November 2026). The data is public and not employer or client data.
