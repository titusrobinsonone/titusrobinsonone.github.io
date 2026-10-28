-- Subscription Revenue Forensics | Titus Robinson
-- Integer cents throughout. events and months are loaded by revenue_forensics.py.
-- An event is the full contracted monthly recurring amount from its effective
-- month, not an invoice or a cash receipt. End-of-month state is used.
CREATE TEMP VIEW accounts AS
SELECT customer_id, MIN(effective_month) AS first_month, MIN(segment) AS segment
FROM events GROUP BY customer_id;

CREATE TEMP VIEW customer_month AS
SELECT a.customer_id, a.segment, m.month,
       COALESCE((SELECT e.mrr_cents FROM events e
                 WHERE e.customer_id=a.customer_id AND e.effective_month<=m.month
                 ORDER BY e.effective_month DESC, e.sequence DESC LIMIT 1), 0) AS mrr_cents
FROM accounts a CROSS JOIN months m WHERE m.month>=a.first_month;

CREATE TEMP VIEW with_history AS
SELECT *,
 LAG(mrr_cents,1,0) OVER (PARTITION BY customer_id ORDER BY month) AS opening_cents,
 COALESCE(MAX(mrr_cents) OVER (PARTITION BY customer_id ORDER BY month
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) AS prior_max
FROM customer_month;

CREATE TEMP VIEW movements AS
SELECT *,
 CASE WHEN opening_cents=0 AND mrr_cents>0 AND prior_max=0 THEN mrr_cents ELSE 0 END AS new_cents,
 CASE WHEN opening_cents=0 AND mrr_cents>0 AND prior_max>0 THEN mrr_cents ELSE 0 END AS reactivation_cents,
 CASE WHEN opening_cents>0 AND mrr_cents>opening_cents THEN mrr_cents-opening_cents ELSE 0 END AS expansion_cents,
 CASE WHEN mrr_cents>0 AND mrr_cents<opening_cents THEN opening_cents-mrr_cents ELSE 0 END AS contraction_cents,
 CASE WHEN opening_cents>0 AND mrr_cents=0 THEN opening_cents ELSE 0 END AS churn_cents
FROM with_history;

CREATE TEMP VIEW revenue_bridge AS
SELECT month, segment, SUM(opening_cents) AS opening, SUM(new_cents) AS new,
 SUM(reactivation_cents) AS reactivation, SUM(expansion_cents) AS expansion,
 SUM(contraction_cents) AS contraction, SUM(churn_cents) AS churn,
 SUM(mrr_cents) AS closing, SUM(mrr_cents>0) AS active
FROM movements GROUP BY month,segment;

CREATE TEMP VIEW cohorts AS
SELECT customer_id, MIN(month) AS cohort FROM customer_month
WHERE mrr_cents>0 GROUP BY customer_id;

CREATE TEMP VIEW cohort_retention AS
SELECT c.cohort, cm.segment, cm.month, COUNT(*) AS original_customers,
 SUM(cm.mrr_cents>0) AS active_customers, SUM(cm.mrr_cents) AS mrr_cents
FROM cohorts c JOIN customer_month cm ON cm.customer_id=c.customer_id AND cm.month>=c.cohort
GROUP BY c.cohort, cm.segment, cm.month;
