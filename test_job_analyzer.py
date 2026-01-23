"""
Quick test to verify the job posting analyzer works.
"""

from services.optimization_service import CvOptimizationService

service = CvOptimizationService()

# Use the same URL from the job_analysis script
url = "https://app.welcometothejungle.com/dashboard/jobs/oA1SArxV"

print(f"Analyzing job posting: {url}\n")

try:
    result = service.create_job_posting(url)
    print("✓ Analysis successful!")
    print(f"\nIdentifier: {result['identifier']}")
    print(f"Company: {result['company']}")
    print(f"Title: {result['title']}")
    print(f"Experience Level: {result['experience_level']}")
    print(f"\nTechnical Skills ({len(result['technical_skills'])}):")
    for skill in result['technical_skills'][:10]:
        print(f"  - {skill}")
    if len(result['technical_skills']) > 10:
        print(f"  ... and {len(result['technical_skills']) - 10} more")
except Exception as e:
    print(f"✗ Analysis failed: {e}")
    import traceback
    traceback.print_exc()
