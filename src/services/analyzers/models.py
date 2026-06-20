from dataclasses import dataclass, field

from pydantic import BaseModel

from models import CurriculumVitae


@dataclass
class OptimizerOutput:
    cv: CurriculumVitae
    artifacts: dict[str, BaseModel] = field(default_factory=dict)
