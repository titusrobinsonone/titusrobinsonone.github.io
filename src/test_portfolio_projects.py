"""Behavioral checks for Titus Robinson's three analytical case studies."""
import copy
import math
import unittest
import inventory_lab as inv
import revenue_forensics as rev
import experiment_studio as exp


class InventoryTests(unittest.TestCase):
    def setUp(self): self.rows=inv.generate_demo(days=112,skus=1)

    def test_future_changes_do_not_change_prior_predictions(self):
        altered=copy.deepcopy(self.rows)
        for r in altered[100:]: r['demand']=10000
        a=inv.simulate_sku(self.rows,'seasonal',7,1.645)['trace']
        b=inv.simulate_sku(altered,'seasonal',7,1.645)['trace']
        self.assertEqual(a[:16],b[:16])

    def test_stock_flow_reconciles_and_cannot_sell_missing_stock(self):
        result=inv.simulate_sku(self.rows,'rolling',7,0)
        for r in result['trace']:
            self.assertEqual(r['opening']+r['arrivals']-r['sold'],r['closing'])
            self.assertEqual(r['sold']+r['lost'],r['demand'])
            self.assertGreaterEqual(r['closing'],0)
        self.assertEqual(result['demand'],result['fulfilled']+result['lost'])

    def test_orders_arrive_after_exact_lead_time(self):
        result=inv.simulate_sku(self.rows,'rolling',3,1)['trace']
        for i,row in enumerate(result): self.assertEqual(row['arrivals'],result[i-3]['ordered'] if i>=3 else 0)

    def test_duplicate_or_missing_days_rejected(self):
        with self.assertRaises(ValueError): inv.validate(self.rows+[self.rows[0]])
        with self.assertRaises(ValueError): inv.validate(self.rows[:95]+self.rows[96:])


class RevenueTests(unittest.TestCase):
    @staticmethod
    def events():
        return [dict(event_id=f'E{i}',customer_id='A',effective_month=f'2026-{i+1:02}',mrr_cents=cents,segment='SMB',sequence=i)
                for i,cents in enumerate([10000,15000,8000,0,9000])]

    def test_expansion_contraction_churn_reactivation_are_distinct(self):
        data,db,_=rev.model(self.events(),end_month='2026-05');db.close();b=data['bridges']
        self.assertEqual(b[0]['new'],10000);self.assertEqual(b[1]['expansion'],5000)
        self.assertEqual(b[2]['contraction'],7000);self.assertEqual(b[3]['churn'],8000)
        self.assertEqual(b[4]['reactivation'],9000);self.assertEqual(b[4]['new'],0)
        self.assertTrue(all(r['residual']==0 for r in b))

    def test_state_is_carried_through_a_month_without_events(self):
        data,db,_=rev.model(self.events()[:1],end_month='2026-03');db.close()
        self.assertEqual([r['closing'] for r in data['bridges']],[10000]*3)
        self.assertEqual(data['bridges'][1]['new'],0)

    def test_duplicate_events_do_not_inflate_revenue(self):
        rows=self.events(); data,db,bad=rev.model(rows+[rows[0]],end_month='2026-05');db.close()
        self.assertEqual(data['bridges'][0]['closing'],10000)
        self.assertEqual(bad[0]['reason'],'duplicate_event_id')

    def test_invalid_money_and_changing_segments_are_quarantined(self):
        rows=self.events(); rows+=[dict(rows[0],event_id='bad',mrr_cents=-1),dict(rows[1],event_id='wrong',segment='Mid-market')]
        good,bad=rev.validate(rows)
        self.assertEqual(len(good),5)
        self.assertEqual([r['reason'] for r in bad],['invalid_mrr','segment_changed'])

    def test_latest_sequence_in_month_determines_closing_mrr(self):
        rows=self.events()[:1]+[dict(self.events()[0],event_id='later',sequence=99,mrr_cents=20000)]
        data,db,_=rev.model(rows,end_month='2026-01');db.close()
        self.assertEqual(data['bridges'][0]['closing'],20000)


class ExperimentTests(unittest.TestCase):
    def test_balanced_and_broken_allocations(self):
        self.assertEqual(exp.srm(10000,10000)['pValue'],1)
        self.assertFalse(exp.srm(12000,9600)['passed'])

    def test_difference_interval_and_direction(self):
        x=exp.difference(200,1000,240,1000)
        se=math.sqrt(.2*.8/1000+.24*.76/1000)
        self.assertAlmostEqual(x['delta'],.04)
        self.assertAlmostEqual(x['lower'],.04-exp.Z95*se)
        reversed_result=exp.difference(240,1000,200,1000)
        self.assertAlmostEqual(reversed_result['delta'],-x['delta'])

    def test_allocation_failure_overrides_large_positive_effect(self):
        result=dict(allocation=dict(passed=False),conversion=exp.difference(100,1000,300,1000),errors=exp.difference(20,1000,20,1000))
        self.assertEqual(exp.decide(result),'Investigate allocation')

    def test_guardrail_regression_overrides_positive_conversion(self):
        result=dict(allocation=dict(passed=True),conversion=exp.difference(1000,10000,1500,10000),errors=exp.difference(100,10000,500,10000))
        self.assertEqual(exp.decide(result),'Stop: guardrail regression')

    def test_invalid_counts_and_duplicate_users_fail(self):
        with self.assertRaises(ValueError): exp.difference(0,0,2,10)
        row=dict(user_id='a',variant='control',converted=0,error=0)
        with self.assertRaises(ValueError): exp.analyze([row,row])


if __name__=='__main__': unittest.main()
