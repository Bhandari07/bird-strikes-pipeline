{% macro json_value(column, field, kind='varchar') -%}
  {% if target.type == 'snowflake' -%}
    case when is_null_value({{ column }}:{{ field }}) then null else {{ column }}:{{ field }}::{{ kind }} end
  {%- else -%}
    cast(json_extract_string({{ column }}, '$.{{ field }}') as {{ kind }})
  {%- endif %}
{%- endmacro %}
