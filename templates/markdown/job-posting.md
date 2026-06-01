# {% if obj.company and obj.company | lower != 'not specified' %}{{ obj.title }} at {{ obj.company }}{% else %}{{ obj.title }}{% endif %}

{% if obj.url -%}
**Original Posting:** {{ obj.url | linkify }}

{% endif -%}
{% if obj.company and obj.company | lower != 'not specified' -%}
**Company:** {{ obj.company }}

{% endif -%}
{% if obj.industry -%}
**Industry:** {{ obj.industry }}

{% endif -%}
{% if obj.experience_level -%}
**Experience Level:** {{ obj.experience_level }}

{% endif -%}
{% if obj.description %}
## Description

{{ obj.description }}

{% endif %}
{% if obj.education or obj.years_experience or obj.hard_requirements %}
## Requirements

{% if obj.education %}
**Education:**

{% for item in obj.education -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.years_experience -%}
**Years Experience:** {{ obj.years_experience }}

{% endif %}
{% if obj.hard_requirements %}
**Must Have:**

{% for item in obj.hard_requirements -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.technical_skills or obj.soft_skills or obj.preferred_skills %}
## Skills

{% if obj.technical_skills %}
**Technical:**

{% for item in obj.technical_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.soft_skills %}
**Soft:**

{% for item in obj.soft_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.preferred_skills %}
**Preferred:**

{% for item in obj.preferred_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.responsibilities %}
## Responsibilities

{% for item in obj.responsibilities -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.deliverables %}
## Deliverables

{% for item in obj.deliverables -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.keywords or obj.tools_and_tech %}
## ATS Optimization

{% if obj.keywords %}
**Keywords:**

{% for item in obj.keywords -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.tools_and_tech %}
**Tools and Technologies:**

{% for item in obj.tools_and_tech -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.application_instructions %}
## Application Instructions

{% for item in obj.application_instructions -%}
- {{ item }}
{% endfor %}
{% endif %}
