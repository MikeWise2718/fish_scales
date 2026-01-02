"""Tests for gradient-based parameter optimizer."""

import pytest
from unittest.mock import Mock, patch

from fish_scale_ui.services.optimizer import (
    GradientOptimizer,
    PARAMETERS,
    DEFAULT_ENABLED,
    run_optimize_step,
)


class TestParameterDefinitions:
    """Tests for parameter definitions."""

    def test_all_parameters_have_required_fields(self):
        """Verify all parameters have min, max, step, lr, is_int."""
        for name, bounds in PARAMETERS.items():
            assert 'min' in bounds, f"{name} missing 'min'"
            assert 'max' in bounds, f"{name} missing 'max'"
            assert 'step' in bounds, f"{name} missing 'step'"
            assert 'lr' in bounds, f"{name} missing 'lr'"
            assert 'is_int' in bounds, f"{name} missing 'is_int'"

    def test_parameter_bounds_are_valid(self):
        """Verify min < max for all parameters."""
        for name, bounds in PARAMETERS.items():
            assert bounds['min'] < bounds['max'], f"{name} has invalid bounds"

    def test_step_sizes_are_positive(self):
        """Verify step sizes are positive."""
        for name, bounds in PARAMETERS.items():
            assert bounds['step'] > 0, f"{name} has non-positive step"

    def test_learning_rates_are_positive(self):
        """Verify learning rates are positive."""
        for name, bounds in PARAMETERS.items():
            assert bounds['lr'] > 0, f"{name} has non-positive learning rate"

    def test_default_enabled_are_valid_params(self):
        """Verify default enabled params are valid."""
        for param in DEFAULT_ENABLED:
            assert param in PARAMETERS, f"Default param {param} not in PARAMETERS"


class TestGradientOptimizerInit:
    """Tests for GradientOptimizer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
        )
        assert optimizer.image_path == '/test/image.png'
        assert optimizer.um_per_px == 0.5
        assert optimizer.enabled_params == DEFAULT_ENABLED
        assert optimizer.max_workers == 4

    def test_init_with_custom_enabled_params(self):
        """Test initialization with custom enabled parameters."""
        enabled = ['threshold', 'blur_sigma']
        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=enabled,
        )
        assert optimizer.enabled_params == enabled

    def test_init_with_invalid_param_raises(self):
        """Test that invalid parameter raises ValueError."""
        with pytest.raises(ValueError, match="Unknown parameter"):
            GradientOptimizer(
                image_path='/test/image.png',
                um_per_px=0.5,
                enabled_params=['invalid_param'],
            )


class TestClamping:
    """Tests for parameter clamping."""

    def test_clamp_within_bounds(self):
        """Test that values within bounds are unchanged."""
        optimizer = GradientOptimizer('/test/image.png', 0.5)

        # Threshold is 0.01-0.50
        result = optimizer._clamp('threshold', 0.25)
        assert result == 0.25

    def test_clamp_below_min(self):
        """Test that values below min are clamped to min."""
        optimizer = GradientOptimizer('/test/image.png', 0.5)

        # Threshold min is 0.01
        result = optimizer._clamp('threshold', -0.5)
        assert result == 0.01

    def test_clamp_above_max(self):
        """Test that values above max are clamped to max."""
        optimizer = GradientOptimizer('/test/image.png', 0.5)

        # Threshold max is 0.50
        result = optimizer._clamp('threshold', 1.0)
        assert result == 0.50

    def test_clamp_integer_param(self):
        """Test that integer params are rounded."""
        optimizer = GradientOptimizer('/test/image.png', 0.5)

        # clahe_kernel is integer
        result = optimizer._clamp('clahe_kernel', 8.7)
        assert result == 9
        assert isinstance(result, int)


class TestConvergenceCheck:
    """Tests for convergence checking."""

    def test_converged_small_delta(self):
        """Test convergence when delta is small."""
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.70,
            new_score=0.7005,
            iteration=5,
            delta_threshold=0.001,
        )
        assert should_stop is True
        assert reason == 'converged'

    def test_converged_target_reached(self):
        """Test convergence when target score is reached."""
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.80,
            new_score=0.86,
            iteration=5,
            target_score=0.85,
        )
        assert should_stop is True
        assert reason == 'target_reached'

    def test_converged_max_iterations(self):
        """Test convergence at max iterations."""
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.50,
            new_score=0.55,
            iteration=20,
            max_iterations=20,
        )
        assert should_stop is True
        assert reason == 'max_iterations'

    def test_not_converged(self):
        """Test when not yet converged."""
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.50,
            new_score=0.55,
            iteration=5,
            delta_threshold=0.001,
            max_iterations=20,
            target_score=0.85,
        )
        assert should_stop is False
        assert reason == ''

    def test_no_convergence_on_first_iteration(self):
        """Test that small delta on iteration 1 does NOT converge."""
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.50,
            new_score=0.50,  # Zero delta
            iteration=1,
            delta_threshold=0.001,
            max_iterations=20,
        )
        assert should_stop is False
        assert reason == ''

    def test_convergence_respects_min_iterations(self):
        """Test that convergence requires min_iterations."""
        # At iteration 1 with custom min_iterations=3, should not converge
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.70,
            new_score=0.70,
            iteration=2,
            delta_threshold=0.001,
            min_iterations=3,
        )
        assert should_stop is False

        # At iteration 3 with min_iterations=3, should converge
        should_stop, reason = GradientOptimizer.check_convergence(
            prev_score=0.70,
            new_score=0.70,
            iteration=3,
            delta_threshold=0.001,
            min_iterations=3,
        )
        assert should_stop is True
        assert reason == 'converged'


class TestGradientEstimation:
    """Tests for gradient estimation with mocked extraction."""

    @patch.object(GradientOptimizer, '_get_hexagonalness')
    def test_gradient_direction(self, mock_hex):
        """Test that gradient points in correct direction."""
        # Setup: increasing threshold increases score
        def mock_extraction(params):
            # Simple mock: higher threshold = higher score
            return 0.5 + params.get('threshold', 0.05) * 0.5

        mock_hex.side_effect = mock_extraction

        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=['threshold'],
        )

        params = {'threshold': 0.1}
        gradient, count = optimizer.estimate_gradient(params)

        # Gradient should be positive (increasing threshold helps)
        assert 'threshold' in gradient
        assert gradient['threshold'] > 0

    @patch.object(GradientOptimizer, '_get_hexagonalness')
    def test_gradient_extractions_count(self, mock_hex):
        """Test that correct number of extractions are performed."""
        mock_hex.return_value = 0.5

        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=['threshold', 'blur_sigma'],
        )

        params = {'threshold': 0.1, 'blur_sigma': 1.0}
        gradient, count = optimizer.estimate_gradient(params)

        # 2 params * 2 (plus and minus) = 4 extractions
        assert count == 4
        assert mock_hex.call_count == 4


class TestStep:
    """Tests for optimization step with mocked extraction."""

    @patch.object(GradientOptimizer, '_run_extraction')
    @patch.object(GradientOptimizer, 'estimate_gradient')
    def test_step_updates_params(self, mock_gradient, mock_extract):
        """Test that step updates parameters correctly."""
        # Mock gradient: positive for threshold
        mock_gradient.return_value = ({'threshold': 10.0}, 2)

        # Mock extraction result
        mock_extract.return_value = {
            'statistics': {'hexagonalness_score': 0.6},
            'tubercles': [],
            'edges': [],
        }

        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=['threshold'],
        )

        params = {'threshold': 0.1}
        result = optimizer.step(params)

        assert result['success'] is True
        assert 'new_params' in result
        # With lr=0.005 and gradient=10, new_threshold = 0.1 + 0.005*10 = 0.15
        assert result['new_params']['threshold'] == pytest.approx(0.15, abs=0.001)

    @patch.object(GradientOptimizer, '_run_extraction')
    @patch.object(GradientOptimizer, 'estimate_gradient')
    def test_step_respects_bounds(self, mock_gradient, mock_extract):
        """Test that step respects parameter bounds."""
        # Mock gradient: very large positive value
        mock_gradient.return_value = ({'threshold': 1000.0}, 2)

        mock_extract.return_value = {
            'statistics': {'hexagonalness_score': 0.6},
            'tubercles': [],
            'edges': [],
        }

        optimizer = GradientOptimizer(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=['threshold'],
        )

        params = {'threshold': 0.4}  # Close to max of 0.50
        result = optimizer.step(params)

        # Should be clamped to max
        assert result['new_params']['threshold'] <= 0.50


class TestRunOptimizeStep:
    """Tests for convenience function."""

    @patch('fish_scale_ui.services.optimizer.GradientOptimizer')
    def test_run_optimize_step_creates_optimizer(self, MockOptimizer):
        """Test that convenience function creates optimizer correctly."""
        mock_instance = Mock()
        mock_instance.step.return_value = {'success': True}
        MockOptimizer.return_value = mock_instance

        result = run_optimize_step(
            image_path='/test/image.png',
            um_per_px=0.5,
            params={'threshold': 0.1},
            enabled_params=['threshold'],
        )

        MockOptimizer.assert_called_once_with(
            image_path='/test/image.png',
            um_per_px=0.5,
            enabled_params=['threshold'],
        )
        mock_instance.step.assert_called_once()
