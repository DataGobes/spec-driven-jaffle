# Findings: fct_orders

Written by the coding agent while implementing `specs/fct_orders.yml` (status: draft).
The SQL follows the spec; the data disagrees with one expectation.

## 1. `amount > 0` does not hold for one order

**Spec line:** `amount` → `checks: ["amount > 0"]`
**Test:** `spec_check_fct_orders_amount__amount_0` warns with 1 row.

```sql
select * from fct_orders where not (amount > 0);
```

| order_id | customer_id | order_date | status    | amount |
|---------:|------------:|------------|-----------|-------:|
| 65       | 26          | 2018-03-08 | completed | 0.00   |

Order 65 has exactly one payment, a credit card payment of $0.00 (payment 74).
The order is `completed`, so it is not a pending or broken order.

**Options (for a human to decide):**
- The $0 order is legitimate (a free or fully discounted order): change the check to
  `amount >= 0` and add a rule saying so.
- The $0 payment is a data error: fix it upstream, keep `amount > 0`.

I have not changed the SQL, the spec or the tests.

**Decision (human, in review):** legitimate. Free and fully discounted orders exist.
The spec now says `amount >= 0` and has a rule that explains why.
