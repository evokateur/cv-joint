# {{ obj.name }}

{{ obj.contact.city }}, {{ obj.contact.state }} | {{ obj.contact.email }} | {{ obj.contact.phone }}

{% if obj.date %}
{{ obj.date }}

{% endif %}
{% if obj.company %}
{{ obj.company }}

{% endif %}
{% if obj.position %}
{{ obj.position }}

{% endif %}
{{ obj.salutation }}

{% for paragraph in obj.paragraphs %}
{{ paragraph }}

{% endfor %}
{{ obj.closing }}

{{ obj.name }}
