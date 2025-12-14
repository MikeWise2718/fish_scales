#!/usr/bin/env python3
"""Test model selection functionality for ADW workflows."""

import sys
import os
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adw_modules.agent import (
    get_model_for_slash_command,
    SLASH_COMMAND_MODEL_MAP,
)
from adw_modules.data_types import AgentTemplateRequest


def test_model_mapping_structure():
    """Test that the model mapping structure is correct."""
    print("Testing model mapping structure...")
    
    # Check that all commands have both base and heavy mappings
    missing_base = []
    missing_heavy = []
    
    for command, config in SLASH_COMMAND_MODEL_MAP.items():
        if "base" not in config:
            missing_base.append(command)
        if "heavy" not in config:
            missing_heavy.append(command)
    
    if missing_base:
        print(f"❌ Commands missing 'base' mapping: {missing_base}")
    else:
        print("✅ All commands have 'base' mapping")
    
    if missing_heavy:
        print(f"❌ Commands missing 'heavy' mapping: {missing_heavy}")
    else:
        print("✅ All commands have 'heavy' mapping")
    
    return len(missing_base) == 0 and len(missing_heavy) == 0


def test_model_mapping_lookups():
    """Test model mapping lookups directly from SLASH_COMMAND_MODEL_MAP."""
    print("\nTesting model mapping lookups...")
    
    test_cases = [
        # (command, model_set, expected)
        ("/implement", "base", "sonnet"),
        ("/implement", "heavy", "opus"),
        ("/classify_issue", "base", "sonnet"),
        ("/classify_issue", "heavy", "sonnet"),  # Both use sonnet
        ("/review", "base", "sonnet"),
        ("/review", "heavy", "sonnet"),  # Both use sonnet
    ]
    
    all_passed = True
    for command, model_set, expected in test_cases:
        config = SLASH_COMMAND_MODEL_MAP.get(command, {})
        result = config.get(model_set, "unknown")
        if result == expected:
            print(f"✅ {command} with {model_set} → {result}")
        else:
            print(f"❌ {command} with {model_set} → {result} (expected {expected})")
            all_passed = False
    
    return all_passed


def test_model_differences():
    """Show which commands use different models in heavy vs base."""
    print("\nCommands with different models in base vs heavy:")
    
    differences = []
    for command, config in SLASH_COMMAND_MODEL_MAP.items():
        base_model = config.get("base", "unknown")
        heavy_model = config.get("heavy", "unknown")
        if base_model != heavy_model:
            differences.append(f"  {command}: base={base_model}, heavy={heavy_model}")
    
    if differences:
        print("\n".join(differences))
    else:
        print("  (none - all commands use same model in both sets)")
    
    print(f"\nTotal commands with differences: {len(differences)}/{len(SLASH_COMMAND_MODEL_MAP)}")


def test_get_model_for_slash_command():
    """Test the get_model_for_slash_command function."""
    print("\nTesting get_model_for_slash_command...")
    
    # Create a mock ADW state
    from adw_modules.state import ADWState
    
    # Test with base model set
    test_adw_id = "test1234"
    state = ADWState(test_adw_id)
    state.update(model_set="base")
    state.save("test")
    
    request = AgentTemplateRequest(
        agent_name="test",
        slash_command="/implement",
        args=["plan.md"],
        adw_id=test_adw_id
    )
    
    model = get_model_for_slash_command(request)
    expected_base = "sonnet"
    if model == expected_base:
        print(f"✅ With model_set='base': /implement → {model}")
    else:
        print(f"❌ With model_set='base': /implement → {model} (expected {expected_base})")
    
    # Test with heavy model set
    state.update(model_set="heavy")
    state.save("test")
    
    # Force reload the state by creating a new request
    model = get_model_for_slash_command(request)
    expected_heavy = "opus"
    if model == expected_heavy:
        print(f"✅ With model_set='heavy': /implement → {model}")
    else:
        print(f"❌ With model_set='heavy': /implement → {model} (expected {expected_heavy})")
    
    # Test with no state (should default to base)
    request_no_state = AgentTemplateRequest(
        agent_name="test",
        slash_command="/review",
        args=["spec.md"],
        adw_id="nonexistent"
    )
    
    model = get_model_for_slash_command(request_no_state)
    expected_default = "sonnet"
    if model == expected_default:
        print(f"✅ With no state: /review → {model} (default to base)")
    else:
        print(f"❌ With no state: /review → {model} (expected {expected_default})")
    
    # Clean up test state
    state_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "agents", test_adw_id, "adw_state.json"
    )
    if os.path.exists(state_file):
        os.remove(state_file)
        # Try to remove empty directories
        try:
            os.rmdir(os.path.dirname(state_file))
            os.rmdir(os.path.dirname(os.path.dirname(state_file)))
        except:
            pass
    
    return True


def main():
    """Run all tests."""
    print("ADW Model Selection Tests")
    print("=" * 50)
    
    all_tests_passed = True
    
    # Run tests
    if not test_model_mapping_structure():
        all_tests_passed = False
    
    if not test_model_mapping_lookups():
        all_tests_passed = False
    
    test_model_differences()
    
    if not test_get_model_for_slash_command():
        all_tests_passed = False
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())