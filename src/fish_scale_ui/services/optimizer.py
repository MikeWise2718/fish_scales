"""Gradient-based parameter optimizer for hexagonalness maximization."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .extraction import run_extraction


# Parameter definitions with bounds, step sizes, and learning rates
PARAMETERS = {
    'threshold': {
        'min': 0.01,
        'max': 0.50,
        'step': 0.01,
        'lr': 0.005,
        'is_int': False,
    },
    'min_diameter_um': {
        'min': 0.5,
        'max': 20.0,
        'step': 0.5,
        'lr': 0.25,
        'is_int': False,
    },
    'max_diameter_um': {
        'min': 1.0,
        'max': 50.0,
        'step': 1.0,
        'lr': 0.5,
        'is_int': False,
    },
    'min_circularity': {
        'min': 0.0,
        'max': 1.0,
        'step': 0.05,
        'lr': 0.025,
        'is_int': False,
    },
    'clahe_clip': {
        'min': 0.01,
        'max': 0.20,
        'step': 0.01,
        'lr': 0.005,
        'is_int': False,
    },
    'clahe_kernel': {
        'min': 4,
        'max': 32,
        'step': 2,
        'lr': 1.0,
        'is_int': True,
    },
    'blur_sigma': {
        'min': 0.0,
        'max': 5.0,
        'step': 0.2,
        'lr': 0.1,
        'is_int': False,
    },
}

# Default parameters to optimize (most impactful)
DEFAULT_ENABLED = ['threshold', 'min_circularity', 'blur_sigma']


class GradientOptimizer:
    """Gradient-based parameter optimizer for hexagonalness maximization.

    Uses central finite differences to estimate gradients and performs
    gradient ascent to maximize the hexagonalness score.
    """

    def __init__(
        self,
        image_path: str,
        um_per_px: float,
        enabled_params: Optional[list] = None,
        max_workers: int = 4,
    ):
        """Initialize the optimizer.

        Args:
            image_path: Path to the image file
            um_per_px: Calibration in micrometers per pixel
            enabled_params: List of parameter names to optimize (default: threshold, min_circularity, blur_sigma)
            max_workers: Maximum number of parallel extraction workers
        """
        self.image_path = image_path
        self.um_per_px = um_per_px
        self.enabled_params = enabled_params or DEFAULT_ENABLED.copy()
        self.max_workers = max_workers

        # Validate enabled params
        for param in self.enabled_params:
            if param not in PARAMETERS:
                raise ValueError(f"Unknown parameter: {param}")

    def _run_extraction(self, params: dict) -> dict:
        """Run extraction with given parameters.

        Args:
            params: Dictionary of extraction parameters

        Returns:
            Full extraction result dictionary
        """
        return run_extraction(
            image_path=self.image_path,
            um_per_px=self.um_per_px,
            method=params.get('method', 'log'),
            threshold=params.get('threshold', 0.05),
            min_diameter_um=params.get('min_diameter_um', 2.0),
            max_diameter_um=params.get('max_diameter_um', 10.0),
            min_circularity=params.get('min_circularity', 0.5),
            clahe_clip=params.get('clahe_clip', 0.03),
            clahe_kernel=params.get('clahe_kernel', 8),
            blur_sigma=params.get('blur_sigma', 1.0),
            neighbor_graph=params.get('neighbor_graph', 'delaunay'),
            cull_long_edges=params.get('cull_long_edges', True),
            cull_factor=params.get('cull_factor', 1.8),
        )

    def _get_hexagonalness(self, params: dict) -> float:
        """Run extraction and return hexagonalness score.

        Args:
            params: Dictionary of extraction parameters

        Returns:
            Hexagonalness score (0-1)
        """
        result = self._run_extraction(params)
        return result['statistics']['hexagonalness_score']

    def _clamp(self, param_name: str, value: float) -> float:
        """Clamp a parameter value to its valid range.

        Args:
            param_name: Name of the parameter
            value: Value to clamp

        Returns:
            Clamped value
        """
        bounds = PARAMETERS[param_name]
        clamped = max(bounds['min'], min(bounds['max'], value))

        if bounds['is_int']:
            clamped = int(round(clamped))

        return clamped

    def estimate_gradient(
        self,
        params: dict,
        progress_callback: Optional[callable] = None,
    ) -> tuple[dict, int]:
        """Estimate gradient using central finite differences.

        For each enabled parameter i:
            gradient[i] = (H(params + delta*e_i) - H(params - delta*e_i)) / (2*delta)

        Args:
            params: Current parameter values
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            Tuple of (gradient dict, number of extractions performed)
        """
        gradient = {}
        total_extractions = len(self.enabled_params) * 2
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            # Submit all +delta and -delta extraction jobs
            for param_name in self.enabled_params:
                delta = PARAMETERS[param_name]['step']

                # Create params with +delta
                params_plus = params.copy()
                params_plus[param_name] = self._clamp(
                    param_name,
                    params[param_name] + delta
                )

                # Create params with -delta
                params_minus = params.copy()
                params_minus[param_name] = self._clamp(
                    param_name,
                    params[param_name] - delta
                )

                # Submit jobs
                futures[f'{param_name}_plus'] = executor.submit(
                    self._get_hexagonalness, params_plus
                )
                futures[f'{param_name}_minus'] = executor.submit(
                    self._get_hexagonalness, params_minus
                )

            # Collect results as they complete
            results = {}
            for future in as_completed(futures.values()):
                completed += 1
                if progress_callback:
                    progress_callback(completed, total_extractions)

            # Get all results
            for key, future in futures.items():
                results[key] = future.result()

            # Calculate gradients
            for param_name in self.enabled_params:
                delta = PARAMETERS[param_name]['step']
                score_plus = results[f'{param_name}_plus']
                score_minus = results[f'{param_name}_minus']

                # Central difference gradient
                gradient[param_name] = (score_plus - score_minus) / (2 * delta)

        return gradient, total_extractions

    def step(
        self,
        params: dict,
        progress_callback: Optional[callable] = None,
    ) -> dict:
        """Perform one gradient ascent step.

        Args:
            params: Current parameter values
            progress_callback: Optional callback for gradient estimation progress

        Returns:
            Dictionary with:
                - new_params: Updated parameter values
                - gradient: Computed gradient
                - prev_hexagonalness: Score before step
                - hexagonalness: Score after step
                - delta: Change in score
                - tubercles: Extraction results
                - edges: Extraction results
                - statistics: Extraction statistics
                - extractions_performed: Number of extractions run
        """
        # Get current score
        prev_result = self._run_extraction(params)
        prev_score = prev_result['statistics']['hexagonalness_score']

        # Estimate gradient
        gradient, gradient_extractions = self.estimate_gradient(
            params, progress_callback
        )

        # Update parameters using gradient ascent
        new_params = params.copy()
        for param_name in self.enabled_params:
            if param_name in gradient:
                lr = PARAMETERS[param_name]['lr']
                new_value = params[param_name] + lr * gradient[param_name]
                new_params[param_name] = self._clamp(param_name, new_value)

        # Run extraction with new parameters
        result = self._run_extraction(new_params)
        new_score = result['statistics']['hexagonalness_score']

        return {
            'success': True,
            'new_params': new_params,
            'gradient': gradient,
            'prev_hexagonalness': prev_score,
            'hexagonalness': new_score,
            'delta': new_score - prev_score,
            'tubercles': result['tubercles'],
            'edges': result['edges'],
            'statistics': result['statistics'],
            'extractions_performed': gradient_extractions + 2,  # +2 for prev and new
        }

    @staticmethod
    def check_convergence(
        prev_score: float,
        new_score: float,
        iteration: int,
        delta_threshold: float = 0.001,
        max_iterations: int = 20,
        target_score: float = 0.85,
        min_iterations: int = 2,
    ) -> tuple[bool, str]:
        """Check if optimization should stop.

        Args:
            prev_score: Previous hexagonalness score
            new_score: Current hexagonalness score
            iteration: Current iteration number (1-indexed)
            delta_threshold: Minimum score change to continue
            max_iterations: Maximum number of iterations
            target_score: Target score to achieve
            min_iterations: Minimum iterations before allowing delta-based convergence

        Returns:
            Tuple of (should_stop, reason)
        """
        delta = abs(new_score - prev_score)

        # Target reached can stop immediately
        if new_score >= target_score:
            return True, 'target_reached'

        # Max iterations always stops
        if iteration >= max_iterations:
            return True, 'max_iterations'

        # Delta-based convergence requires minimum iterations
        # (first iteration may have zero delta if gradient is flat)
        if iteration >= min_iterations and delta < delta_threshold:
            return True, 'converged'

        return False, ''


def run_optimize_step(
    image_path: str,
    um_per_px: float,
    params: dict,
    enabled_params: Optional[list] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """Convenience function to run a single optimization step.

    Args:
        image_path: Path to the image file
        um_per_px: Calibration in micrometers per pixel
        params: Current parameter values
        enabled_params: List of parameter names to optimize
        progress_callback: Optional callback for progress updates

    Returns:
        Step result dictionary
    """
    optimizer = GradientOptimizer(
        image_path=image_path,
        um_per_px=um_per_px,
        enabled_params=enabled_params,
    )
    return optimizer.step(params, progress_callback)
