{% macro get_date_spine(start_date='2019-01-01', end_date='2026-12-31') %}
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ start_date ~ "' as date)",
        end_date="dateadd(day, 1, cast('" ~ end_date ~ "' as date))"
    ) }}
{% endmacro %}
