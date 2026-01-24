from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from typing import List
from models.schema import JobPosting
from crews.job_posting_analyzer.config.settings import get_config


@CrewBase
class JobPostingAnalyzer():
    """Job Posting Analyzer crew - analyzes job posting URLs and extracts structured data"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        config = get_config()
        self.llm = LLM(
            model=config.job_analyst_model,
            temperature=float(config.job_analyst_temperature),
        )

    @agent
    def job_analyst(self) -> Agent:
        """Agent that analyzes job postings from URLs"""
        return Agent(
            config=self.agents_config['job_analyst'], # type: ignore[index]
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
            llm=self.llm,
            verbose=True
        )

    @task
    def job_analysis_task(self) -> Task:
        """Task that extracts structured JobPosting data from a URL"""
        return Task(
            config=self.tasks_config['job_analysis_task'], # type: ignore[index]
            output_pydantic=JobPosting,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Job Posting Analyzer crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
