{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is not none -%}
        {{ custom_schema_name | trim | upper }}
    {%- elif node.resource_type == 'seed' -%}
        SEEDS
    {%- elif 'staging' in node.fqn -%}
        STAGING
    {%- elif 'intermediate' in node.fqn -%}
        INTERMEDIATE
    {%- elif 'marts' in node.fqn -%}
        MARTS
    {%- else -%}
        {{ default_schema }}
    {%- endif -%}
{%- endmacro %}
