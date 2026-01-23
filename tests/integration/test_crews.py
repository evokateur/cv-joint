import pytest


@pytest.mark.integration
def test_job_posting_analyzer_crew_instantiates():
    """Test that JobPostingAnalyzer crew can be instantiated with its config"""
    from job_posting_analyzer.crew import JobPostingAnalyzer

    crew = JobPostingAnalyzer()
    assert crew is not None
    assert hasattr(crew, "crew")
    assert hasattr(crew, "job_analyst")
    assert hasattr(crew, "job_analysis_task")


@pytest.mark.integration
def test_cv_analyzer_crew_instantiates():
    """Test that CvAnalyzer crew can be instantiated with its config"""
    from cv_analyzer.crew import CvAnalyzer

    crew = CvAnalyzer()
    assert crew is not None
    assert hasattr(crew, "crew")
    assert hasattr(crew, "cv_analyst")
    assert hasattr(crew, "cv_analysis_task")


@pytest.mark.integration
def test_service_layer_instantiates():
    """Test that service layer analyzers can be instantiated"""
    from services.analyzers.job_posting_analyzer import JobPostingAnalyzer
    from services.analyzers.cv_analyzer import CvAnalyzer

    job_analyzer = JobPostingAnalyzer()
    cv_analyzer = CvAnalyzer()

    assert job_analyzer is not None
    assert cv_analyzer is not None
    assert hasattr(job_analyzer, "analyze")
    assert hasattr(cv_analyzer, "analyze")
