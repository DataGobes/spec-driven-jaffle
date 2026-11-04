{#- Generic tests used by the YAML that specgen generates from specs. -#}

{% test spec_unique_combination(model, columns) %}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}


{% test spec_check(model, column_name, expression) %}
select *
from {{ model }}
where not ({{ expression }})
{% endtest %}


{% test spec_rowcount_equals(model, compare_model) %}
with actual as (select count(*) as n from {{ model }}),
     expected as (select count(*) as n from {{ compare_model }})
select actual.n as actual_rows, expected.n as expected_rows
from actual, expected
where actual.n <> expected.n
{% endtest %}
