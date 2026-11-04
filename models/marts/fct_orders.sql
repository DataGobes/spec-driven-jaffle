-- Implemented by a coding agent from specs/fct_orders.yml

with orders as (

    select order_id, customer_id, order_date, status
    from {{ ref('stg_orders') }}

),

order_amounts as (

    -- rule: amount is the sum of all payments, regardless of payment method
    select order_id, sum(amount) as amount
    from {{ ref('stg_payments') }}
    group by order_id

)

select
    cast(orders.order_id as integer) as order_id,
    cast(orders.customer_id as integer) as customer_id,
    cast(orders.order_date as date) as order_date,
    cast(orders.status as varchar) as status,
    -- rule: every order has at least one payment, so no default for missing amounts
    cast(order_amounts.amount as decimal(18,2)) as amount
from orders
left join order_amounts using (order_id)
