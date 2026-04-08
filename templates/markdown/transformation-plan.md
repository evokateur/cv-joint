{{ frontmatter }}
# Transformation Plan: {{ plan.job_title }} at {{ plan.company }}

{% if plan.matching_skills or plan.missing_skills or plan.transferable_skills %}
## Alignment Analysis

{% if plan.matching_skills %}
**Matching Skills:**

{% for item in plan.matching_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if plan.missing_skills %}
**Missing Skills:**

{% for item in plan.missing_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if plan.transferable_skills %}
**Transferable Skills:**

{% for item in plan.transferable_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if plan.profession_update or plan.core_expertise_updates or plan.summary_updates or plan.experience_updates %}
## Transformations

{% if plan.profession_update -%}
**Profession Update:** {{ plan.profession_update }}

{% endif %}
{% if plan.core_expertise_updates %}
**Core Expertise Updates:**

{% for item in plan.core_expertise_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if plan.summary_updates %}
**Summary Updates:**

{% for item in plan.summary_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if plan.experience_updates %}
**Experience Updates:**

{% for item in plan.experience_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if plan.keyword_insertions or plan.quantification_suggestions %}
## ATS Optimization

{% if plan.keyword_insertions %}
**Keyword Insertions:**

{% for item in plan.keyword_insertions -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if plan.quantification_suggestions %}
**Quantification Suggestions:**

{% for item in plan.quantification_suggestions -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if plan.evidence_sources %}
## Evidence Sources

{% for item in plan.evidence_sources -%}
- {{ item }}
{% endfor %}
{% endif %}
