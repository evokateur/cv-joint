from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional


class Contact(BaseModel):
    city: str
    state: str
    email: str
    phone: str
    linkedin: str
    github: str


class Education(BaseModel):
    degree: str
    coursework: str
    institution: str
    location: str
    start_date: str
    end_date: str


class Experience(BaseModel):
    title: str
    company: str
    location: str
    start_date: str
    end_date: str
    responsibilities: Optional[List[str]] = None


class AdditionalExperience(BaseModel):
    title: str
    company: str
    location: str
    start_date: str
    end_date: str


class AreaOfExpertise(BaseModel):
    name: str
    skills: List[str]


class Language(BaseModel):
    language: str
    level: str


class CurriculumVitae(BaseModel):
    name: str
    contact: Contact
    profession: str
    core_expertise: List[str]
    summary_of_qualifications: List[str]
    education: List[Education]
    experience: List[Experience]
    additional_experience: List[AdditionalExperience]
    areas_of_expertise: List[AreaOfExpertise]
    languages: List[Language]


class CoverLetterContact(BaseModel):
    city: str
    state: str
    phone: str
    email: str


class CoverLetter(BaseModel):
    name: str
    contact: CoverLetterContact
    company: str
    position: str
    paragraphs: List[str]
    alternate_paragraphs: Optional[List[str]] = None


class JobPosting(BaseModel):
    # Basic metadata
    url: str = Field(description="The job posting URL")
    title: str
    company: str
    industry: str
    description: str
    experience_level: str  # entry, mid, senior, etc.

    # Requirements
    education: List[str] = []  # degrees, certifications
    years_experience: Optional[str] = None  # "5+ years"
    hard_requirements: List[str] = []  # absolute musts (e.g., "CPA license")

    # Skills (structured)
    technical_skills: List[str] = []  # e.g., "Python", "AWS", "GraphQL"
    soft_skills: List[str] = []  # e.g., "leadership", "teamwork"
    preferred_skills: List[str] = []  # nice-to-have

    # Responsibilities
    responsibilities: List[str] = []  # parsed job duties

    # Extracted for ATS alignment
    keywords: List[str] = []  # important phrases/terms from posting
    tools_and_tech: List[str] = []  # specific stack/tools


class CvTransformationPlan(BaseModel):
    """Plan for transforming a CV to align with a job posting."""

    # Context - copied from job posting for traceability
    job_title: str = Field(description="Job title from the posting (copied verbatim)")
    company: str = Field(description="Company name from the posting (copied verbatim)")

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
        description="New profession field value, or null if no change needed",
    )
    core_expertise_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for core_expertise changes (add, remove, reorder)",
    )
    summary_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for summary_of_qualifications rewrites",
    )
    experience_updates: List[str] = Field(
        default_factory=list,
        description="Instructions for experience[].responsibilities changes, with indices",
    )

    # ATS optimization
    keyword_insertions: List[str] = Field(
        default_factory=list,
        description="Specific keywords from job posting to incorporate",
    )
    quantification_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions to add metrics/numbers where possible",
    )

    # Evidence from knowledge base
    evidence_sources: List[str] = Field(
        default_factory=list,
        description="File paths or sources supporting the recommendations",
    )


class CvOptimization(BaseModel):
    """
    Persisted optimization metadata - the 'save marker' that makes a directory valid.

    The actual plan and optimized CV are stored in separate files (transformation-plan.json, cv.json)
    and loaded on demand. This model just tracks the optimization's identity and provenance.
    """

    identifier: str = Field(
        description="Unique identifier for this optimization (timestamp-based)"
    )
    base_cv_identifier: str = Field(
        description="Identifier of the CV this optimization transforms"
    )
    created_at: datetime = Field(description="When this optimization was created")
