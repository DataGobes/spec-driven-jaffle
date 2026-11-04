-- Implemented by a coding agent from specs/fct_customer_monthly_revenue.yml

with orders as (

    select order_id, customer_id, order_date
    from {{ ref('stg_orders') }}
    -- rule: returned and return_pending orders do not count as revenue
    where status not in ('returned', 'return_pending')

),

order_revenue as (

    -- rule: revenue is the sum of all payments on an order
    select order_id, sum(amount) as revenue
    from {{ ref('stg_payments') }}
    group by order_id

),

monthly as (

    select
        orders.customer_id,
        date_trunc('month', orders.order_date)::date as order_month,
        count(*) as order_count,
        sum(coalesce(order_revenue.revenue, 0)) as revenue
    from orders
    left join order_revenue using (order_id)
    group by 1, 2

)

select
    cast(customer_id as integer) as customer_id,
    cast(order_month as date) as order_month,
    cast(order_count as integer) as order_count,
    cast(revenue as decimal(18,2)) as revenue
from monthly
