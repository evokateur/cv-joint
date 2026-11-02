from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class Contact(BaseModel):
    """The candidate's location and contact information."""

    city: str = Field(description="City where the candidate is based")
    state: str = Field(
        description="State, province, or region where the candidate is based"
    )
    email: str
    phone: str
    linkedin: Optional[str] = Field(
        default=None,
        description="The candidate's LinkedIn profile identifier (the part after linkedin.com/in/)",
    )
    github: Optional[str] = Field(
        default=None,
        description="The candidate's GitHub username",
    )


class Education(BaseModel):
    """An education entry from the candidate's academic history."""

    degree: str
    coursework: str = Field(
        description="Courses or subject areas studied, expressed as a single text value"
    )
    institution: str
    location: str
    start_date: str = Field(description="Date the candidate began this course of study")
    end_date: str = Field(
        description="Date this course of study ended, or an indication that it is ongoing"
    )


class Experience(BaseModel):
    """A role in the candidate's work history, with detailed responsibilities and achievements."""

    title: str
    company: str
    location: str
    start_date: str = Field(description="Date the candidate began this role")
    end_date: str = Field(
        description="Date this role ended, or an indication that it is ongoing"
    )
    responsibilities: Optional[List[str]] = Field(
        default=None,
        description="Duties and achievements in this role, including associated metrics",
    )


class AdditionalExperience(BaseModel):
    """An additional or earlier role listed without detailed responsibilities."""

    title: str
    company: str
    location: str
    start_date: str = Field(description="Date the candidate began this role")
    end_date: str = Field(
        description="Date this role ended, or an indication that it is ongoing"
    )


class AreaOfExpertise(BaseModel):
    """A named grouping of related skills in the candidate's CV."""

    name: str = Field(description="Category name for this group of skills")
    skills: List[str] = Field(
        description="Individual skills belonging to this category"
    )


class Language(BaseModel):
    """A human language and the candidate's stated proficiency."""

    language: str = Field(description="Name of the human language")
    level: str = Field(
        description="The candidate's proficiency in this language, such as native, fluent, or B2"
    )


class CurriculumVitae(BaseModel):
    """The candidate's professional profile, qualifications, and career history."""

    name: str
    contact: Contact
    profession: str = Field(
        description="Professional headline describing the candidate's role or specialization"
    )
    core_expertise: List[str] = Field(
        description="Concise highlights of the candidate's principal areas of expertise"
    )
    qualifications: List[str] = Field(
        description="Summary of qualifications; each item is a full paragraph"
    )
    education: List[Education]
    experience: List[Experience]
    additional_experience: List[AdditionalExperience]
    areas_of_expertise: List[AreaOfExpertise]
    languages: List[Language]


class CoverLetter(BaseModel):
    """A candidate's letter introducing their application to an employer."""

    name: str
    contact: Contact
    company: Optional[str] = Field(
        default=None, description="Employer the letter is addressed to"
    )
    position: Optional[str] = Field(
        default=None, description="Role the candidate is applying for"
    )
    salutation: str
    closing: str
    date: Optional[str] = Field(
        default=None,
        description="Date of the letter",
    )
    paragraphs: List[str] = Field(
        description="Body paragraphs in reading order, excluding the salutation and closing"
    )
    alternate_paragraphs: Optional[List[str]] = Field(
        default=None,
        description="Optional alternative body paragraphs available for selection",
    )


class JobPosting(BaseModel):
    """A job posting's role, requirements, and application instructions."""

    # Basic metadata
    url: Optional[str] = Field(default=None, description="The job posting URL")
    title: str
    company: str
    industry: str
    experience_level: str = Field(
        description="Seniority of the role, such as entry, mid, senior, or lead"
    )
    description: str = Field(
        description="Prose overview of what the job involves and its context"
    )

    # Requirements
    education: List[str] = Field(
        default=[], description="Degrees and certifications requested in the posting"
    )
    years_experience: Optional[str] = Field(
        default=None,
        description="Experience-duration requirements, such as 5+ years",
    )
    hard_requirements: List[str] = Field(
        default=[],
        description="Mandatory qualifications or conditions, such as a required CPA license",
    )

    # Skills (structured)
    technical_skills: List[str] = Field(
        default=[],
        description="Technical skills requested, such as Python, AWS, or GraphQL",
    )
    soft_skills: List[str] = Field(
        default=[],
        description="Interpersonal and professional skills requested, such as leadership or teamwork",
    )
    preferred_skills: List[str] = Field(
        default=[],
        description="Skills identified as desirable or nice-to-have rather than mandatory",
    )

    # Responsibilities and deliverables
    responsibilities: List[str] = Field(
        default=[],
        description="Specific day-to-day duties and ongoing work expected in the role",
    )
    deliverables: List[str] = Field(
        default=[],
        description="Concrete outputs or artifacts expected, such as an API integration or technical documentation",
    )

    # Extracted for ATS alignment
    keywords: List[str] = Field(
        default=[],
        description="ATS-relevant terms and phrases from the posting, such as domain terminology and industry keywords",
    )
    tools_and_tech: List[str] = Field(
        default=[],
        description="Technologies, platforms, products, and services named in the posting, including third-party SaaS tools and APIs",
    )

    # Application
    application_instructions: Optional[List[str]] = Field(
        default=None,
        description="Instructions for applicants, including required materials, questions, secret keywords, and formatting requirements",
    )


class CvTransformationPlan(BaseModel):
    """Plan for transforming a CV to align with a job posting."""

    # Context - copied from job posting for traceability
    job_title: str = Field(description="Job title from the posting")
    company: str = Field(description="Company name from the posting")

    # Alignment analysis - transparency about what matches
    matching_skills: List[str] = Field(
        default_factory=list, description="Skills in the CV that match job requirements"
    )
    missing_skills: List[str] = Field(
        default_factory=list,
        description="Required skills not found in the CV or knowledge base",
    )
    transferable_skills: List[str] = Field(
        default_factory=list,
        description="CV skills that relate to requirements but need reframing",
    )

    # Field-specific transformation instructions
    profession_update: Optional[str] = Field(
        default=None,
        description="Proposed replacement for the CV's professional headline",
    )
    core_expertise_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for core_expertise changes (add, remove, reorder)",
    )
    summary_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for rewriting the CV's qualifications paragraphs",
    )
    experience_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for experience[].responsibilities changes, with indices",
    )

    # ATS optimization
    keyword_insertions: List[str] = Field(
        default_factory=list,
        description="Keywords from the job posting proposed for inclusion in the CV",
    )
    quantification_suggestions: List[str] = Field(
        default_factory=list,
        description=(
            "Suggested additions of quantitative evidence, based on figures available "
            "in the CV or knowledge base"
        ),
    )

    # Evidence from knowledge base
    evidence_sources: List[str] = Field(
        default_factory=list,
        description="File paths or sources supporting the recommendations",
    )


DOMAIN_OBJECT_REGISTRY: dict[str, type["BaseModel"]] = {}


class JobPostingRecord(BaseModel):
    """
    Job posting persistence record.

    Tracks identity, provenance, and key fields needed for listing display.
    """

    identifier: str = Field(description="Unique identifier of the job posting")
    path: Optional[str] = Field(
        default=None,
        description="Directory path relative to data dir",
    )
    url: Optional[str] = Field(default=None, description="Original job posting URL")
    company: str = Field(description="Company name (for listing display)")
    title: str = Field(description="Job title (for listing display)")
    experience_level: str = Field(description="Experience level (for listing display)")
    applied_at: Optional[datetime] = Field(
        default=None, description="When the application was submitted"
    )
    applied_with: Optional[str] = Field(
        default=None, description="CV identifier used to apply"
    )
    is_archived: bool = Field(
        default=False, description="Whether this posting is archived"
    )
    location: Optional[str] = Field(
        default=None, description="Current filed location; null means active/unfiled"
    )
    transitions: list[dict] = Field(
        default_factory=list, description="Ordered audit log of location transitions"
    )
    created_at: datetime = Field(description="When this record was created")
    updated_at: datetime = Field(description="When this record was last updated")


class CurriculumVitaeRecord(BaseModel):
    """
    CV persistence record.

    Tracks identity, provenance, and key fields needed for listing display.
    """

    identifier: str = Field(description="Unique identifier of the CV")
    path: Optional[str] = Field(
        default=None,
        description="Directory path relative to data dir",
    )
    name: str = Field(description="Person's name (for listing display)")
    profession: str = Field(description="Profession (for listing display)")
    job_posting_identifier: Optional[str] = Field(
        default=None,
        description="Parent job posting identifier, if this is an optimized CV",
    )
    created_at: datetime = Field(description="When this record was created")
    updated_at: datetime = Field(description="When this record was last updated")


class OptimizedCvRecord(BaseModel):
    """
    Optimized CV persistence record.

    Tracks identity, path, and key fields for listing display.
    """

    identifier: str = Field(description="Unique identifier of the optimized CV")
    path: Optional[str] = Field(
        default=None,
        description="Directory path relative to data dir",
    )
    job_posting_identifier: str = Field(
        description="Identifier of the job posting this CV was optimized for"
    )
    base_cv_identifier: Optional[str] = Field(
        default=None,
        description="Identifier of the source CV, or None when no base CV is recorded",
    )
    name: str = Field(description="Person's name (for listing display)")
    profession: str = Field(description="Profession (for listing display)")
    job_title: Optional[str] = Field(
        default=None, description="Job title (for listing display)"
    )
    company: Optional[str] = Field(
        default=None, description="Company (for listing display)"
    )
    created_at: datetime = Field(description="When this optimized CV was created")
    updated_at: datetime = Field(description="When this optimized CV was last updated")


class CoverLetterRecord(BaseModel):
    """
    Cover letter persistence record.

    Tracks identity and key fields needed for listing display.
    """

    identifier: str = Field(description="Unique identifier of the cover letter")
    path: Optional[str] = Field(
        default=None,
        description="Directory path relative to data dir",
    )
    name: str = Field(description="Person's name (for listing display)")
    company: Optional[str] = Field(
        default=None, description="Company (for listing display)"
    )
    position: Optional[str] = Field(
        default=None, description="Position (for listing display)"
    )
    created_at: datetime = Field(description="When this record was created")
    updated_at: datetime = Field(description="When this record was last updated")


DOMAIN_OBJECT_REGISTRY.update(
    {
        "CurriculumVitae": CurriculumVitae,
        "CvTransformationPlan": CvTransformationPlan,
        "JobPosting": JobPosting,
        "CoverLetter": CoverLetter,
    }
)
