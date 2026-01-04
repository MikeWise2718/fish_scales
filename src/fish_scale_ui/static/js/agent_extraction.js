/**
 * Fish Scale Measurement UI - Agent Extraction Tab
 *
 * This module handles LLM agent-based optimization for tubercle detection.
 * The agent iteratively refines detection parameters to maximize hexagonalness score.
 */

window.agentExtraction = (function() {
    // State for tracking optimization progress
    const state = {
        isRunning: false,
        isPaused: false,
        sessionId: null,
        currentIteration: 0,
        maxIterations: 30,
        currentPhase: null,         // Current agent phase (e.g., "Phase 1: Initial Detection")
        currentTubercleCount: null, // Current number of detected tubercles
        currentITCCount: null,      // Current number of ITC connections
        currentReasoning: null,     // LLM's reasoning for current adjustment
        lastPrompt: null,           // Full prompt text (with truncated base64)
        lastPromptSize: 0,          // Size of last prompt in bytes
        actionSummary: [],          // Array of { timestamp, elapsed, action }
        seenLogLines: new Set(),    // Track processed log lines to avoid duplicates
        bestScore: 0,
        bestParams: null,
        bestSetName: null,
        history: [],  // Array of { iteration, score, params, setName }
        pollingInterval: null,
        providers: [],  // Available providers from API
        chart: null,    // Chart.js instance or canvas context
        startTime: null,     // Timestamp when agent started
        stepStartTime: null, // Timestamp when current step/iteration started
        lastIteration: -1,   // Track iteration changes for step timing
        // Cost tracking
        costs: {
            provider: null,
            model: null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,        // Cost of last LLM call
            previousCost: 0,        // Previous total cost (for delta calculation)
        },
    };

    // Default optimization configuration
    const config = {
        pollIntervalMs: 1000,
        targetScore: 0.85,
        earlyStopThreshold: 5,  // Stop if no improvement for N iterations
    };

    /**
     * Get theme colors from CSS custom properties.
     * Falls back to default dark theme colors if variables are not set.
     */
    function getThemeColors() {
        const styles = getComputedStyle(document.documentElement);
        return {
            background: styles.getPropertyValue('--panel-dark-bg-alt').trim() || '#1a1a2e',
            backgroundLight: styles.getPropertyValue('--panel-dark-bg').trim() || '#1e293b',
            grid: styles.getPropertyValue('--panel-dark-grid').trim() || '#333344',
            text: styles.getPropertyValue('--panel-dark-text-muted').trim() || '#888888',
            textDim: styles.getPropertyValue('--panel-dark-text-dim').trim() || '#64748b',
            border: styles.getPropertyValue('--panel-dark-border').trim() || '#334155',
        };
    }

    /**
     * Initialize providers from API
     */
    async function loadProviders() {
        try {
            const response = await fetch('/api/agent/providers');
            const data = await response.json();
            state.providers = data.providers || [];
            populateProviderSelect();
            populateModelSelect();
        } catch (err) {
            console.error('Failed to load providers:', err);
        }
    }

    /**
     * Populate the provider select dropdown
     */
    function populateProviderSelect() {
        const select = document.getElementById('agentProvider');
        if (!select) return;

        // Keep existing options but mark configured ones
        const options = select.querySelectorAll('option');
        options.forEach(opt => {
            const provider = state.providers.find(p => p.name === opt.value);
            if (provider) {
                const suffix = provider.configured ? '' : ' (not configured)';
                opt.textContent = `${provider.display_name}${suffix}`;
                opt.disabled = !provider.configured;
            }
        });

        // Select first configured provider
        const firstConfigured = state.providers.find(p => p.configured);
        if (firstConfigured) {
            select.value = firstConfigured.name;
        }
    }

    /**
     * Populate the model select dropdown based on selected provider
     */
    function populateModelSelect() {
        const providerSelect = document.getElementById('agentProvider');
        const modelSelect = document.getElementById('agentModel');
        if (!providerSelect || !modelSelect) return;

        const providerName = providerSelect.value;
        const provider = state.providers.find(p => p.name === providerName);

        // Clear existing options
        modelSelect.innerHTML = '';

        if (provider) {
            // Add default model option
            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = `Default (${provider.default_model})`;
            modelSelect.appendChild(defaultOpt);

            // Provider-specific models could be added here if API returns them
        } else {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = '-- Select Provider First --';
            modelSelect.appendChild(opt);
        }
    }

    /**
     * Start the agent optimization process
     */
    async function startOptimization() {
        if (state.isRunning) {
            console.warn('Optimization already running');
            return;
        }

        // Validate inputs
        const provider = document.getElementById('agentProvider')?.value;
        const model = document.getElementById('agentModel')?.value;
        const profile = document.getElementById('agentProfile')?.value || 'default';
        const useCurrentParams = document.getElementById('agentUseCurrentParams')?.checked ?? true;
        const targetScore = parseFloat(document.getElementById('agentTargetScore')?.value) || 0.70;
        const maxIterations = parseInt(document.getElementById('agentMaxIterations')?.value, 10) || 30;

        // Check if provider is configured
        const providerInfo = state.providers.find(p => p.name === provider);
        if (!providerInfo || !providerInfo.configured) {
            window.app?.showToast(`Provider ${provider} is not configured. Set ${providerInfo?.env_var} environment variable.`, 'error');
            return;
        }

        // Get current image info from server
        let currentImage = null;
        try {
            const imgResponse = await fetch('/api/current-image');
            currentImage = await imgResponse.json();
        } catch (err) {
            console.error('Failed to get current image info:', err);
        }

        // Check if image is loaded
        if (!currentImage?.loaded) {
            window.app?.showToast('No image loaded. Load an image first.', 'warning');
            return;
        }

        // Check calibration
        const calibration = window.calibration?.getCurrentCalibration();
        if (!calibration || !calibration.um_per_px) {
            window.app?.showToast('Calibration not set. Set calibration first.', 'warning');
            return;
        }

        console.log('Starting agent optimization...');
        state.isRunning = true;
        state.isPaused = false;
        state.currentIteration = 0;
        state.maxIterations = maxIterations;
        state.history = [];
        state.bestScore = 0;
        state.bestParams = null;
        state.bestSetName = null;
        state.startTime = Date.now();
        state.stepStartTime = Date.now();
        state.lastIteration = -1;
        // Initialize costs with selected provider/model
        state.costs = {
            provider: provider,
            model: model || providerInfo?.default_model || null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
        };

        updateUI();
        updateStatus('Starting agent...');
        updateElapsed();
        updateCosts();

        // Disable Configure tab controls during optimization
        window.configure?.setEnabled?.(false);

        try {
            const response = await fetch('/api/agent/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider: provider,
                    model: model || undefined,
                    max_iterations: maxIterations,
                    target_score: targetScore,
                    profile: useCurrentParams ? null : profile,
                    use_current_params: useCurrentParams,
                    verbose: true,
                    image_path: currentImage?.path || currentImage?.web_path,
                    calibration: calibration.um_per_px,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app?.showToast(result.error, 'error');
                state.isRunning = false;
                updateUI();
                updateStatus('Failed to start');
                return;
            }

            state.sessionId = result.session_id;
            console.log('Agent started, session:', state.sessionId);
            window.app?.showToast('Agent started', 'success');
            updateStatus('Running...');

            // Start polling for status updates
            startPolling();

        } catch (err) {
            console.error('Failed to start agent:', err);
            window.app?.showToast(`Failed to start agent: ${err.message}`, 'error');
            state.isRunning = false;
            updateUI();
            updateStatus('Error starting agent');
        }
    }

    /**
     * Stop the agent optimization process
     */
    async function stopOptimization() {
        if (!state.isRunning || !state.sessionId) {
            console.warn('No optimization running');
            return;
        }

        console.log('Stopping agent optimization...');
        updateStatus('Stopping...');

        try {
            const response = await fetch(`/api/agent/stop/${state.sessionId}`, {
                method: 'POST',
            });

            const result = await response.json();

            if (result.error) {
                console.error('Stop error:', result.error);
            }

            state.isRunning = false;
            state.isPaused = false;
            stopPolling();
            updateUI();
            updateStatus('Stopped by user');
            window.app?.showToast('Agent stopped', 'info');

            // Re-enable Configure tab controls
            window.configure?.setEnabled?.(true);

        } catch (err) {
            console.error('Failed to stop agent:', err);
            window.app?.showToast(`Failed to stop agent: ${err.message}`, 'error');
        }
    }

    /**
     * Accept the best result from optimization
     */
    async function acceptBest() {
        if (!state.bestSetName) {
            window.app?.showToast('No best result available', 'warning');
            return;
        }

        console.log('Accepting best result:', state.bestSetName);
        updateStatus('Applying best result...');

        // Switch to the best set if sets module is available
        if (window.sets && state.bestSetName) {
            // Try to find and switch to the best set
            const sets = window.sets.getAllSets?.() || [];
            const bestSet = sets.find(s => s.name === state.bestSetName);
            if (bestSet) {
                window.sets.switchTo?.(bestSet.id);
            }
        }

        // Apply best parameters if configure module is available
        if (window.configure && state.bestParams) {
            window.configure.setParams?.(state.bestParams);
        }

        window.app?.showToast(`Accepted best result: ${state.bestSetName}`, 'success');
    }

    /**
     * Reset the optimization state
     */
    function reset() {
        console.log('Resetting agent optimization state');

        stopPolling();

        state.isRunning = false;
        state.isPaused = false;
        state.sessionId = null;
        state.currentIteration = 0;
        state.currentPhase = null;
        state.currentTubercleCount = null;
        state.currentITCCount = null;
        state.currentReasoning = null;
        state.lastPrompt = null;
        state.lastPromptSize = 0;
        state.actionSummary = [];
        state.seenLogLines = new Set();
        state.bestScore = 0;
        state.bestParams = null;
        state.bestSetName = null;
        state.history = [];
        state.startTime = null;
        state.stepStartTime = null;
        state.lastIteration = -1;
        // Reset costs
        state.costs = {
            provider: null,
            model: null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,
            previousCost: 0,
        };

        updateUI();
        updateChart();
        updateStatus('Ready');
        updateElapsed();
        updateCosts();

        // Re-enable Configure tab controls
        window.configure?.setEnabled?.(true);
    }

    /**
     * Format elapsed time as HH:MM:SS
     */
    function formatElapsed(ms) {
        const seconds = Math.floor(ms / 1000);
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) {
            return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    /**
     * Format bytes as human readable string (KB, MB, etc.)
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Copy text to clipboard and show feedback
     * @param {string} text - Text to copy
     * @param {HTMLElement} button - Button element for visual feedback
     */
    async function copyToClipboard(text, button) {
        try {
            await navigator.clipboard.writeText(text);
            // Visual feedback
            if (button) {
                button.classList.add('copied');
                const originalText = button.innerHTML;
                button.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
                setTimeout(() => {
                    button.classList.remove('copied');
                    button.innerHTML = originalText;
                }, 1500);
            }
            return true;
        } catch (err) {
            console.error('Failed to copy:', err);
            window.app?.showToast('Failed to copy to clipboard', 'error');
            return false;
        }
    }

    /**
     * Add an action to the action summary
     * @param {string} action - Description of the action
     */
    function addAction(action) {
        if (!state.startTime) return;

        const now = Date.now();
        const elapsedMs = now - state.startTime;
        const elapsedSec = (elapsedMs / 1000).toFixed(1);

        state.actionSummary.push({
            timestamp: now,
            elapsed: elapsedSec,
            action: action,
        });

        updateActionSummary();
    }

    /**
     * Update the action summary display
     */
    function updateActionSummary() {
        const summaryEl = document.getElementById('agentActionSummary');
        if (!summaryEl) return;

        if (state.actionSummary.length === 0) {
            summaryEl.textContent = 'No actions yet.';
            return;
        }

        const lines = state.actionSummary.map(a => `[${a.elapsed}s] ${a.action}`);
        summaryEl.textContent = lines.join('\n');

        // Auto-scroll to bottom
        summaryEl.scrollTop = summaryEl.scrollHeight;
    }

    /**
     * Clear the action summary
     */
    function clearActions() {
        state.actionSummary = [];
        updateActionSummary();
    }

    /**
     * Update elapsed time display
     */
    function updateElapsed() {
        const elapsedEl = document.getElementById('agentElapsed');
        if (!elapsedEl) return;

        if (!state.startTime || !state.isRunning) {
            elapsedEl.textContent = '-';
            return;
        }

        const elapsed = Date.now() - state.startTime;
        elapsedEl.textContent = formatElapsed(elapsed);
    }

    /**
     * Update step time display
     */
    function updateStepTime() {
        const stepTimeEl = document.getElementById('agentStepTime');
        if (!stepTimeEl) return;

        if (!state.stepStartTime || !state.isRunning) {
            stepTimeEl.textContent = '-';
            return;
        }

        const stepElapsed = Date.now() - state.stepStartTime;
        stepTimeEl.textContent = formatElapsed(stepElapsed);
    }

    /**
     * Check if iteration changed and reset step timer if so
     */
    function checkIterationChange(newIteration) {
        if (newIteration !== state.lastIteration) {
            state.lastIteration = newIteration;
            state.stepStartTime = Date.now();
        }
    }

    /**
     * Update the status display with data from API
     * @param {string|object} data - Status message string or status data object from API
     */
    function updateStatus(data) {
        // Handle string messages (for local status updates)
        if (typeof data === 'string') {
            const lastActionEl = document.getElementById('agentLastAction');
            if (lastActionEl) {
                lastActionEl.textContent = data;
            }
            updateStateDisplay();
            return;
        }

        // Handle status data object from API
        if (data) {
            // Update state values from API response
            if (data.iteration !== undefined) {
                checkIterationChange(data.iteration);
                state.currentIteration = data.iteration;
            }
            if (data.phase !== undefined) {
                state.currentPhase = data.phase;
            }
            if (data.tubercle_count !== undefined) {
                state.currentTubercleCount = data.tubercle_count;
            }
            if (data.best_score !== undefined) {
                state.bestScore = data.best_score;
            }
            if (data.best_params !== undefined) {
                state.bestParams = data.best_params;
            }
            if (data.best_set_name !== undefined) {
                state.bestSetName = data.best_set_name;
            }
            if (data.history) {
                state.history = data.history;
            }

            // Update last action from various possible fields
            const lastActionEl = document.getElementById('agentLastAction');
            if (lastActionEl) {
                const message = data.message || data.last_action || data.last_output || 'Running...';
                // Truncate long messages
                lastActionEl.textContent = message.length > 80 ? message.substring(0, 80) + '...' : message;
            }
        }

        updateStateDisplay();
    }

    /**
     * Update state indicator elements
     */
    function updateStateDisplay() {
        // Update state indicator
        const stateEl = document.getElementById('agentState');
        if (stateEl) {
            if (state.isRunning) {
                stateEl.textContent = state.isPaused ? 'Paused' : 'Running';
                stateEl.className = 'agent-status-value status-running';
            } else {
                stateEl.textContent = 'Idle';
                stateEl.className = 'agent-status-value';
            }
        }

        // Update phase display
        const phaseEl = document.getElementById('agentPhase');
        if (phaseEl) {
            phaseEl.textContent = state.currentPhase || '-';
        }

        // Update iteration counter
        const iterEl = document.getElementById('agentIteration');
        if (iterEl) {
            if (state.isRunning || state.currentIteration > 0) {
                iterEl.textContent = `${state.currentIteration} / ${state.maxIterations}`;
            } else {
                iterEl.textContent = '-';
            }
        }

        // Update tubercle count
        const tubCountEl = document.getElementById('agentTubercleCount');
        if (tubCountEl) {
            tubCountEl.textContent = state.currentTubercleCount !== null && state.currentTubercleCount !== undefined
                ? state.currentTubercleCount
                : '-';
        }

        // Update best score
        const bestScoreEl = document.getElementById('agentBestScore');
        if (bestScoreEl) {
            if (state.bestScore > 0) {
                bestScoreEl.textContent = state.bestScore.toFixed(3);
            } else {
                bestScoreEl.textContent = '-';
            }
        }

        // Update elapsed time
        updateElapsed();

        // Update step time
        updateStepTime();
    }

    /**
     * Update the progress chart with optimization history
     */
    function updateChart() {
        // Try agentChart (canvas) first, then agentProgressChart (div container)
        let canvas = document.getElementById('agentChart');
        const chartContainer = document.getElementById('agentProgressChart');

        // If no canvas by ID, try to find/create one in the container
        if (!canvas && chartContainer) {
            canvas = chartContainer.querySelector('canvas');
            if (!canvas && state.history.length > 0) {
                chartContainer.innerHTML = '';
                canvas = document.createElement('canvas');
                canvas.width = 400;
                canvas.height = 200;
                chartContainer.appendChild(canvas);
            }
        }

        if (!canvas) return;

        // Show placeholder message if no history
        if (state.history.length === 0) {
            const ctx = canvas.getContext('2d');
            const width = canvas.width;
            const height = canvas.height;
            const colors = getThemeColors();
            ctx.fillStyle = colors.backgroundLight;
            ctx.fillRect(0, 0, width, height);
            ctx.fillStyle = colors.textDim;
            ctx.font = '14px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Progress chart will appear during extraction', width / 2, height / 2);
            return;
        }

        // Ensure canvas size is set
        if (!canvas.width || canvas.width < 100) {
            canvas.width = 400;
            canvas.height = 200;
        }

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const colors = getThemeColors();

        // Clear canvas
        ctx.fillStyle = colors.background;
        ctx.fillRect(0, 0, width, height);

        // Draw chart
        const padding = { top: 20, right: 20, bottom: 30, left: 50 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Get data points
        const scores = state.history.map(h => h.score || h.hexagonalness || 0);
        const maxScore = Math.max(1.0, ...scores);
        const minScore = 0;

        // Draw grid lines
        ctx.strokeStyle = colors.grid;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartHeight * i / 4);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
        }

        // Draw y-axis labels
        ctx.fillStyle = colors.text;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
            const value = maxScore - (maxScore - minScore) * i / 4;
            const y = padding.top + (chartHeight * i / 4);
            ctx.fillText(value.toFixed(2), padding.left - 5, y + 3);
        }

        // Draw x-axis label
        ctx.textAlign = 'center';
        ctx.fillText('Iteration', width / 2, height - 5);

        // Draw best score line
        if (state.bestScore > 0) {
            const bestY = padding.top + chartHeight * (1 - (state.bestScore - minScore) / (maxScore - minScore));
            ctx.strokeStyle = '#00ff88';
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            ctx.moveTo(padding.left, bestY);
            ctx.lineTo(width - padding.right, bestY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Label
            ctx.fillStyle = '#00ff88';
            ctx.textAlign = 'left';
            ctx.fillText(`Best: ${state.bestScore.toFixed(3)}`, padding.left + 5, bestY - 5);
        }

        // Draw data line
        if (scores.length > 1) {
            ctx.strokeStyle = '#00aaff';
            ctx.lineWidth = 2;
            ctx.beginPath();

            for (let i = 0; i < scores.length; i++) {
                const x = padding.left + (chartWidth * i / (scores.length - 1));
                const y = padding.top + chartHeight * (1 - (scores[i] - minScore) / (maxScore - minScore));
                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            ctx.stroke();

            // Draw points
            ctx.fillStyle = '#00aaff';
            for (let i = 0; i < scores.length; i++) {
                const x = padding.left + (chartWidth * i / (scores.length - 1));
                const y = padding.top + chartHeight * (1 - (scores[i] - minScore) / (maxScore - minScore));
                ctx.beginPath();
                ctx.arc(x, y, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw legend/summary on chart
        const latest = state.history[state.history.length - 1];
        const latestScore = (latest?.score || latest?.hexagonalness || 0).toFixed(3);

        ctx.fillStyle = colors.text;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(`Iterations: ${state.history.length}  Latest: ${latestScore}`, width - padding.right, height - 5);
    }

    /**
     * Update the current parameters display
     * @param {object} data - Status data containing current parameters
     */
    function updateParams(data) {
        const paramsEl = document.getElementById('agentParamsDisplay');
        if (!paramsEl) return;

        const params = data?.current_params || data?.best_params || state.bestParams;

        if (!params) {
            paramsEl.innerHTML = '<p class="hint">Parameters will be displayed when agent is running.</p>';
            return;
        }

        // Build parameter display HTML
        const paramItems = [];
        const displayNames = {
            method: 'Method',
            threshold: 'Threshold',
            min_diameter_um: 'Min Diameter',
            max_diameter_um: 'Max Diameter',
            min_circularity: 'Circularity',
            clahe_clip: 'CLAHE Clip',
            clahe_kernel: 'CLAHE Kernel',
            blur_sigma: 'Blur Sigma',
            neighbor_graph: 'Graph Type',
            graph_type: 'Graph Type',
            cull_long_edges: 'Cull Long Edges',
            cull_factor: 'Cull Factor',
        };

        for (const [key, value] of Object.entries(params)) {
            const displayName = displayNames[key] || key;
            // Format value based on type
            let displayValue;
            if (typeof value === 'boolean') {
                displayValue = value ? 'Yes' : 'No';
            } else if (typeof value === 'number') {
                displayValue = value.toFixed(3);
            } else {
                displayValue = value;
            }
            paramItems.push(`
                <div class="agent-param-row">
                    <span class="agent-param-label">${displayName}:</span>
                    <span class="agent-param-value">${displayValue}</span>
                </div>
            `);
        }

        paramsEl.innerHTML = paramItems.join('');
    }

    /**
     * Update the costs panel display
     * @param {object} data - Status data containing usage information
     */
    function updateCosts(data) {
        const modelEl = document.getElementById('agentCostModel');
        const inputTokensEl = document.getElementById('agentCostInputTokens');
        const outputTokensEl = document.getElementById('agentCostOutputTokens');
        const totalTokensEl = document.getElementById('agentCostTotalTokens');
        const estimateEl = document.getElementById('agentCostEstimate');

        // Update from status data if available
        if (data) {
            if (data.provider) {
                state.costs.provider = data.provider;
            }
            if (data.model) {
                state.costs.model = data.model;
            }
            if (data.usage) {
                state.costs.inputTokens = data.usage.input_tokens || data.usage.prompt_tokens || 0;
                state.costs.outputTokens = data.usage.output_tokens || data.usage.completion_tokens || 0;
                state.costs.estimatedCost = data.usage.cost_usd || data.usage.estimated_cost || 0;
            }
            // Also check for direct token counts
            if (data.input_tokens !== undefined) {
                state.costs.inputTokens = data.input_tokens;
            }
            if (data.output_tokens !== undefined) {
                state.costs.outputTokens = data.output_tokens;
            }
            if (data.cost_usd !== undefined) {
                state.costs.estimatedCost = data.cost_usd;
            }
        }

        // Update model display
        if (modelEl) {
            if (state.costs.model) {
                modelEl.textContent = state.costs.model;
            } else if (state.costs.provider) {
                modelEl.textContent = `${state.costs.provider} (default)`;
            } else {
                modelEl.textContent = '-';
            }
        }

        // Update token counts
        if (inputTokensEl) {
            inputTokensEl.textContent = state.costs.inputTokens.toLocaleString();
        }
        if (outputTokensEl) {
            outputTokensEl.textContent = state.costs.outputTokens.toLocaleString();
        }
        if (totalTokensEl) {
            const total = state.costs.inputTokens + state.costs.outputTokens;
            totalTokensEl.textContent = total.toLocaleString();
        }

        // Update cost estimate
        if (estimateEl) {
            if (state.costs.estimatedCost > 0) {
                estimateEl.textContent = `$${state.costs.estimatedCost.toFixed(4)}`;
            } else if (state.costs.inputTokens > 0 || state.costs.outputTokens > 0) {
                // Estimate cost if not provided (rough estimates based on typical pricing)
                const inputCost = state.costs.inputTokens * 0.000003;  // ~$3/M
                const outputCost = state.costs.outputTokens * 0.000015; // ~$15/M
                const estimated = inputCost + outputCost;
                estimateEl.textContent = `~$${estimated.toFixed(4)}`;
            } else {
                estimateEl.textContent = '$0.0000';
            }
        }

        // Update last step cost
        const lastStepEl = document.getElementById('agentCostLastStep');
        if (lastStepEl) {
            if (state.costs.lastStepCost > 0) {
                lastStepEl.textContent = `$${state.costs.lastStepCost.toFixed(4)}`;
            } else {
                lastStepEl.textContent = '$0.0000';
            }
        }
    }

    /**
     * Poll the agent status API for updates
     */
    async function pollStatus() {
        if (!state.isRunning || !state.sessionId) return;

        try {
            const response = await fetch(`/api/agent/status/${state.sessionId}`);

            if (!response.ok) {
                if (response.status === 404) {
                    console.log('Agent session not found');
                    state.isRunning = false;
                    stopPolling();
                    updateUI();
                    updateStatus('Session ended');
                    return;
                }
                console.log('Agent status request failed:', response.status);
                return;
            }

            const status = await response.json();

            // Parse log lines for structured data
            const prevIteration = state.currentIteration;
            parseLogLines(status.log_lines || []);

            // Fetch current parameters from the tools API
            let currentParams = null;
            try {
                const paramsResponse = await fetch('/api/tools/params');
                if (paramsResponse.ok) {
                    const paramsData = await paramsResponse.json();
                    currentParams = paramsData.parameters || paramsData.params || paramsData;
                }
            } catch (e) {
                // Ignore params fetch errors
            }

            // Update UI with status
            updateStatus(status);
            updateChart();
            updateParams({ current_params: currentParams });
            updateLLMDisplay(status);
            updateCosts(status);

            // Sync parameters to Configure tab (if params changed)
            if (currentParams && window.configure?.setParams) {
                window.configure.setParams(currentParams);
            }

            // Refresh overlay when iteration changes (new extraction completed)
            if (state.currentIteration !== prevIteration && state.currentIteration > 0) {
                refreshFromMCP();
            }

            // Check for completion
            if (status.state === 'completed') {
                state.isRunning = false;
                stopPolling();
                updateStatus('Extraction complete');
                updateUI();
                window.app?.showToast('Agent extraction complete', 'success');

                // Refresh data from MCP state
                refreshFromMCP();

                // Re-enable Configure tab controls
                window.configure?.setEnabled?.(true);

            } else if (status.state === 'failed' || status.state === 'error') {
                state.isRunning = false;
                stopPolling();
                updateStatus(`Error: ${status.error || 'Unknown error'}`);
                updateUI();
                window.app?.showToast(`Agent error: ${status.error || 'Unknown error'}`, 'error');

                // Re-enable Configure tab controls
                window.configure?.setEnabled?.(true);

            } else if (status.state === 'stopped') {
                state.isRunning = false;
                stopPolling();
                updateStatus('Stopped');
                updateUI();

                // Re-enable Configure tab controls
                window.configure?.setEnabled?.(true);
            }

        } catch (err) {
            console.log('Error polling agent status:', err);
            // Don't stop on polling errors - agent may just be busy
        }
    }

    /**
     * Parse log lines to extract structured information
     * @param {string[]} logLines - Array of log line strings
     */
    function parseLogLines(logLines) {
        // Look for iteration, phase, and score information in log output
        for (const line of logLines.slice(-20)) {  // Check last 20 lines
            // Parse iteration numbers - matches both "Iteration N" and "Extraction [N/M]"
            const iterMatch = line.match(/Iteration\s+(\d+)|Extraction\s*\[(\d+)/i);
            if (iterMatch) {
                const iterNum = parseInt(iterMatch[1] || iterMatch[2], 10);
                if (iterNum > state.currentIteration) {
                    state.currentIteration = iterNum;
                }
            }

            // Parse phase information
            const phaseMatch = line.match(/Phase\s+(\d+)/i);
            if (phaseMatch) {
                state.currentPhase = `Phase ${phaseMatch[1]}`;
            }

            // Parse tubercle counts - matches both "42 tubercles" and "Tubercles: 42"
            const tubMatch = line.match(/tubercles?[:\s]+(\d+)|(\d+)\s+tubercles?/i);
            if (tubMatch) {
                state.currentTubercleCount = parseInt(tubMatch[1] || tubMatch[2], 10);
            }

            // Parse usage/cost information
            // Format: "Usage: 1234 input, 567 output, $0.0123 (model-name)"
            const usageMatch = line.match(/Usage:\s*(\d+)\s*input,\s*(\d+)\s*output,\s*\$([0-9.]+)(?:\s*\(([^)]+)\))?/i);
            if (usageMatch) {
                const newCost = parseFloat(usageMatch[3]);
                // Calculate last step cost as delta from previous
                if (state.costs.estimatedCost > 0) {
                    state.costs.lastStepCost = newCost - state.costs.previousCost;
                }
                state.costs.previousCost = state.costs.estimatedCost;
                state.costs.inputTokens = parseInt(usageMatch[1], 10);
                state.costs.outputTokens = parseInt(usageMatch[2], 10);
                state.costs.estimatedCost = newCost;
                if (usageMatch[4]) {
                    state.costs.model = usageMatch[4];
                }
            }

            // Parse ITC (edge) count
            // Format: "edges: 42" or "42 edges" or "n_edges: 42"
            const itcMatch = line.match(/(?:edges|n_edges)[:\s]+(\d+)|(\d+)\s+edges/i);
            if (itcMatch) {
                state.currentITCCount = parseInt(itcMatch[1] || itcMatch[2], 10);
            }

            // Parse prompt statistics
            // Format: "Prompt-Stats: size=12345"
            const promptStatsMatch = line.match(/Prompt-Stats:\s*size=(\d+)/i);
            if (promptStatsMatch) {
                state.lastPromptSize = parseInt(promptStatsMatch[1], 10);
            }

            // Parse full prompt (multiline, pipe-separated)
            // Format: "LLM-Prompt: prompt text here | with pipes for newlines"
            const promptMatch = line.match(/LLM-Prompt:\s*(.+)$/i);
            if (promptMatch) {
                state.lastPrompt = promptMatch[1].replace(/ \| /g, '\n');
            }

            // Parse full LLM response JSON
            // Format: "LLM-Response: { | "text": "...", | "tool_calls": [...] | }"
            const responseMatch = line.match(/LLM-Response:\s*(.+)$/i);
            if (responseMatch) {
                // Convert pipe separators back to newlines for display
                state.currentReasoning = responseMatch[1].replace(/ \| /g, '\n');
            }

            // Parse hexagonalness scores - but NOT "Target hexagonalness" which is a config value
            // Match patterns like "Hexagonalness: 0.72" or "hexagonalness 0.72" but not "Target hexagonalness: 0.7"
            if (!line.toLowerCase().includes('target')) {
                const hexMatch = line.match(/hexagonalness[:\s]+([0-9.]+)/i);
                if (hexMatch) {
                    const score = parseFloat(hexMatch[1]);
                    if (!isNaN(score) && score > 0 && score <= 1) {
                        // Add to history if it's a new score for this iteration
                        const historyEntry = {
                            iteration: state.currentIteration,
                            score: score,
                            timestamp: Date.now(),
                        };

                        // Check if this iteration is already in history
                        const existing = state.history.find(h => h.iteration === state.currentIteration);
                        if (!existing && state.currentIteration > 0) {
                            state.history.push(historyEntry);
                        }

                        // Update best score only if we have a valid iteration
                        if (score > state.bestScore && state.currentIteration > 0) {
                            state.bestScore = score;
                        }
                    }
                }
            }

            // Track actions for action summary (avoid duplicates)
            // Use the full log line for important events
            if (!state.seenLogLines.has(line)) {
                state.seenLogLines.add(line);

                // Skip large data lines (prompt, response, usage) - they're not actions
                const isDataLine = line.includes('LLM-Prompt:') ||
                    line.includes('LLM-Response:') ||
                    line.includes('Prompt-Stats:') ||
                    line.includes('Usage:');

                if (!isDataLine) {
                    // Track significant events with full log line text
                    // Strip timestamp prefix if present (format: [HH:MM:SS])
                    const cleanLine = line.replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, '');

                    if (line.includes('Tool:') ||
                        line.includes('Iteration') ||
                        line.includes('AUTO-ACCEPT') ||
                        line.includes('MAX ITERATIONS') ||
                        line.includes('Agent completed') ||
                        line.includes('Optimization stopped') ||
                        line.includes('Extraction completed') ||
                        line.includes('Profile:') ||
                        line.includes('hexagonalness') ||
                        line.includes('tubercles') ||
                        line.includes('Starting') ||
                        line.includes('Trying profile') ||
                        line.includes('Best score')) {
                        // Add the full log line (without timestamp) to action summary
                        addAction(cleanLine);
                    }
                }
            }
        }
    }

    /**
     * Update LLM prompt/response display
     * @param {object} status - Status data from API
     */
    function updateLLMDisplay(status) {
        const logLines = status.log_lines || [];

        // Extract tool calls from log lines
        const toolCalls = [];
        const otherLogs = [];
        for (const line of logLines.slice(-30)) {  // Last 30 lines
            if (line.includes('Tool:')) {
                toolCalls.push(line);
            } else if (line.includes('AUTO-ACCEPT') || line.includes('MAX ITERATIONS') ||
                       line.includes('Agent completed') || line.includes('Optimization stopped')) {
                otherLogs.push(line);
            }
        }

        // Update prompt display with full prompt and statistics header
        const promptEl = document.getElementById('agentLastPrompt');
        if (promptEl) {
            // Build statistics header
            const statsLines = [
                `--- Prompt Statistics ---`,
                `Iteration: ${state.currentIteration}/${state.maxIterations}`,
                `Hexagonalness: ${state.bestScore.toFixed(3)}`,
                `Tubercles: ${state.currentTubercleCount || '-'}`,
                `ITC: ${state.currentITCCount || '-'}`,
                `Prompt Size: ${state.lastPromptSize > 0 ? formatBytes(state.lastPromptSize) : '-'}`,
                `-------------------------`,
                ``
            ].join('\n');

            if (state.lastPrompt) {
                // Show statistics header followed by full prompt
                promptEl.textContent = statsLines + state.lastPrompt;
            } else if (status.last_prompt) {
                promptEl.textContent = statsLines + status.last_prompt;
            } else {
                // Show just statistics if no prompt yet
                promptEl.textContent = statsLines + '(Waiting for first LLM call...)';
            }
        }

        // Update response display with LLM reasoning
        const responseEl = document.getElementById('agentLastResponse');
        if (responseEl) {
            if (state.currentReasoning) {
                // Show the LLM's reasoning for its parameter adjustments
                responseEl.textContent = state.currentReasoning;
            } else if (status.last_response) {
                responseEl.textContent = status.last_response;
            } else if (toolCalls.length > 0 || otherLogs.length > 0) {
                // Show recent tool calls as fallback
                const recentCalls = toolCalls.slice(-5).join('\n');
                const recentLogs = otherLogs.slice(-3).join('\n');
                responseEl.textContent = (recentCalls + '\n' + recentLogs).trim() || 'Waiting for agent actions...';
            } else {
                responseEl.textContent = 'Waiting for agent actions...';
            }
        }
    }

    /**
     * Refresh data display from MCP state after agent completes
     */
    async function refreshFromMCP() {
        try {
            const response = await fetch('/api/tools/state');
            const mcpState = await response.json();

            if (mcpState.tubercles && mcpState.tubercles.length > 0) {
                // Update overlay
                if (window.overlay) {
                    window.overlay.setData(mcpState.tubercles, mcpState.edges || []);
                }

                // Update data tables
                if (window.data) {
                    const statsResponse = await fetch('/api/tools/statistics');
                    const stats = await statsResponse.json();
                    window.data.setData(mcpState.tubercles, mcpState.edges || [], stats);
                }

                // Update sets module
                if (window.sets) {
                    window.sets.setCurrentData(mcpState.tubercles, mcpState.edges || []);
                    // Store the extraction parameters used
                    if (mcpState.parameters) {
                        window.sets.setCurrentParameters(mcpState.parameters);
                    }
                }
            }
        } catch (err) {
            console.log('Failed to refresh from MCP:', err);
        }
    }

    /**
     * Start polling for status updates
     */
    function startPolling() {
        if (state.pollingInterval) {
            clearInterval(state.pollingInterval);
        }
        state.pollingInterval = setInterval(pollStatus, config.pollIntervalMs);
        console.log('Started status polling');
    }

    /**
     * Stop polling for status updates
     */
    function stopPolling() {
        if (state.pollingInterval) {
            clearInterval(state.pollingInterval);
            state.pollingInterval = null;
        }
        console.log('Stopped status polling');
    }

    /**
     * Update UI elements based on current state
     */
    function updateUI() {
        // Use button IDs from workspace.html template
        const startBtn = document.getElementById('startAgentBtn');
        const stopBtn = document.getElementById('stopAgentBtn');
        const acceptBtn = document.getElementById('acceptBestBtn');
        const resetBtn = document.getElementById('resetAgentBtn');
        const spinner = document.getElementById('agentSpinner');

        if (startBtn) {
            startBtn.disabled = state.isRunning;
            startBtn.textContent = state.isRunning ? 'Running...' : 'Start Agent Extraction';
        }
        if (stopBtn) {
            stopBtn.disabled = !state.isRunning;
        }
        if (acceptBtn) {
            // Enable accept button when we have a best score and not running
            acceptBtn.disabled = state.isRunning || state.bestScore <= 0;
        }
        if (resetBtn) {
            // Reset button is always enabled unless running
            resetBtn.disabled = state.isRunning;
        }
        if (spinner) {
            spinner.style.display = state.isRunning ? 'inline-block' : 'none';
        }

        // Update configuration inputs (disable while running)
        const configInputs = [
            'agentProvider',
            'agentModel',
            'agentProfile',
            'agentTargetScore',
            'agentMaxIterations',
        ];
        configInputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = state.isRunning;
            }
        });
    }

    /**
     * Get current optimization state (for debugging/external access)
     */
    function getState() {
        return { ...state };
    }

    /**
     * Initialize the module
     */
    function init() {
        console.log('Initializing agent extraction module');

        // Load available providers
        loadProviders();

        // Bind event listeners for control buttons (using IDs from workspace.html)
        const startBtn = document.getElementById('startAgentBtn');
        if (startBtn) {
            startBtn.addEventListener('click', startOptimization);
        }

        const stopBtn = document.getElementById('stopAgentBtn');
        if (stopBtn) {
            stopBtn.addEventListener('click', stopOptimization);
        }

        const acceptBtn = document.getElementById('acceptBestBtn');
        if (acceptBtn) {
            acceptBtn.addEventListener('click', acceptBest);
        }

        const resetBtn = document.getElementById('resetAgentBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', reset);
        }

        // Provider select change - update model options
        const providerSelect = document.getElementById('agentProvider');
        if (providerSelect) {
            providerSelect.addEventListener('change', populateModelSelect);
        }

        // Use current params checkbox - toggle profile select
        const useCurrentParamsCheckbox = document.getElementById('agentUseCurrentParams');
        const profileSelect = document.getElementById('agentProfile');
        if (useCurrentParamsCheckbox && profileSelect) {
            useCurrentParamsCheckbox.addEventListener('change', () => {
                profileSelect.disabled = useCurrentParamsCheckbox.checked;
            });
        }

        // Read max iterations from input if available
        const maxIterInput = document.getElementById('agentMaxIterations');
        if (maxIterInput) {
            state.maxIterations = parseInt(maxIterInput.value, 10) || 30;
            maxIterInput.addEventListener('change', () => {
                state.maxIterations = parseInt(maxIterInput.value, 10) || 30;
            });
        }

        // Initialize collapsible sections
        initCollapsibles();

        // Bind copy button handlers
        const copyPromptBtn = document.getElementById('copyPromptBtn');
        if (copyPromptBtn) {
            copyPromptBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const promptEl = document.getElementById('agentLastPrompt');
                if (promptEl) {
                    copyToClipboard(promptEl.textContent, copyPromptBtn);
                }
            });
        }

        const copyResponseBtn = document.getElementById('copyResponseBtn');
        if (copyResponseBtn) {
            copyResponseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const responseEl = document.getElementById('agentLastResponse');
                if (responseEl) {
                    copyToClipboard(responseEl.textContent, copyResponseBtn);
                }
            });
        }

        const copyActionsBtn = document.getElementById('copyActionsBtn');
        if (copyActionsBtn) {
            copyActionsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const actionsEl = document.getElementById('agentActionSummary');
                if (actionsEl) {
                    copyToClipboard(actionsEl.textContent, copyActionsBtn);
                }
            });
        }

        const clearActionsBtn = document.getElementById('clearActionsBtn');
        if (clearActionsBtn) {
            clearActionsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                clearActions();
            });
        }

        // Initialize UI state
        updateUI();
        updateStatus('Ready');
        updateChart();
    }

    /**
     * Initialize collapsible sections for prompt/response display
     */
    function initCollapsibles() {
        const collapsibles = document.querySelectorAll('.agent-collapsible-header');
        collapsibles.forEach(header => {
            header.addEventListener('click', (e) => {
                // Don't toggle if clicking on a button
                if (e.target.closest('button')) {
                    return;
                }
                const parent = header.closest('.agent-collapsible');
                if (parent) {
                    parent.classList.toggle('collapsed');
                }
            });
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Redraw chart when theme colors change
    window.addEventListener('themeColorsChanged', () => {
        updateChart();
    });

    // Export public API
    return {
        startOptimization,
        stopOptimization,
        acceptBest,
        reset,
        updateStatus,
        updateChart,
        updateParams,
        updateCosts,
        pollStatus,
        getState,
        loadProviders,
    };
})();
