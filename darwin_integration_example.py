#!/usr/bin/env python3
"""
Darwin Integration Example - Research Plan Generator Integration

This module demonstrates how to integrate the Research Plan Generator with Darwin's
actual output to create actionable research plans from AI-generated hypotheses.
"""

import json
from pathlib import Path
from research_plan_generator import (
    ResearchPlanGenerator, HypothesisParser, Hypothesis
)


def darwin_to_research_plan_demo():
    """Demonstrate converting real Darwin output to research plans."""

    # Parse the actual Darwin output we generated earlier
    darwin_output_path = "/tmp/sample_output.txt"

    if not Path(darwin_output_path).exists():
        print(f"Darwin output file not found at {darwin_output_path}")
        return

    # Initialize components
    parser = HypothesisParser()
    generator = ResearchPlanGenerator()

    # Parse Darwin text output
    darwin_text = Path(darwin_output_path).read_text()
    hypotheses = parser.parse_darwin_text(darwin_text)

    print(f"Parsed {len(hypotheses)} hypotheses from Darwin output")

    # Generate research plans for each hypothesis
    research_plans = []
    for i, hypothesis in enumerate(hypotheses):
        print(f"\nGenerating research plan for hypothesis {i+1}/{len(hypotheses)}")
        print(f"Hypothesis: {hypothesis.text[:80]}...")

        # Generate customized timeline based on hypothesis complexity
        timeline_weeks = 32  # Default
        if hypothesis.score > 0.9:
            timeline_weeks = 40  # More time for high-confidence hypotheses
        elif hypothesis.score < 0.7:
            timeline_weeks = 24  # Less time for lower-confidence hypotheses

        plan = generator.generate_plan(hypothesis, timeline_weeks)
        research_plans.append(plan)

        print(f"  - Timeline: {plan.timeline_weeks} weeks")
        print(f"  - Budget: ${plan.budget_total:,.0f}")
        print(f"  - Risks identified: {len(plan.risks)}")
        print(f"  - Resources needed: {len(plan.resources)}")

    # Export all plans
    print(f"\nExporting {len(research_plans)} research plans...")

    for i, plan in enumerate(research_plans):
        # Export as JSON and Markdown
        json_output = generator.export_plan(plan, 'json')
        md_output = generator.export_plan(plan, 'markdown')

        # Save to files
        json_path = f"research_plan_{i+1}.json"
        md_path = f"research_plan_{i+1}.md"

        Path(json_path).write_text(json_output)
        Path(md_path).write_text(md_output)

        print(f"  - Plan {i+1}: {json_path}, {md_path}")

    # Generate summary report
    generate_summary_report(research_plans)

    return research_plans


def generate_summary_report(plans):
    """Generate a summary report comparing all research plans."""

    total_budget = sum(plan.budget_total for plan in plans)
    avg_timeline = sum(plan.timeline_weeks for plan in plans) / len(plans)
    total_risks = sum(len(plan.risks) for plan in plans)

    summary = f"""
# Research Portfolio Summary

## Overview
- **Total Hypotheses**: {len(plans)}
- **Combined Budget**: ${total_budget:,.2f}
- **Average Timeline**: {avg_timeline:.1f} weeks
- **Total Risks Identified**: {total_risks}

## Individual Plans

| Plan | Hypothesis Score | Timeline | Budget | Risk Count |
|------|------------------|----------|---------|------------|
"""

    for i, plan in enumerate(plans, 1):
        summary += f"| {i} | {plan.hypothesis.score:.4f} | {plan.timeline_weeks}w | ${plan.budget_total:,.0f} | {len(plan.risks)} |\n"

    summary += f"""

## Budget Breakdown by Plan
"""

    for i, plan in enumerate(plans, 1):
        summary += f"\n### Plan {i}: {plan.hypothesis.text[:50]}...\n"
        resource_costs = {}
        for resource in plan.resources:
            category = resource.type
            if category not in resource_costs:
                resource_costs[category] = 0
            resource_costs[category] += resource.quantity * resource.unit_cost

        for category, cost in resource_costs.items():
            summary += f"- **{category.title()}**: ${cost:,.2f}\n"

    summary += f"""

## Timeline Coordination

To execute these plans in parallel would require:
- **Peak Budget**: ${max(plan.budget_total for plan in plans):,.2f} (most expensive plan)
- **Sequential Timeline**: {sum(plan.timeline_weeks for plan in plans)} weeks total
- **Parallel Timeline**: {max(plan.timeline_weeks for plan in plans)} weeks (if run simultaneously)

## Resource Conflicts

Equipment sharing opportunities:
"""

    # Find common equipment needs
    all_equipment = {}
    for plan in plans:
        for resource in plan.resources:
            if resource.type == 'equipment':
                if resource.name not in all_equipment:
                    all_equipment[resource.name] = []
                all_equipment[resource.name].append(plan.id)

    for equipment, plan_ids in all_equipment.items():
        if len(plan_ids) > 1:
            summary += f"- **{equipment}**: Needed by {len(plan_ids)} plans (shared resource opportunity)\n"

    summary += f"""

## Risk Summary

Common risk patterns:
- **Technical Risks**: Present in all plans (methodology validation, complexity)
- **Resource Risks**: Equipment availability and personnel
- **Timeline Risks**: Experimental delays and scope creep

## Recommendations

1. **Portfolio Approach**: Execute highest-scoring hypotheses first
2. **Resource Sharing**: Coordinate equipment usage across plans
3. **Risk Mitigation**: Implement common risk management strategies
4. **Phased Execution**: Stagger plan starts to optimize resource utilization

---
*Generated by Darwin Research Plan Generator Integration*
"""

    Path("research_portfolio_summary.md").write_text(summary)
    print(f"Portfolio summary saved to: research_portfolio_summary.md")


def create_project_management_export(plans):
    """Create project management system compatible export."""

    # Create Gantt chart compatible JSON
    gantt_data = {
        "projects": [],
        "tasks": [],
        "dependencies": []
    }

    for i, plan in enumerate(plans):
        project_id = f"proj_{i+1}"
        gantt_data["projects"].append({
            "id": project_id,
            "name": f"Hypothesis {plan.hypothesis.id}",
            "description": plan.hypothesis.text[:100] + "...",
            "start_date": plan.created_date.isoformat(),
            "duration_weeks": plan.timeline_weeks,
            "budget": plan.budget_total
        })

        # Add milestones as tasks
        for milestone in plan.milestones:
            task_id = f"{project_id}_{milestone.id}"
            gantt_data["tasks"].append({
                "id": task_id,
                "project_id": project_id,
                "name": milestone.name,
                "description": milestone.description,
                "due_date": milestone.due_date.isoformat(),
                "deliverables": milestone.deliverables,
                "phase": milestone.phase
            })

            # Add dependencies
            for dep in milestone.dependencies:
                dep_task_id = f"{project_id}_{dep}"
                gantt_data["dependencies"].append({
                    "predecessor": dep_task_id,
                    "successor": task_id,
                    "type": "finish_to_start"
                })

    # Save project management export
    pm_export = json.dumps(gantt_data, indent=2)
    Path("research_plans_project_management.json").write_text(pm_export)
    print("Project management export saved to: research_plans_project_management.json")

    return gantt_data


if __name__ == "__main__":
    print("=== Darwin to Research Plan Integration Demo ===")

    try:
        plans = darwin_to_research_plan_demo()
        if plans:
            print(f"\n✓ Successfully generated {len(plans)} research plans")

            # Create additional exports
            create_project_management_export(plans)

            print("\nGenerated files:")
            for f in Path(".").glob("research_plan_*.md"):
                print(f"  - {f}")
            for f in Path(".").glob("research_plan_*.json"):
                print(f"  - {f}")
            print(f"  - research_portfolio_summary.md")
            print(f"  - research_plans_project_management.json")

            print("\n✓ Integration demo complete!")
        else:
            print("❌ No plans generated - check Darwin output file")

    except Exception as e:
        print(f"❌ Error in integration demo: {e}")
        import traceback
        traceback.print_exc()