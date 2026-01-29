import pytest


@pytest.mark.integration
def test_job_posting_analyzer_crew_instantiates():
    """Test that JobPostingAnalysisCrew crew can be instantiated with its config"""
    from crews import JobPostingAnalysisCrew

    crew = JobPostingAnalysisCrew()
    assert crew is not None
    assert hasattr(crew, "crew")
    assert hasattr(crew, "job_analyst")
    assert hasattr(crew, "job_analysis_task")


@pytest.mark.integration
def test_cv_analyzer_crew_instantiates():
    """Test that CvAnalysisCrew crew can be instantiated with its config"""
    from crews import CvAnalysisCrew

    crew = CvAnalysisCrew()
    assert crew is not None
    assert hasattr(crew, "crew")
    assert hasattr(crew, "cv_analyst")
    assert hasattr(crew, "cv_analysis_task")


@pytest.mark.integration
def test_cv_optimization_crew_instantiates():
    """Test that CvOptimizationCrew can be instantiated with its config"""
    from crews import CvOptimizationCrew

    crew = CvOptimizationCrew()
    assert crew is not None
    assert hasattr(crew, "crew")
    assert hasattr(crew, "cv_strategist")
    assert hasattr(crew, "cv_rewriter")
    assert hasattr(crew, "cv_alignment_task")
    assert hasattr(crew, "cv_transformation_task")


@pytest.mark.integration
def test_service_layer_instantiates():
    """Test that service layer analyzers can be instantiated"""
    from services.analyzers import JobPostingAnalyzer
    from services.analyzers import CvAnalyzer

    job_analyzer = JobPostingAnalyzer()
    cv_analyzer = CvAnalyzer()

    assert job_analyzer is not None
    assert cv_analyzer is not None
    assert hasattr(job_analyzer, "analyze")
    assert hasattr(cv_analyzer, "analyze")
