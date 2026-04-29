{{ frontmatter }}
# Transformation Plan: {{ obj.job_title }} at {{ obj.company }}

{% if obj.matching_skills or obj.missing_skills or obj.transferable_skills %}
## Alignment Analysis

{% if obj.matching_skills %}
**Matching Skills:**

{% for item in obj.matching_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.missing_skills %}
**Missing Skills:**

{% for item in obj.missing_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.transferable_skills %}
**Transferable Skills:**

{% for item in obj.transferable_skills -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.profession_update or obj.core_expertise_updates or obj.summary_updates or obj.experience_updates %}
## Transformations

{% if obj.profession_update -%}
**Profession Update:** {{ obj.profession_update }}

{% endif %}
{% if obj.core_expertise_updates %}
**Core Expertise Updates:**

{% for item in obj.core_expertise_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.summary_updates %}
**Summary Updates:**

{% for item in obj.summary_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.experience_updates %}
**Experience Updates:**

{% for item in obj.experience_updates -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.keyword_insertions or obj.quantification_suggestions %}
## ATS Optimization

{% if obj.keyword_insertions %}
**Keyword Insertions:**

{% for item in obj.keyword_insertions -%}
- {{ item }}
{% endfor %}
{% endif %}
{% if obj.quantification_suggestions %}
**Quantification Suggestions:**

{% for item in obj.quantification_suggestions -%}
- {{ item }}
{% endfor %}
{% endif %}
{% endif %}
{% if obj.evidence_sources %}
## Evidence Sources

{% for item in obj.evidence_sources -%}
- {{ item }}
{% endfor %}
{% endif %}
