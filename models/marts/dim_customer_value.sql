-- Implemented by a coding agent from specs/dim_customer_value.yml

with customers as (

    select customer_id, first_name
    from {{ ref('stg_customers') }}

),

customer_revenue as (

    select
        customer_id,
        count(*) as active_months,
        sum(revenue) as lifetime_revenue
    from {{ ref('fct_customer_monthly_revenue') }}
    group by customer_id

),

-- rule: every customer appears, including customers without revenue
joined as (

    select
        customers.customer_id,
        customers.first_name,
        coalesce(customer_revenue.active_months, 0) as active_months,
        coalesce(customer_revenue.lifetime_revenue, 0) as lifetime_revenue
    from customers
    left join customer_revenue using (customer_id)

)

select
    cast(customer_id as integer) as customer_id,
    cast(first_name as varchar) as first_name,
    cast(active_months as integer) as active_months,
    cast(lifetime_revenue as decimal(18,2)) as lifetime_revenue,
    -- rule: 'high' from 50 dollars, 'medium' from 20, 'low' above 0, else 'none'
    cast(case
        when lifetime_revenue >= 50 then 'high'
        when lifetime_revenue >= 20 then 'medium'
        when lifetime_revenue > 0 then 'low'
        else 'none'
    end as varchar) as value_tier
from joined
