from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, task, crew
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import FileReadTool
from typing import List

from models import CurriculumVitae, CvTransformationPlan
from crews.tools import KnowledgeSearchTool
from .config.settings import get_config


@CrewBase
class CvOptimizationCrew:
    """CV Optimization crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        config = get_config()
        self.llms = {
            "cv_strategist": LLM(
                model=config.cv_strategist_model,
                temperature=float(config.cv_strategist_temperature),
            ),
            "cv_rewriter": LLM(
                model=config.cv_rewriter_model,
                temperature=float(config.cv_rewriter_temperature),
            ),
        }

    @agent
    def cv_strategist(self) -> Agent:
        """Agent that devises a strategy to optimize CVs for job postings"""
        return Agent(
            config=self.agents_config["cv_strategist"],  # type: ignore[index]
            tools=[
                FileReadTool(),
                KnowledgeSearchTool(),
            ],
            llm=self.llms["cv_strategist"],
        )

    @agent
    def cv_rewriter(self) -> Agent:
        """Agent that rewrites CVs based on the strategy devised by the CV Strategist"""
        return Agent(
            config=self.agents_config["cv_rewriter"],  # type: ignore[index]
            tools=[FileReadTool()],
            llm=self.llms["cv_rewriter"],
        )

    @task
    def cv_alignment_task(self) -> Task:
        """Task that devises an optimization strategy for aligning CVs to job postings"""
        return Task(
            config=self.tasks_config["cv_alignment_task"],  # type: ignore[index]
            output_pydantic=CvTransformationPlan,
        )

    @task
    def cv_transformation_task(self) -> Task:
        """Task that rewrites CVs based on the optimization strategy"""
        return Task(
            config=self.tasks_config["cv_transformation_task"],  # type: ignore[index]
            output_pydantic=CurriculumVitae,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
