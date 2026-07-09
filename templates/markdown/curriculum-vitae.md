# {{ obj.name }}

**{{ obj.contact.city }}, {{ obj.contact.state }}** | {{ obj.contact.email }} | {{ obj.contact.phone }}
{%- if obj.contact.linkedin %} | {{ obj.contact.linkedin }}{% endif %}
{%- if obj.contact.github %} | {{ obj.contact.github }}{% endif %}

## {{ obj.profession }}

{{ obj.core_expertise | join(' | ') }}

## Summary of Qualifications

{% for qualification in obj.qualifications -%}
- {{ qualification }}
{% endfor %}

## Areas of Expertise

{% for area in obj.areas_of_expertise -%}
- **{{ area.name }}:** {{ area.skills | join(', ') }}
{% endfor %}
## Experience

{% for job in obj.experience %}
### {{ job.title }}

**{{ job.company }}** | {{ job.location }} | {{ job.start_date }} -- {{ job.end_date }}

{% if job.responsibilities %}
{% for item in job.responsibilities -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endfor %}
## Education

{% for path in obj.education %}
### {{ path.degree }}

**{{ path.institution }}** | {{ path.location }} | {{ path.start_date }} -- {{ path.end_date }}

{% if path.coursework -%}
{{ path.coursework }}
{% endif %}
{% endfor %}
{% if obj.additional_experience %}
## Additional Experience

{% for job in obj.additional_experience -%}
- **{{ job.title }}**, {{ job.company }} ({{ job.start_date }} -- {{ job.end_date }})
{% endfor %}
{% endif %}
{% if obj.languages %}
## Languages

{% for lang in obj.languages -%}
- **{{ lang.language }}:** {{ lang.level }}
{% endfor %}
{% endif %}
