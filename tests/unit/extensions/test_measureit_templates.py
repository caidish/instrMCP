"""
Unit tests for MeasureIt template generation.

Tests template generation for Sweep0D, Sweep1D, Sweep2D, SimulSweep,
SweepQueue, common patterns, and comprehensive code examples.
"""

import json
from instrmcp.extensions.MeasureIt.measureit_templates import (
    get_sweep0d_template,
    get_sweep1d_template,
    get_sweep2d_template,
    get_simulsweep_template,
    get_sweepqueue_template,
    get_common_patterns_template,
    get_measureit_code_examples,
)


class TestSweep0DTemplate:
    """Test Sweep0D template generation."""

    def test_sweep0d_returns_valid_json(self):
        """Test Sweep0D template returns valid JSON."""
        template = get_sweep0d_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_sweep0d_contains_required_fields(self):
        """Test Sweep0D template has all required fields."""
        template = json.loads(get_sweep0d_template())
        assert "description" in template
        assert "use_cases" in template
        assert "basic_pattern" in template
        assert "common_parameters" in template
        assert "tips" in template

    def test_sweep0d_description(self):
        """Test Sweep0D has correct description."""
        template = json.loads(get_sweep0d_template())
        assert "time" in template["description"].lower()
        assert "sweep0d" in template["description"].lower()

    def test_sweep0d_use_cases(self):
        """Test Sweep0D includes expected use cases."""
        template = json.loads(get_sweep0d_template())
        use_cases = template["use_cases"]
        assert isinstance(use_cases, list)
        assert len(use_cases) > 0
        assert any("monitor" in case.lower() for case in use_cases)

    def test_sweep0d_basic_pattern_is_code(self):
        """Test Sweep0D basic pattern contains executable code."""
        template = json.loads(get_sweep0d_template())
        code = template["basic_pattern"]
        assert "from measureit import Sweep0D" in code
        assert "s = Sweep0D(" in code
        assert "s.follow_param(" in code
        assert "init_database" in code
        assert "s.start()" in code

    def test_sweep0d_common_parameters(self):
        """Test Sweep0D includes key parameters."""
        template = json.loads(get_sweep0d_template())
        params = template["common_parameters"]
        assert "inter_delay" in params
        assert "save_data" in params
        assert "plot_bin" in params
        assert "max_time" in params

    def test_sweep0d_tips(self):
        """Test Sweep0D includes helpful tips."""
        template = json.loads(get_sweep0d_template())
        tips = template["tips"]
        assert isinstance(tips, list)
        assert len(tips) > 0
        assert any("ESC" in tip for tip in tips)


class TestSweep1DTemplate:
    """Test Sweep1D template generation."""

    def test_sweep1d_returns_valid_json(self):
        """Test Sweep1D template returns valid JSON."""
        template = get_sweep1d_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_sweep1d_contains_required_fields(self):
        """Test Sweep1D template has all required fields."""
        template = json.loads(get_sweep1d_template())
        assert "description" in template
        assert "use_cases" in template
        assert "basic_pattern" in template
        assert "advanced_patterns" in template
        assert "common_parameters" in template
        assert "tips" in template

    def test_sweep1d_description(self):
        """Test Sweep1D has correct description."""
        template = json.loads(get_sweep1d_template())
        assert "sweep1d" in template["description"].lower()
        assert "one parameter" in template["description"].lower()

    def test_sweep1d_use_cases(self):
        """Test Sweep1D includes expected use cases."""
        template = json.loads(get_sweep1d_template())
        use_cases = template["use_cases"]
        assert len(use_cases) > 0
        use_cases_str = " ".join(use_cases).lower()
        assert any(term in use_cases_str for term in ["gate", "voltage", "sweep"])

    def test_sweep1d_basic_pattern_is_code(self):
        """Test Sweep1D basic pattern contains executable code."""
        template = json.loads(get_sweep1d_template())
        code = template["basic_pattern"]
        assert "from measureit import Sweep1D" in code
        assert "s = Sweep1D(" in code
        assert "start=" in code
        assert "stop=" in code
        assert "step=" in code
        assert "s.start()" in code

    def test_sweep1d_advanced_patterns(self):
        """Test Sweep1D includes advanced patterns."""
        template = json.loads(get_sweep1d_template())
        advanced = template["advanced_patterns"]
        assert isinstance(advanced, dict)
        assert len(advanced) > 0
        # Check for specific advanced patterns
        assert any(
            "fast" in key.lower()
            or "temperature" in key.lower()
            or "continual" in key.lower()
            for key in advanced.keys()
        )

    def test_sweep1d_common_parameters(self):
        """Test Sweep1D includes key parameters."""
        template = json.loads(get_sweep1d_template())
        params = template["common_parameters"]
        assert "start" in params
        assert "stop" in params
        assert "step" in params
        assert "bidirectional" in params

    def test_sweep1d_tips_include_safety(self):
        """Test Sweep1D tips include safety considerations."""
        template = json.loads(get_sweep1d_template())
        tips = template["tips"]
        tips_str = " ".join(tips).lower()
        assert any(term in tips_str for term in ["safely", "rate", "ramp"])


class TestSweep2DTemplate:
    """Test Sweep2D template generation."""

    def test_sweep2d_returns_valid_json(self):
        """Test Sweep2D template returns valid JSON."""
        template = get_sweep2d_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_sweep2d_contains_required_fields(self):
        """Test Sweep2D template has all required fields."""
        template = json.loads(get_sweep2d_template())
        assert "description" in template
        assert "use_cases" in template
        assert "basic_pattern" in template
        assert "advanced_patterns" in template
        assert "common_parameters" in template
        assert "tips" in template

    def test_sweep2d_description(self):
        """Test Sweep2D has correct description."""
        template = json.loads(get_sweep2d_template())
        assert "sweep2d" in template["description"].lower()
        assert "2d" in template["description"].lower()

    def test_sweep2d_use_cases(self):
        """Test Sweep2D includes expected use cases."""
        template = json.loads(get_sweep2d_template())
        use_cases = template["use_cases"]
        assert len(use_cases) > 0
        use_cases_str = " ".join(use_cases).lower()
        assert any(term in use_cases_str for term in ["map", "2d", "stability"])

    def test_sweep2d_basic_pattern_is_code(self):
        """Test Sweep2D basic pattern contains executable code."""
        template = json.loads(get_sweep2d_template())
        code = template["basic_pattern"]
        assert "from measureit import Sweep2D" in code
        assert "s = Sweep2D(" in code
        assert "inner_param" in code
        assert "outer_param" in code
        assert "follow_heatmap_param" in code
        assert "s.start()" in code

    def test_sweep2d_advanced_patterns(self):
        """Test Sweep2D includes advanced patterns."""
        template = json.loads(get_sweep2d_template())
        advanced = template["advanced_patterns"]
        assert isinstance(advanced, dict)
        assert len(advanced) >= 2
        # Should include various mapping strategies
        for pattern_code in advanced.values():
            assert "Sweep2D" in pattern_code

    def test_sweep2d_common_parameters(self):
        """Test Sweep2D includes key parameters."""
        template = json.loads(get_sweep2d_template())
        params = template["common_parameters"]
        assert "inner_param" in params
        assert "outer_param" in params
        assert "inter_delay" in params
        assert "outer_delay" in params
        assert "back_multiplier" in params

    def test_sweep2d_tips_include_performance(self):
        """Test Sweep2D tips include performance considerations."""
        template = json.loads(get_sweep2d_template())
        tips = template["tips"]
        tips_str = " ".join(tips).lower()
        assert any(term in tips_str for term in ["inner", "outer", "back_multiplier"])


class TestSimulSweepTemplate:
    """Test SimulSweep template generation."""

    def test_simulsweep_returns_valid_json(self):
        """Test SimulSweep template returns valid JSON."""
        template = get_simulsweep_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_simulsweep_contains_required_fields(self):
        """Test SimulSweep template has all required fields."""
        template = json.loads(get_simulsweep_template())
        assert "description" in template
        assert "use_cases" in template
        assert "basic_pattern" in template
        assert "advanced_patterns" in template
        assert "common_parameters" in template
        assert "tips" in template

    def test_simulsweep_description(self):
        """Test SimulSweep has correct description."""
        template = json.loads(get_simulsweep_template())
        assert "simulsweep" in template["description"].lower()
        assert "simultaneous" in template["description"].lower()

    def test_simulsweep_basic_pattern_is_code(self):
        """Test SimulSweep basic pattern contains executable code."""
        template = json.loads(get_simulsweep_template())
        code = template["basic_pattern"]
        assert "from measureit import SimulSweep" in code
        assert "parameter_dict" in code
        assert "SimulSweep(parameter_dict" in code
        assert "start" in code
        assert "stop" in code
        assert "step" in code

    def test_simulsweep_advanced_patterns(self):
        """Test SimulSweep includes advanced patterns."""
        template = json.loads(get_simulsweep_template())
        advanced = template["advanced_patterns"]
        assert isinstance(advanced, dict)
        assert len(advanced) >= 2
        # Check for multi-parameter examples
        for pattern_code in advanced.values():
            assert "SimulSweep" in pattern_code
            assert "parameter_dict" in pattern_code

    def test_simulsweep_common_parameters(self):
        """Test SimulSweep includes key parameters."""
        template = json.loads(get_simulsweep_template())
        params = template["common_parameters"]
        assert "parameter_dict" in params
        assert "bidirectional" in params

    def test_simulsweep_tips_mention_step_coordination(self):
        """Test SimulSweep tips mention step coordination."""
        template = json.loads(get_simulsweep_template())
        tips = template["tips"]
        tips_str = " ".join(tips).lower()
        assert any(term in tips_str for term in ["steps", "simultaneous", "same"])


class TestSweepQueueTemplate:
    """Test SweepQueue template generation."""

    def test_sweepqueue_returns_valid_json(self):
        """Test SweepQueue template returns valid JSON."""
        template = get_sweepqueue_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_sweepqueue_contains_required_fields(self):
        """Test SweepQueue template has all required fields."""
        template = json.loads(get_sweepqueue_template())
        assert "description" in template
        assert "use_cases" in template
        assert "basic_pattern" in template
        assert "advanced_patterns" in template
        assert "common_patterns" in template
        assert "tips" in template

    def test_sweepqueue_description(self):
        """Test SweepQueue has correct description."""
        template = json.loads(get_sweepqueue_template())
        assert "sweepqueue" in template["description"].lower()
        assert (
            "chain" in template["description"].lower()
            or "sequential" in template["description"].lower()
        )

    def test_sweepqueue_basic_pattern_is_code(self):
        """Test SweepQueue basic pattern contains executable code."""
        template = json.loads(get_sweepqueue_template())
        code = template["basic_pattern"]
        assert "from measureit.tools.sweep_queue import SweepQueue" in code
        assert "DatabaseEntry" in code
        assert "sq = SweepQueue()" in code
        assert "sq +=" in code
        assert "sq.start()" in code

    def test_sweepqueue_advanced_patterns(self):
        """Test SweepQueue includes advanced patterns."""
        template = json.loads(get_sweepqueue_template())
        advanced = template["advanced_patterns"]
        assert isinstance(advanced, dict)
        assert len(advanced) >= 2
        # Should include workflow examples
        for pattern_code in advanced.values():
            assert "SweepQueue" in pattern_code

    def test_sweepqueue_common_patterns(self):
        """Test SweepQueue includes common patterns."""
        template = json.loads(get_sweepqueue_template())
        common = template["common_patterns"]
        assert "adding_sweeps" in common
        assert "adding_functions" in common
        assert "database_entry" in common

    def test_sweepqueue_tips_mention_workflow(self):
        """Test SweepQueue tips mention workflow operations."""
        template = json.loads(get_sweepqueue_template())
        tips = template["tips"]
        tips_str = " ".join(tips).lower()
        assert any(term in tips_str for term in ["queue", "functions", "sequential"])


class TestCommonPatternsTemplate:
    """Test common patterns template generation."""

    def test_common_patterns_returns_valid_json(self):
        """Test common patterns template returns valid JSON."""
        template = get_common_patterns_template()
        parsed = json.loads(template)
        assert isinstance(parsed, dict)

    def test_common_patterns_contains_sections(self):
        """Test common patterns template has major sections."""
        template = json.loads(get_common_patterns_template())
        assert "description" in template
        assert "database_setup" in template
        assert "parameter_following" in template
        assert "plotting_setup" in template
        assert "safety_patterns" in template
        assert "error_handling" in template
        assert "optimization_tips" in template
        assert "troubleshooting" in template

    def test_database_setup_patterns(self):
        """Test database setup includes multiple patterns."""
        template = json.loads(get_common_patterns_template())
        db_setup = template["database_setup"]
        assert "basic" in db_setup
        assert "with_path" in db_setup
        assert "init_database" in db_setup["basic"]

    def test_parameter_following_patterns(self):
        """Test parameter following includes patterns."""
        template = json.loads(get_common_patterns_template())
        param_following = template["parameter_following"]
        assert "basic" in param_following
        assert "follow_param" in param_following["basic"]

    def test_safety_patterns_exist(self):
        """Test safety patterns are included."""
        template = json.loads(get_common_patterns_template())
        safety = template["safety_patterns"]
        assert isinstance(safety, dict)
        assert len(safety) > 0

    def test_error_handling_patterns(self):
        """Test error handling patterns are included."""
        template = json.loads(get_common_patterns_template())
        error_handling = template["error_handling"]
        assert "basic" in error_handling
        assert "try:" in error_handling["basic"]

    def test_optimization_tips_is_list(self):
        """Test optimization tips is a list of strings."""
        template = json.loads(get_common_patterns_template())
        tips = template["optimization_tips"]
        assert isinstance(tips, list)
        assert len(tips) > 0
        assert all(isinstance(tip, str) for tip in tips)

    def test_troubleshooting_section(self):
        """Test troubleshooting section exists."""
        template = json.loads(get_common_patterns_template())
        troubleshooting = template["troubleshooting"]
        assert isinstance(troubleshooting, dict)
        assert len(troubleshooting) > 0


class TestMeasureItCodeExamples:
    """Test comprehensive MeasureIt code examples."""

    def test_code_examples_returns_valid_json(self):
        """Test code examples returns valid JSON."""
        examples = get_measureit_code_examples()
        parsed = json.loads(examples)
        assert isinstance(parsed, dict)

    def test_code_examples_has_metadata(self):
        """Test code examples include metadata."""
        examples = json.loads(get_measureit_code_examples())
        assert "description" in examples
        assert "version" in examples
        assert "categories" in examples
        assert "quick_reference" in examples
        assert "measurement_selection_guide" in examples

    def test_code_examples_categories_complete(self):
        """Test all sweep types are included in categories."""
        examples = json.loads(get_measureit_code_examples())
        categories = examples["categories"]
        assert "sweep0d" in categories
        assert "sweep1d" in categories
        assert "sweep2d" in categories
        assert "simulsweep" in categories
        assert "sweepqueue" in categories
        assert "common_patterns" in categories

    def test_each_category_has_template(self):
        """Test each category includes a template."""
        examples = json.loads(get_measureit_code_examples())
        categories = examples["categories"]
        for category_name, category_data in categories.items():
            assert "description" in category_data
            assert "template" in category_data
            assert isinstance(category_data["template"], dict)

    def test_quick_reference_sections(self):
        """Test quick reference includes essential sections."""
        examples = json.loads(get_measureit_code_examples())
        quick_ref = examples["quick_reference"]
        assert "basic_imports" in quick_ref
        assert "database_setup" in quick_ref
        assert "parameter_following" in quick_ref
        assert "plotting_setup" in quick_ref

    def test_quick_reference_code_snippets(self):
        """Test quick reference contains executable code."""
        examples = json.loads(get_measureit_code_examples())
        quick_ref = examples["quick_reference"]
        assert "import" in quick_ref["basic_imports"]
        assert "MeasureIt" in quick_ref["basic_imports"]

    def test_measurement_selection_guide(self):
        """Test measurement selection guide covers all sweep types."""
        examples = json.loads(get_measureit_code_examples())
        guide = examples["measurement_selection_guide"]
        assert "sweep0d" in guide
        assert "sweep1d" in guide
        assert "sweep2d" in guide
        assert "simulsweep" in guide
        assert "sweepqueue" in guide

    def test_measurement_guide_structure(self):
        """Test each measurement guide entry has proper structure."""
        examples = json.loads(get_measureit_code_examples())
        guide = examples["measurement_selection_guide"]
        for sweep_type, info in guide.items():
            assert "when_to_use" in info
            assert "examples" in info
            assert "key_parameters" in info
            assert isinstance(info["examples"], list)

    def test_code_generation_hints_exist(self):
        """Test code generation hints are included."""
        examples = json.loads(get_measureit_code_examples())
        assert "code_generation_hints" in examples
        hints = examples["code_generation_hints"]
        assert "ai_instructions" in hints
        assert "safety_guidelines" in hints
        assert "performance_tips" in hints

    def test_ai_instructions_is_list(self):
        """Test AI instructions is a list of actionable items."""
        examples = json.loads(get_measureit_code_examples())
        instructions = examples["code_generation_hints"]["ai_instructions"]
        assert isinstance(instructions, list)
        assert len(instructions) > 0
        assert all(isinstance(item, str) for item in instructions)

    def test_safety_guidelines_is_list(self):
        """Test safety guidelines is a list of safety practices."""
        examples = json.loads(get_measureit_code_examples())
        guidelines = examples["code_generation_hints"]["safety_guidelines"]
        assert isinstance(guidelines, list)
        assert len(guidelines) > 0
        guidelines_str = " ".join(guidelines).lower()
        assert any(term in guidelines_str for term in ["safe", "limit", "rate"])

    def test_performance_tips_is_list(self):
        """Test performance tips is a list of optimization advice."""
        examples = json.loads(get_measureit_code_examples())
        tips = examples["code_generation_hints"]["performance_tips"]
        assert isinstance(tips, list)
        assert len(tips) > 0


class TestTemplateIntegration:
    """Test integration and consistency across templates."""

    def test_all_templates_parse_as_json(self):
        """Test all template functions return valid JSON."""
        templates = [
            get_sweep0d_template(),
            get_sweep1d_template(),
            get_sweep2d_template(),
            get_simulsweep_template(),
            get_sweepqueue_template(),
            get_common_patterns_template(),
            get_measureit_code_examples(),
        ]
        for template in templates:
            parsed = json.loads(template)
            assert isinstance(parsed, dict)

    def test_all_basic_templates_have_description(self):
        """Test all basic templates include description field."""
        templates = [
            get_sweep0d_template(),
            get_sweep1d_template(),
            get_sweep2d_template(),
            get_simulsweep_template(),
            get_sweepqueue_template(),
            get_common_patterns_template(),
        ]
        for template_str in templates:
            template = json.loads(template_str)
            assert "description" in template
            assert isinstance(template["description"], str)
            assert len(template["description"]) > 0

    def test_all_sweep_templates_have_basic_pattern(self):
        """Test all sweep templates include basic pattern."""
        templates = [
            get_sweep0d_template(),
            get_sweep1d_template(),
            get_sweep2d_template(),
            get_simulsweep_template(),
            get_sweepqueue_template(),
        ]
        for template_str in templates:
            template = json.loads(template_str)
            assert "basic_pattern" in template
            code = template["basic_pattern"]
            assert "import" in code
            assert "start()" in code

    def test_code_examples_includes_all_individual_templates(self):
        """Test comprehensive examples include all individual template data."""
        all_examples = json.loads(get_measureit_code_examples())
        categories = all_examples["categories"]

        # Verify individual templates match categories
        sweep0d = json.loads(get_sweep0d_template())
        assert (
            categories["sweep0d"]["template"]["description"] == sweep0d["description"]
        )

        sweep1d = json.loads(get_sweep1d_template())
        assert (
            categories["sweep1d"]["template"]["description"] == sweep1d["description"]
        )

    def test_no_template_contains_placeholder_text(self):
        """Test templates don't contain obvious placeholder text."""
        templates = [
            get_sweep0d_template(),
            get_sweep1d_template(),
            get_sweep2d_template(),
            get_simulsweep_template(),
            get_sweepqueue_template(),
            get_common_patterns_template(),
            get_measureit_code_examples(),
        ]
        forbidden_terms = ["TODO", "FIXME", "placeholder", "XXX", "TBD"]
        for template_str in templates:
            template_lower = template_str.lower()
            for term in forbidden_terms:
                assert (
                    term.lower() not in template_lower
                ), f"Found placeholder '{term}' in template"
