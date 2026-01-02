/**
 * Fish Scale Measurement UI - Parameter Optimization
 *
 * Gradient-based optimizer that adjusts extraction parameters
 * to maximize the hexagonalness score.
 */
console.log('[optimize.js] Module loading...');

window.optimize = (function() {
    'use strict';
    console.log('[optimize] IIFE executing');

    // State
    const state = {
        isRunning: false,
        currentIteration: 0,
        maxIterations: 20,
        history: [],
        bestScore: 0,
        bestParams: null,
        stopRequested: false,
    };

    // Default enabled parameters (most impactful)
    const DEFAULT_ENABLED = ['threshold', 'min_circularity', 'blur_sigma'];

    /**
     * Initialize the optimization module
     */
    function init() {
        console.log('[optimize] init() called');

        // Bind button handlers
        const stepBtn = document.getElementById('optimizeStepBtn');
        const autoBtn = document.getElementById('optimizeAutoBtn');
        const stopBtn = document.getElementById('optimizeStopBtn');

        if (stepBtn) {
            stepBtn.addEventListener('click', runStep);
        }
        if (autoBtn) {
            autoBtn.addEventListener('click', runAuto);
        }
        if (stopBtn) {
            stopBtn.addEventListener('click', stop);
        }

        // Set default checkboxes
        const checkboxes = document.querySelectorAll('.optimize-param-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = DEFAULT_ENABLED.includes(cb.dataset.param);
        });

        console.log('Optimize module initialized');
    }

    /**
     * Get currently enabled parameters from checkboxes
     */
    function getEnabledParams() {
        const checkboxes = document.querySelectorAll('.optimize-param-checkbox:checked');
        return Array.from(checkboxes).map(cb => cb.dataset.param);
    }

    /**
     * Get current parameters from configure module
     */
    function getCurrentParams() {
        if (window.configure && typeof window.configure.getParams === 'function') {
            return window.configure.getParams();
        }
        // Fallback to reading from form
        return {
            method: document.getElementById('method')?.value || 'log',
            threshold: parseFloat(document.getElementById('threshold')?.value) || 0.05,
            min_diameter_um: parseFloat(document.getElementById('min_diameter_um')?.value) || 2.0,
            max_diameter_um: parseFloat(document.getElementById('max_diameter_um')?.value) || 10.0,
            min_circularity: parseFloat(document.getElementById('min_circularity')?.value) || 0.5,
            clahe_clip: parseFloat(document.getElementById('clahe_clip')?.value) || 0.03,
            clahe_kernel: parseInt(document.getElementById('clahe_kernel')?.value) || 8,
            blur_sigma: parseFloat(document.getElementById('blur_sigma')?.value) || 1.0,
            neighbor_graph: document.getElementById('neighbor_graph')?.value || 'delaunay',
            cull_long_edges: document.getElementById('cull_long_edges')?.checked ?? true,
            cull_factor: parseFloat(document.getElementById('cull_factor')?.value) || 1.8,
        };
    }

    /**
     * Set UI running state
     */
    function setRunning(running) {
        state.isRunning = running;

        const stepBtn = document.getElementById('optimizeStepBtn');
        const autoBtn = document.getElementById('optimizeAutoBtn');
        const stopBtn = document.getElementById('optimizeStopBtn');
        const spinner = document.getElementById('optimizeSpinner');
        const checkboxes = document.querySelectorAll('.optimize-param-checkbox');

        if (stepBtn) stepBtn.disabled = running;
        if (autoBtn) autoBtn.disabled = running;
        if (stopBtn) stopBtn.disabled = !running;
        if (spinner) spinner.style.display = running ? 'inline-block' : 'none';

        // Disable checkboxes while running
        checkboxes.forEach(cb => cb.disabled = running);
    }

    /**
     * Update status display
     */
    function updateStatus(message, type) {
        const statusEl = document.getElementById('optimizeStatus');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.className = 'optimize-status-value';
            if (type) {
                statusEl.classList.add(`status-${type}`);
            }
        }
    }

    /**
     * Update iteration display
     */
    function updateIterationDisplay(iteration, hexScore, delta, bestScore) {
        const iterEl = document.getElementById('optimizeIteration');
        const hexEl = document.getElementById('optimizeHexScore');
        const deltaEl = document.getElementById('optimizeHexDelta');
        const bestEl = document.getElementById('optimizeBestScore');

        if (iterEl) {
            iterEl.textContent = iteration || '-';
        }
        if (hexEl) {
            hexEl.textContent = hexScore !== undefined ? hexScore.toFixed(3) : '-';
        }
        if (deltaEl && delta !== undefined) {
            const sign = delta >= 0 ? '+' : '';
            deltaEl.textContent = `(${sign}${delta.toFixed(4)})`;
            deltaEl.className = 'optimize-delta ' + (delta >= 0 ? 'positive' : 'negative');
        } else if (deltaEl) {
            deltaEl.textContent = '';
        }
        if (bestEl) {
            bestEl.textContent = bestScore !== undefined ? bestScore.toFixed(3) : '-';
        }
    }

    /**
     * Apply new parameters to the configure form
     */
    function applyParamsToForm(params) {
        if (!params) {
            console.log('[optimize] applyParamsToForm: no params');
            return;
        }

        console.log('[optimize] applyParamsToForm:', params);

        // Update form inputs
        const paramIds = [
            'threshold', 'min_diameter_um', 'max_diameter_um', 'min_circularity',
            'clahe_clip', 'clahe_kernel', 'blur_sigma'
        ];

        paramIds.forEach(param => {
            const el = document.getElementById(param);
            const paramValue = params[param];
            console.log(`[optimize] Setting ${param}: element=${!!el}, value=${paramValue}`);
            if (el && paramValue !== undefined) {
                const oldValue = el.value;
                el.value = paramValue;
                console.log(`[optimize] ${param}: ${oldValue} -> ${el.value}`);
                // Trigger input event for sliders with value displays
                el.dispatchEvent(new Event('input', { bubbles: true }));
                // Also trigger change event
                el.dispatchEvent(new Event('change', { bubbles: true }));

                // Manually update value display span
                const displayEl = document.getElementById(`${param}_value`);
                if (displayEl) {
                    const val = parseFloat(paramValue);
                    const formatted = isNaN(val) ? paramValue : val.toFixed(3);
                    if (displayEl.tagName === 'INPUT') {
                        displayEl.value = formatted;
                    } else {
                        displayEl.textContent = formatted;
                    }
                    console.log(`[optimize] Updated ${param}_value display to: ${formatted}`);
                }
            }
        });
    }

    /**
     * Update UI with optimization results
     */
    function handleStepResult(result) {
        console.log('[optimize] handleStepResult:', result);

        // Apply new parameters to form
        applyParamsToForm(result.new_params);

        // Update overlay with new tubercles/edges
        console.log('[optimize] Updating overlay with', result.tubercles?.length, 'tubercles,', result.edges?.length, 'edges');
        if (window.overlay) {
            window.overlay.setData(result.tubercles, result.edges);
            // Ensure render happens
            if (typeof window.overlay.render === 'function') {
                window.overlay.render();
            }
        } else {
            console.warn('[optimize] window.overlay not available');
        }

        // Update sets module
        if (window.sets) {
            window.sets.setCurrentData(result.tubercles, result.edges);
            window.sets.setCurrentParameters(result.new_params);
        }

        // Update data tables
        if (window.data) {
            window.data.setData(result.tubercles, result.edges, result.statistics);
        }

        // Update editor
        if (window.editor) {
            window.editor.setData(result.tubercles, result.edges);
        }

        // Update statistics display
        if (window.extraction && typeof window.extraction.updateStatsDisplay === 'function') {
            window.extraction.updateStatsDisplay(result.statistics);
        }

        // Track history
        state.history.push({
            iteration: state.currentIteration,
            score: result.hexagonalness,
            params: { ...result.new_params },
        });

        // Track best
        if (result.hexagonalness > state.bestScore) {
            state.bestScore = result.hexagonalness;
            state.bestParams = { ...result.new_params };
        }

        // Update display
        updateIterationDisplay(
            state.currentIteration,
            result.hexagonalness,
            result.delta,
            state.bestScore
        );
    }

    /**
     * Run a single optimization step
     */
    async function runStep() {
        if (state.isRunning) return;

        const params = getCurrentParams();
        const enabledParams = getEnabledParams();

        if (enabledParams.length === 0) {
            window.app?.showToast('Select at least one parameter to optimize', 'warning');
            return;
        }

        setRunning(true);
        updateStatus('Estimating gradient...', 'running');
        state.currentIteration++;

        try {
            const response = await fetch('/api/optimize-step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    params,
                    enabled_params: enabledParams,
                }),
            });

            const result = await response.json();

            if (result.error) {
                updateStatus(result.error, 'error');
                window.app?.showToast(result.error, 'error');
                return;
            }

            handleStepResult(result);
            updateStatus('Step complete', 'success');

            const deltaSign = result.delta >= 0 ? '+' : '';
            window.app?.showToast(
                `Step ${state.currentIteration}: Hexagonalness ${result.hexagonalness.toFixed(3)} (${deltaSign}${result.delta.toFixed(4)})`,
                result.delta >= 0 ? 'success' : 'info'
            );

        } catch (err) {
            updateStatus('Step failed: ' + err.message, 'error');
            window.app?.showToast('Optimization step failed: ' + err.message, 'error');
        } finally {
            setRunning(false);
        }
    }

    /**
     * Run automatic optimization until convergence (frontend-driven loop)
     */
    async function runAuto() {
        console.log('[optimize] runAuto() called');
        if (state.isRunning) return;

        let params = getCurrentParams();
        console.log('[optimize] Current params:', params);
        const enabledParams = getEnabledParams();
        const maxIter = parseInt(document.getElementById('optimizeMaxIterations')?.value) || 20;
        const deltaThreshold = parseFloat(document.getElementById('optimizeDeltaThreshold')?.value) || 0.001;
        const targetScore = parseFloat(document.getElementById('optimizeTargetScore')?.value) || 0.85;

        if (enabledParams.length === 0) {
            window.app?.showToast('Select at least one parameter to optimize', 'warning');
            return;
        }

        // Reset state
        state.history = [];
        state.currentIteration = 0;
        state.maxIterations = maxIter;
        state.bestScore = 0;
        state.bestParams = null;
        state.stopRequested = false;

        setRunning(true);
        updateStatus('Starting optimization...', 'running');

        // Update max iterations display
        const maxIterEl = document.getElementById('optimizeMaxIter');
        if (maxIterEl) maxIterEl.textContent = maxIter;

        let lastResult = null;
        let stopReason = '';

        try {
            // Frontend-driven loop: call step repeatedly
            for (let iteration = 1; iteration <= maxIter; iteration++) {
                // Check if stop was requested
                if (state.stopRequested) {
                    stopReason = 'stopped';
                    break;
                }

                state.currentIteration = iteration;
                updateStatus(`Iteration ${iteration}/${maxIter}...`, 'running');

                const response = await fetch('/api/optimize-step', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        params,
                        enabled_params: enabledParams,
                        iteration,
                        max_iterations: maxIter,
                        delta_threshold: deltaThreshold,
                        target_score: targetScore,
                    }),
                });

                const result = await response.json();

                if (result.error) {
                    updateStatus(result.error, 'error');
                    window.app?.showToast(result.error, 'error');
                    return;
                }

                lastResult = result;

                // Update UI immediately after each step
                handleStepResult(result);

                // Show iteration progress
                const deltaSign = result.delta >= 0 ? '+' : '';
                updateStatus(
                    `Iteration ${iteration}: Hex ${result.hexagonalness.toFixed(3)} (${deltaSign}${result.delta.toFixed(4)})`,
                    result.delta >= 0 ? 'running' : 'warning'
                );

                // Use the new params for next iteration
                params = { ...params, ...result.new_params };

                // Check if we should stop
                if (result.should_stop) {
                    stopReason = result.stop_reason;
                    break;
                }

                // Small delay to allow UI to update
                await new Promise(resolve => setTimeout(resolve, 50));
            }

            // Final status update
            if (lastResult) {
                const reasonMap = {
                    'converged': 'Converged',
                    'target_reached': 'Target reached',
                    'max_iterations': 'Max iterations',
                    'stopped': 'Stopped by user',
                };
                const reasonText = reasonMap[stopReason] || stopReason || 'Complete';
                updateStatus(`${reasonText} after ${state.currentIteration} iterations`, 'success');

                window.app?.showToast(
                    `Optimization complete: ${reasonText}. Final score: ${lastResult.hexagonalness.toFixed(3)}`,
                    'success'
                );
            }

        } catch (err) {
            updateStatus('Optimization failed: ' + err.message, 'error');
            window.app?.showToast('Optimization failed: ' + err.message, 'error');
        } finally {
            setRunning(false);
        }
    }

    /**
     * Stop running optimization
     */
    function stop() {
        if (!state.isRunning) return;

        state.stopRequested = true;
        updateStatus('Stopping...', 'warning');
        window.app?.showToast('Optimization will stop after current step', 'info');
    }

    /**
     * Reset optimization state
     */
    function reset() {
        state.history = [];
        state.currentIteration = 0;
        state.bestScore = 0;
        state.bestParams = null;

        updateStatus('Ready', '');
        updateIterationDisplay(null, null, null, null);
    }

    /**
     * Get optimization history
     */
    function getHistory() {
        return [...state.history];
    }

    /**
     * Get current state
     */
    function getState() {
        return { ...state };
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    return {
        init,
        runStep,
        runAuto,
        stop,
        reset,
        getEnabledParams,
        getHistory,
        getState,
    };
})();
