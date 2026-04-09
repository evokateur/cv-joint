{{ frontmatter }}
# {% if job.company and job.company | lower != 'not specified' %}{{ job.title }} at {{ job.company }}{% else %}{{ job.title }}{% endif %}

{% if job.url -%}
**Original Posting:** {{ job.url | linkify }}

{% endif -%}
{% if job.company and job.company | lower != 'not specified' -%}
**Company:** {{ job.company }}

{% endif -%}
{% if job.industry -%}
**Industry:** {{ job.industry }}

{% endif -%}
{% if job.experience_level -%}
**Experience Level:** {{ job.experience_level }}

{% endif -%}
{% if job.description %}
## Description

{{ job.description }}

{% endif %}
{% if job.education or job.years_experience or job.hard_requirements %}
## Requirements

{% if job.education %}
**Education:**

{% for item in job.education -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.years_experience -%}
**Years Experience:** {{ job.years_experience }}

{% endif %}
{% if job.hard_requirements %}
**Must Have:**

{% for item in job.hard_requirements -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if job.technical_skills or job.soft_skills or job.preferred_skills %}
## Skills

{% if job.technical_skills %}
**Technical:**

{% for item in job.technical_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.soft_skills %}
**Soft:**

{% for item in job.soft_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.preferred_skills %}
**Preferred:**

{% for item in job.preferred_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if job.responsibilities %}
## Responsibilities

{% for item in job.responsibilities -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.deliverables %}
## Deliverables

{% for item in job.deliverables -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.keywords or job.tools_and_tech %}
## ATS Optimization

{% if job.keywords %}
**Keywords:**

{% for item in job.keywords -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if job.tools_and_tech %}
**Tools and Technologies:**

{% for item in job.tools_and_tech -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if job.application_instructions %}
## Application Instructions

{% for item in job.application_instructions -%}
- {{ item }}
{% endfor %}
{% endif %}
