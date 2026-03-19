#!/usr/bin/env python3
"""
Research Plan Generator - Proof of Concept Implementation

This module demonstrates the core functionality for converting Darwin hypotheses
into actionable research plans.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PhaseStatus(Enum):
    """Project phase status."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


@dataclass
class Hypothesis:
    """Darwin hypothesis structure."""
    id: str
    text: str
    score: float
    generation: int
    evolved_from: Optional[str]
    references: List[str]


@dataclass
class Resource:
    """Research resource specification."""
    name: str
    type: str  # 'equipment', 'material', 'personnel', 'software'
    description: str
    quantity: int
    unit_cost: float
    availability_date: datetime
    criticality: RiskLevel


@dataclass
class Milestone:
    """Project milestone definition."""
    id: str
    name: str
    description: str
    phase: str
    due_date: datetime
    deliverables: List[str]
    dependencies: List[str]
    success_criteria: List[str]
    status: PhaseStatus


@dataclass
class Risk:
    """Risk assessment entry."""
    id: str
    description: str
    category: str  # 'technical', 'resource', 'external'
    probability: float  # 0.0-1.0
    impact: RiskLevel
    mitigation_strategy: str
    contingency_plan: str


@dataclass
class ExperimentalDesign:
    """Experimental design specification."""
    study_type: str
    sample_size: int
    control_groups: List[str]
    independent_variables: List[str]
    dependent_variables: List[str]
    statistical_methods: List[str]
    power_analysis: Dict[str, Any]


@dataclass
class ResearchPlan:
    """Complete research plan structure."""
    id: str
    title: str
    hypothesis: Hypothesis
    objectives: List[str]
    methodology: str
    timeline_weeks: int
    budget_total: float
    resources: List[Resource]
    milestones: List[Milestone]
    risks: List[Risk]
    experimental_design: ExperimentalDesign
    expected_outcomes: List[str]
    created_date: datetime


class HypothesisParser:
    """Parse and validate Darwin hypothesis input."""

    def parse_darwin_json(self, json_data: str | Dict[str, Any]) -> List[Hypothesis]:
        """Parse Darwin JSON output into Hypothesis objects."""
        if isinstance(json_data, str):
            data = json.loads(json_data)
        else:
            data = json_data

        hypotheses = []
        for hyp_data in data.get("final_hypotheses", []):
            hypothesis = Hypothesis(
                id=hyp_data["id"],
                text=hyp_data["text"],
                score=hyp_data["score"],
                generation=hyp_data["generation"],
                evolved_from=hyp_data.get("evolved_from"),
                references=hyp_data.get("references", [])
            )
            hypotheses.append(hypothesis)

        return hypotheses

    def parse_darwin_text(self, text_content: str) -> List[Hypothesis]:
        """Extract hypotheses from Darwin text output."""
        # Simplified parser - in practice would use regex/NLP
        hypotheses = []
        lines = text_content.split('\n')

        current_hyp = None
        for line in lines:
            if line.startswith('#') and '[Score:' in line:
                # New hypothesis
                if current_hyp:
                    hypotheses.append(current_hyp)

                # Extract score from "#1. [Score: 1.0000]" format
                score_part = line.split('[Score: ')[1].split(']')[0]
                score = float(score_part)

                current_hyp = {
                    'id': str(uuid.uuid4())[:8],
                    'score': score,
                    'text': '',
                    'generation': 1,  # Default
                    'evolved_from': None,
                    'references': []
                }
            elif current_hyp and line.strip() and not line.startswith('   Generation:'):
                # Hypothesis text content
                if current_hyp['text']:
                    current_hyp['text'] += ' ' + line.strip()
                else:
                    current_hyp['text'] = line.strip()

        if current_hyp:
            hypotheses.append(current_hyp)

        return [Hypothesis(**hyp) for hyp in hypotheses]


class ResourceEstimator:
    """Estimate required resources for research execution."""

    def __init__(self):
        # Resource templates based on hypothesis types and complexity
        self.equipment_templates = {
            'ml_computational': [
                Resource(
                    name="GPU Cluster", type="equipment",
                    description="High-performance GPU cluster for ML training",
                    quantity=1, unit_cost=50000.0,
                    availability_date=datetime.now() + timedelta(weeks=4),
                    criticality=RiskLevel.HIGH
                ),
                Resource(
                    name="Cloud Computing Credits", type="software",
                    description="AWS/GCP credits for scalable computation",
                    quantity=10000, unit_cost=0.50,
                    availability_date=datetime.now(),
                    criticality=RiskLevel.MEDIUM
                )
            ],
            'materials_synthesis': [
                Resource(
                    name="Synthesis Equipment", type="equipment",
                    description="Chemical synthesis and processing equipment",
                    quantity=1, unit_cost=75000.0,
                    availability_date=datetime.now() + timedelta(weeks=8),
                    criticality=RiskLevel.HIGH
                ),
                Resource(
                    name="Chemical Precursors", type="material",
                    description="Raw materials for synthesis experiments",
                    quantity=100, unit_cost=500.0,
                    availability_date=datetime.now() + timedelta(weeks=2),
                    criticality=RiskLevel.MEDIUM
                )
            ],
            'characterization': [
                Resource(
                    name="XRD System", type="equipment",
                    description="X-ray diffraction for structural analysis",
                    quantity=1, unit_cost=200000.0,
                    availability_date=datetime.now() + timedelta(weeks=12),
                    criticality=RiskLevel.HIGH
                ),
                Resource(
                    name="SEM/TEM Access", type="equipment",
                    description="Electron microscopy for morphological analysis",
                    quantity=40, unit_cost=150.0,  # Per hour
                    availability_date=datetime.now() + timedelta(weeks=1),
                    criticality=RiskLevel.MEDIUM
                )
            ]
        }

    def estimate_resources(self, hypothesis: Hypothesis) -> List[Resource]:
        """Estimate required resources based on hypothesis content."""
        resources = []
        text_lower = hypothesis.text.lower()

        # Keyword-based resource estimation
        if any(keyword in text_lower for keyword in ['machine learning', 'neural network', 'algorithm']):
            resources.extend(self.equipment_templates['ml_computational'])

        if any(keyword in text_lower for keyword in ['synthesis', 'fabrication', 'processing']):
            resources.extend(self.equipment_templates['materials_synthesis'])

        if any(keyword in text_lower for keyword in ['characterization', 'analysis', 'microscopy']):
            resources.extend(self.equipment_templates['characterization'])

        # Add personnel resources
        resources.append(
            Resource(
                name="Principal Investigator", type="personnel",
                description="Lead researcher with domain expertise",
                quantity=1, unit_cost=120000.0,  # Annual salary
                availability_date=datetime.now(),
                criticality=RiskLevel.CRITICAL
            )
        )

        resources.append(
            Resource(
                name="Research Assistant", type="personnel",
                description="Graduate student or postdoc researcher",
                quantity=2, unit_cost=50000.0,  # Annual salary
                availability_date=datetime.now() + timedelta(weeks=2),
                criticality=RiskLevel.HIGH
            )
        )

        return resources


class TimelineGenerator:
    """Generate project timelines and milestones."""

    def generate_milestones(self, hypothesis: Hypothesis, timeline_weeks: int) -> List[Milestone]:
        """Generate standard research milestones."""
        start_date = datetime.now()
        milestones = []

        # Phase 1: Foundation (25% of timeline)
        foundation_end = start_date + timedelta(weeks=int(timeline_weeks * 0.25))
        milestones.append(
            Milestone(
                id="M1", name="Foundation Complete",
                description="Literature review and methodology setup",
                phase="foundation", due_date=foundation_end,
                deliverables=[
                    "Comprehensive literature review",
                    "Methodology validation report",
                    "Resource procurement complete"
                ],
                dependencies=[],
                success_criteria=[
                    "All required resources secured",
                    "Methodology validated on test cases",
                    "Team competency confirmed"
                ],
                status=PhaseStatus.PLANNED
            )
        )

        # Phase 2: Development (35% of timeline)
        development_end = start_date + timedelta(weeks=int(timeline_weeks * 0.6))
        milestones.append(
            Milestone(
                id="M2", name="Development Complete",
                description="Method development and initial validation",
                phase="development", due_date=development_end,
                deliverables=[
                    "Validated experimental protocols",
                    "Initial proof-of-concept results",
                    "Quality control procedures"
                ],
                dependencies=["M1"],
                success_criteria=[
                    "Reproducible experimental protocols",
                    "Reliable data collection pipeline",
                    "Initial hypothesis validation signals"
                ],
                status=PhaseStatus.PLANNED
            )
        )

        # Phase 3: Execution (30% of timeline)
        execution_end = start_date + timedelta(weeks=int(timeline_weeks * 0.9))
        milestones.append(
            Milestone(
                id="M3", name="Execution Complete",
                description="Full experimental campaign and analysis",
                phase="execution", due_date=execution_end,
                deliverables=[
                    "Complete experimental dataset",
                    "Statistical analysis results",
                    "Hypothesis validation results"
                ],
                dependencies=["M2"],
                success_criteria=[
                    "Statistically significant results obtained",
                    "Hypothesis clearly validated or refuted",
                    "Reproducibility demonstrated"
                ],
                status=PhaseStatus.PLANNED
            )
        )

        # Phase 4: Dissemination (10% of timeline)
        final_end = start_date + timedelta(weeks=timeline_weeks)
        milestones.append(
            Milestone(
                id="M4", name="Project Complete",
                description="Results validation and dissemination",
                phase="dissemination", due_date=final_end,
                deliverables=[
                    "Peer-reviewed publication draft",
                    "Reproducibility documentation",
                    "Data and code repositories"
                ],
                dependencies=["M3"],
                success_criteria=[
                    "Manuscript ready for submission",
                    "Community validation achieved",
                    "Knowledge transfer completed"
                ],
                status=PhaseStatus.PLANNED
            )
        )

        return milestones


class RiskAssessment:
    """Assess and manage project risks."""

    def assess_risks(self, hypothesis: Hypothesis, resources: List[Resource]) -> List[Risk]:
        """Generate risk assessment for the research plan."""
        risks = []

        # Technical risks based on hypothesis complexity
        complexity_score = self._assess_complexity(hypothesis)
        if complexity_score > 0.7:
            risks.append(
                Risk(
                    id="R1",
                    description="High technical complexity may lead to methodology failures",
                    category="technical",
                    probability=0.35,
                    impact=RiskLevel.HIGH,
                    mitigation_strategy="Early feasibility studies and expert consultation",
                    contingency_plan="Simplify approach or develop alternative methodology"
                )
            )

        # Resource risks
        high_cost_resources = [r for r in resources if r.unit_cost > 50000]
        if high_cost_resources:
            risks.append(
                Risk(
                    id="R2",
                    description="High-cost equipment may be unavailable or delayed",
                    category="resource",
                    probability=0.25,
                    impact=RiskLevel.HIGH,
                    mitigation_strategy="Early procurement and backup equipment identification",
                    contingency_plan="Alternative methods or equipment sharing agreements"
                )
            )

        # Timeline risks
        risks.append(
            Risk(
                id="R3",
                description="Timeline delays due to experimental complexity",
                category="external",
                probability=0.45,
                impact=RiskLevel.MEDIUM,
                mitigation_strategy="Realistic scheduling with buffer allocation",
                contingency_plan="Parallel processing and scope prioritization"
            )
        )

        return risks

    def _assess_complexity(self, hypothesis: Hypothesis) -> float:
        """Assess hypothesis complexity (0.0-1.0 scale)."""
        text = hypothesis.text.lower()
        complexity_indicators = [
            'multi-scale', 'hybrid', 'complex', 'novel', 'unprecedented',
            'real-time', 'dynamic', 'non-equilibrium', 'interpretable'
        ]

        complexity_count = sum(1 for indicator in complexity_indicators if indicator in text)
        return min(complexity_count / len(complexity_indicators), 1.0)


class ExperimentalDesigner:
    """Design experimental frameworks for hypothesis testing."""

    def design_experiment(self, hypothesis: Hypothesis) -> ExperimentalDesign:
        """Design experimental approach for hypothesis validation."""
        # Simplified experimental design based on hypothesis type
        text_lower = hypothesis.text.lower()

        if 'machine learning' in text_lower or 'model' in text_lower:
            return self._design_ml_experiment(hypothesis)
        elif 'synthesis' in text_lower or 'materials' in text_lower:
            return self._design_materials_experiment(hypothesis)
        else:
            return self._design_general_experiment(hypothesis)

    def _design_ml_experiment(self, hypothesis: Hypothesis) -> ExperimentalDesign:
        """Design ML-focused experimental validation."""
        return ExperimentalDesign(
            study_type="computational_validation",
            sample_size=1000,  # Dataset size
            control_groups=["baseline_model", "random_baseline"],
            independent_variables=["model_architecture", "training_data", "hyperparameters"],
            dependent_variables=["accuracy", "precision", "recall", "f1_score"],
            statistical_methods=["cross_validation", "statistical_significance_test", "effect_size"],
            power_analysis={
                "effect_size": 0.3,
                "alpha": 0.05,
                "power": 0.8,
                "sample_size_justification": "Based on similar ML validation studies"
            }
        )

    def _design_materials_experiment(self, hypothesis: Hypothesis) -> ExperimentalDesign:
        """Design materials science experimental validation."""
        return ExperimentalDesign(
            study_type="experimental_validation",
            sample_size=30,  # Number of material samples
            control_groups=["standard_synthesis", "literature_benchmark"],
            independent_variables=["synthesis_conditions", "precursor_composition", "processing_parameters"],
            dependent_variables=["structural_properties", "functional_properties", "performance_metrics"],
            statistical_methods=["anova", "regression_analysis", "design_of_experiments"],
            power_analysis={
                "effect_size": 0.5,
                "alpha": 0.05,
                "power": 0.8,
                "sample_size_justification": "Standard for materials characterization studies"
            }
        )

    def _design_general_experiment(self, hypothesis: Hypothesis) -> ExperimentalDesign:
        """Design general experimental validation approach."""
        return ExperimentalDesign(
            study_type="mixed_methods",
            sample_size=50,
            control_groups=["control_condition", "historical_baseline"],
            independent_variables=["primary_factor", "secondary_factor"],
            dependent_variables=["primary_outcome", "secondary_outcomes"],
            statistical_methods=["t_test", "regression_analysis", "descriptive_statistics"],
            power_analysis={
                "effect_size": 0.4,
                "alpha": 0.05,
                "power": 0.8,
                "sample_size_justification": "Conservative estimate for exploratory research"
            }
        )


class ResearchPlanGenerator:
    """Main class for generating comprehensive research plans."""

    def __init__(self):
        self.parser = HypothesisParser()
        self.resource_estimator = ResourceEstimator()
        self.timeline_generator = TimelineGenerator()
        self.risk_assessor = RiskAssessment()
        self.experiment_designer = ExperimentalDesigner()

    def generate_plan(
        self,
        hypothesis: Hypothesis,
        timeline_weeks: int = 32,
        budget_limit: Optional[float] = None
    ) -> ResearchPlan:
        """Generate a complete research plan from a Darwin hypothesis."""

        # Generate plan components
        resources = self.resource_estimator.estimate_resources(hypothesis)
        milestones = self.timeline_generator.generate_milestones(hypothesis, timeline_weeks)
        risks = self.risk_assessor.assess_risks(hypothesis, resources)
        experimental_design = self.experiment_designer.design_experiment(hypothesis)

        # Calculate total budget
        total_budget = sum(r.quantity * r.unit_cost for r in resources)

        # Generate objectives from hypothesis
        objectives = self._generate_objectives(hypothesis)

        # Create research plan
        plan = ResearchPlan(
            id=str(uuid.uuid4()),
            title=f"Research Plan: {hypothesis.text[:50]}...",
            hypothesis=hypothesis,
            objectives=objectives,
            methodology=self._generate_methodology(hypothesis),
            timeline_weeks=timeline_weeks,
            budget_total=total_budget,
            resources=resources,
            milestones=milestones,
            risks=risks,
            experimental_design=experimental_design,
            expected_outcomes=self._generate_expected_outcomes(hypothesis),
            created_date=datetime.now()
        )

        return plan

    def _generate_objectives(self, hypothesis: Hypothesis) -> List[str]:
        """Generate research objectives from hypothesis."""
        return [
            f"Validate the hypothesis: {hypothesis.text}",
            "Develop reproducible experimental methodology",
            "Quantify the effect size and statistical significance",
            "Assess practical implications and applications",
            "Document findings for peer review and replication"
        ]

    def _generate_methodology(self, hypothesis: Hypothesis) -> str:
        """Generate methodology description."""
        return f"""
        This research will employ a systematic approach to validate the hypothesis through
        both computational and experimental methods. The methodology will include:

        1. Comprehensive literature review and gap analysis
        2. Development of validated experimental protocols
        3. Systematic data collection with appropriate controls
        4. Statistical analysis and hypothesis testing
        5. Results validation and reproducibility assessment

        The approach is designed to provide robust evidence for or against the hypothesis:
        "{hypothesis.text}"
        """

    def _generate_expected_outcomes(self, hypothesis: Hypothesis) -> List[str]:
        """Generate expected research outcomes."""
        return [
            "Validated or refuted hypothesis with statistical confidence",
            "Peer-reviewed publication in high-impact journal",
            "Reproducible experimental protocols and datasets",
            "Practical insights for future research directions",
            "Potential intellectual property or commercialization opportunities"
        ]

    def export_plan(self, plan: ResearchPlan, output_format: str = 'json') -> str:
        """Export research plan in specified format."""
        if output_format == 'json':
            return self._export_json(plan)
        elif output_format == 'markdown':
            return self._export_markdown(plan)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _export_json(self, plan: ResearchPlan) -> str:
        """Export plan as JSON."""
        # Convert dataclass to dict for JSON serialization
        plan_dict = {
            'id': plan.id,
            'title': plan.title,
            'hypothesis': {
                'id': plan.hypothesis.id,
                'text': plan.hypothesis.text,
                'score': plan.hypothesis.score,
                'generation': plan.hypothesis.generation,
                'evolved_from': plan.hypothesis.evolved_from,
                'references': plan.hypothesis.references
            },
            'objectives': plan.objectives,
            'methodology': plan.methodology,
            'timeline_weeks': plan.timeline_weeks,
            'budget_total': plan.budget_total,
            'resources': [
                {
                    'name': r.name,
                    'type': r.type,
                    'description': r.description,
                    'quantity': r.quantity,
                    'unit_cost': r.unit_cost,
                    'availability_date': r.availability_date.isoformat(),
                    'criticality': r.criticality.value
                }
                for r in plan.resources
            ],
            'milestones': [
                {
                    'id': m.id,
                    'name': m.name,
                    'description': m.description,
                    'phase': m.phase,
                    'due_date': m.due_date.isoformat(),
                    'deliverables': m.deliverables,
                    'dependencies': m.dependencies,
                    'success_criteria': m.success_criteria,
                    'status': m.status.value
                }
                for m in plan.milestones
            ],
            'risks': [
                {
                    'id': r.id,
                    'description': r.description,
                    'category': r.category,
                    'probability': r.probability,
                    'impact': r.impact.value,
                    'mitigation_strategy': r.mitigation_strategy,
                    'contingency_plan': r.contingency_plan
                }
                for r in plan.risks
            ],
            'experimental_design': {
                'study_type': plan.experimental_design.study_type,
                'sample_size': plan.experimental_design.sample_size,
                'control_groups': plan.experimental_design.control_groups,
                'independent_variables': plan.experimental_design.independent_variables,
                'dependent_variables': plan.experimental_design.dependent_variables,
                'statistical_methods': plan.experimental_design.statistical_methods,
                'power_analysis': plan.experimental_design.power_analysis
            },
            'expected_outcomes': plan.expected_outcomes,
            'created_date': plan.created_date.isoformat()
        }

        return json.dumps(plan_dict, indent=2)

    def _export_markdown(self, plan: ResearchPlan) -> str:
        """Export plan as Markdown document."""
        md_content = f"""
# {plan.title}

**Plan ID:** {plan.id}
**Created:** {plan.created_date.strftime('%Y-%m-%d %H:%M')}
**Timeline:** {plan.timeline_weeks} weeks
**Budget:** ${plan.budget_total:,.2f}

## Hypothesis

**ID:** {plan.hypothesis.id}
**Score:** {plan.hypothesis.score:.4f}
**Generation:** {plan.hypothesis.generation}

{plan.hypothesis.text}

## Objectives

{chr(10).join(f"- {obj}" for obj in plan.objectives)}

## Methodology

{plan.methodology}

## Timeline & Milestones

| Milestone | Phase | Due Date | Status |
|-----------|-------|----------|---------|
{chr(10).join(f"| {m.name} | {m.phase} | {m.due_date.strftime('%Y-%m-%d')} | {m.status.value} |" for m in plan.milestones)}

## Resource Requirements

| Resource | Type | Quantity | Cost | Criticality |
|----------|------|----------|------|-------------|
{chr(10).join(f"| {r.name} | {r.type} | {r.quantity} | ${r.unit_cost:,.2f} | {r.criticality.value} |" for r in plan.resources)}

**Total Budget:** ${plan.budget_total:,.2f}

## Risk Assessment

""" + chr(10).join([f"""### {risk.description} ({risk.impact.value.title()} Risk)
**Probability:** {risk.probability:.0%}
**Category:** {risk.category}
**Mitigation:** {risk.mitigation_strategy}
**Contingency:** {risk.contingency_plan}
""" for risk in plan.risks]) + """

## Experimental Design

**Study Type:** {plan.experimental_design.study_type}
**Sample Size:** {plan.experimental_design.sample_size}

**Control Groups:** {', '.join(plan.experimental_design.control_groups)}
**Independent Variables:** {', '.join(plan.experimental_design.independent_variables)}
**Dependent Variables:** {', '.join(plan.experimental_design.dependent_variables)}
**Statistical Methods:** {', '.join(plan.experimental_design.statistical_methods)}

### Power Analysis
{chr(10).join(f"- **{k}:** {v}" for k, v in plan.experimental_design.power_analysis.items())}

## Expected Outcomes

{chr(10).join(f"- {outcome}" for outcome in plan.expected_outcomes)}

---
*Generated by Research Plan Generator*
"""
        return md_content


# Example usage and demonstration
def demo_research_plan_generator():
    """Demonstrate the research plan generator with a sample Darwin hypothesis."""

    # Sample Darwin hypothesis
    sample_hypothesis = Hypothesis(
        id="2975",
        text="Cross-domain transfer learning between materials databases will exhibit systematic biases that correlate with differences in experimental measurement protocols, requiring development of domain adaptation techniques that account for instrumental and methodological variations.",
        score=1.0000,
        generation=1,
        evolved_from=None,
        references=["paper_1", "paper_2"]
    )

    # Generate research plan
    generator = ResearchPlanGenerator()
    research_plan = generator.generate_plan(sample_hypothesis, timeline_weeks=32)

    # Export in different formats
    json_output = generator.export_plan(research_plan, 'json')
    markdown_output = generator.export_plan(research_plan, 'markdown')

    print("=== Research Plan Generator Demo ===")
    print(f"Generated plan for hypothesis: {sample_hypothesis.id}")
    print(f"Total budget: ${research_plan.budget_total:,.2f}")
    print(f"Timeline: {research_plan.timeline_weeks} weeks")
    print(f"Risk count: {len(research_plan.risks)}")
    print(f"Milestone count: {len(research_plan.milestones)}")
    print(f"Resource count: {len(research_plan.resources)}")

    return research_plan, json_output, markdown_output


if __name__ == "__main__":
    # Run demonstration
    plan, json_out, md_out = demo_research_plan_generator()

    # Save outputs to files for inspection
    Path("sample_research_plan.json").write_text(json_out)
    Path("sample_research_plan.md").write_text(md_out)

    print("\nDemo complete. Check sample_research_plan.json and sample_research_plan.md")