{{ frontmatter }}
# {{ cv.name }}

**{{ cv.contact.city }}, {{ cv.contact.state }}** | {{ cv.contact.email }} | {{ cv.contact.phone }}
{%- if cv.contact.linkedin %} | {{ cv.contact.linkedin }}{% endif %}
{%- if cv.contact.github %} | {{ cv.contact.github }}{% endif %}

## {{ cv.profession }}

{{ cv.core_expertise | join(' | ') }}

## Summary of Qualifications

{{ cv.summary_of_qualifications }}

## Areas of Expertise

{% for area in cv.areas_of_expertise -%}
- **{{ area.name }}:** {{ area.skills | join(', ') }}
{% endfor %}
## Experience

{% for job in cv.experience %}
### {{ job.title }}

**{{ job.company }}** | {{ job.location }} | {{ job.start_date }} -- {{ job.end_date }}

{% if job.responsibilities %}
{% for item in job.responsibilities -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endfor %}
## Education

{% for path in cv.education %}
### {{ path.degree }}

**{{ path.institution }}** | {{ path.location }} | {{ path.start_date }} -- {{ path.end_date }}

{% if path.coursework -%}
{{ path.coursework }}
{% endif %}
{% endfor %}
{% if cv.additional_experience %}
## Additional Experience

{% for job in cv.additional_experience -%}
- **{{ job.title }}**, {{ job.company }} ({{ job.start_date }} -- {{ job.end_date }})
{% endfor %}
{% endif %}
{% if cv.languages %}
## Languages

{% for lang in cv.languages -%}
- **{{ lang.language }}:** {{ lang.level }}
{% endfor %}
{% endif %}
