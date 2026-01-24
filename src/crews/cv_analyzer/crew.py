from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import FileReadTool
from typing import List
from models import CurriculumVitae
from crews.cv_analyzer.config.settings import get_config


@CrewBase
class CvAnalyzer():
    """CV Analyzer crew - analyzes CV files and extracts structured data"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        config = get_config()
        self.llm = LLM(
            model=config.cv_analyst_model,
            temperature=float(config.cv_analyst_temperature),
        )

    @agent
    def cv_analyst(self) -> Agent:
        """Agent that analyzes CV files"""
        return Agent(
            config=self.agents_config['cv_analyst'], # type: ignore[index]
            tools=[FileReadTool()],
            llm=self.llm,
            verbose=True
        )

    @task
    def cv_analysis_task(self) -> Task:
        """Task that extracts structured CurriculumVitae data from a CV file"""
        return Task(
            config=self.tasks_config['cv_analysis_task'], # type: ignore[index]
            output_pydantic=CurriculumVitae,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the CV Analyzer crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
