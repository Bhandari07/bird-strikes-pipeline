{% macro dimension_key(fields) -%}
md5(concat({% for field in fields %}
    case when {{ field }} is null then 'N;'
    else concat('V',cast(length(cast({{ field }} as varchar)) as varchar),':',cast({{ field }} as varchar),';') end
    {% if not loop.last %},{% endif %}{% endfor %}))
{%- endmacro %}
