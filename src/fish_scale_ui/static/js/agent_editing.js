/**
 * Fish Scale Measurement UI - AgenticEdit Tab
 *
 * This module handles LLM agent-based pattern completion for tubercle detection.
 * The agent visually analyzes the image and adds missing tubercles to achieve
 * high hexagonalness and coverage.
 */

window.agentEditing = (function() {
    'use strict';

    // State for tracking editing progress
    const state = {
        isRunning: false,
        sessionId: null,
        currentIteration: 0,
        maxIterations: 30,
        plateauThreshold: 3,
        plateauCount: 0,
        initialTubercleCount: 0,
        currentTubercleCount: 0,
        initialHexagonalness: 0,
        currentHexagonalness: 0,
        initialCoverage: 0,
        currentCoverage: 0,
        currentPhase: null,
        lastPrompt: null,
        lastResponse: null,
        actionSummary: [],
        seenLogLines: new Set(),
        history: [],  // Array of { iteration, hexagonalness, coverage, tubercleCount }
        pollingInterval: null,
        providers: [],
        startTime: null,
        // Cost tracking
        costs: {
            provider: null,
            model: null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,
            previousCost: 0,
        },
        // Debug seed tracking
        debugSeeds: null,
        debugSeedRadius: 15,
        seedAnalysis: null,
    };

    // Configuration
    const config = {
        pollIntervalMs: 1000,
    };

    // Storage key for persisting user preferences
    const CONFIG_STORAGE_KEY = 'editAgentConfig';

    // Default configuration values
    const configDefaults = {
        provider: 'claude',
        model: '',  // Empty means use provider default
        maxIterations: 30,
        plateauThreshold: 3,
        autoConnect: true,
        autoConnectMethod: 'gabriel',
        debugSeeds: '',
        debugSeedRadius: 15,
        goal: 'hex_pattern',
        spotCount: 20,
        minSeparation: 30,
        logImages: false,
    };

    // Current saved configuration
    let savedConfig = { ...configDefaults };

    /**
     * Load configuration from localStorage and apply to UI
     */
    function loadConfig() {
        try {
            const stored = localStorage.getItem(CONFIG_STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                savedConfig = { ...configDefaults, ...parsed };
            }
        } catch (e) {
            console.warn('Failed to load edit agent config:', e);
        }

        // Apply to UI elements (after a short delay to ensure providers are loaded)
        setTimeout(() => {
            applyConfigToUI();
        }, 100);
    }

    /**
     * Apply saved configuration to UI elements
     */
    function applyConfigToUI() {
        const elements = {
            'editAgentProvider': savedConfig.provider,
            'editAgentMaxIterations': savedConfig.maxIterations,
            'editAgentPlateauThreshold': savedConfig.plateauThreshold,
            'editAgentAutoConnect': savedConfig.autoConnect,
            'editAgentAutoConnectMethod': savedConfig.autoConnectMethod,
            'editAgentDebugSeeds': savedConfig.debugSeeds,
            'editAgentDebugSeedRadius': savedConfig.debugSeedRadius,
            'editAgentGoal': savedConfig.goal,
            'editAgentSpotCount': savedConfig.spotCount,
            'editAgentMinSeparation': savedConfig.minSeparation,
            'editAgentLogImages': savedConfig.logImages,
        };

        for (const [id, value] of Object.entries(elements)) {
            const el = document.getElementById(id);
            if (!el) continue;

            if (el.type === 'checkbox') {
                el.checked = value;
            } else {
                el.value = value;
            }
        }

        // Trigger change events to update dependent UI
        const providerEl = document.getElementById('editAgentProvider');
        if (providerEl) {
            providerEl.dispatchEvent(new Event('change'));
            // After provider change populates models, set saved model
            setTimeout(() => {
                const modelEl = document.getElementById('editAgentModel');
                if (modelEl && savedConfig.model) {
                    modelEl.value = savedConfig.model;
                }
            }, 150);
        }

        // Show/hide debug seed radius row
        const debugSeedsEl = document.getElementById('editAgentDebugSeeds');
        const radiusRow = document.getElementById('editAgentDebugSeedRadiusRow');
        if (debugSeedsEl && radiusRow) {
            radiusRow.style.display = debugSeedsEl.value ? 'flex' : 'none';
        }

        // Show/hide bright spots params
        const goalEl = document.getElementById('editAgentGoal');
        const brightSpotsParams = document.getElementById('editAgentBrightSpotsParams');
        if (goalEl && brightSpotsParams) {
            brightSpotsParams.style.display = goalEl.value === 'bright_spots' ? 'block' : 'none';
        }
    }

    /**
     * Save current UI configuration to localStorage
     */
    function saveConfig() {
        const newConfig = {
            provider: document.getElementById('editAgentProvider')?.value || configDefaults.provider,
            model: document.getElementById('editAgentModel')?.value || '',
            maxIterations: parseInt(document.getElementById('editAgentMaxIterations')?.value, 10) || configDefaults.maxIterations,
            plateauThreshold: parseInt(document.getElementById('editAgentPlateauThreshold')?.value, 10) || configDefaults.plateauThreshold,
            autoConnect: document.getElementById('editAgentAutoConnect')?.checked ?? configDefaults.autoConnect,
            autoConnectMethod: document.getElementById('editAgentAutoConnectMethod')?.value || configDefaults.autoConnectMethod,
            debugSeeds: document.getElementById('editAgentDebugSeeds')?.value || '',
            debugSeedRadius: parseFloat(document.getElementById('editAgentDebugSeedRadius')?.value) || configDefaults.debugSeedRadius,
            goal: document.getElementById('editAgentGoal')?.value || configDefaults.goal,
            spotCount: parseInt(document.getElementById('editAgentSpotCount')?.value, 10) || configDefaults.spotCount,
            minSeparation: parseInt(document.getElementById('editAgentMinSeparation')?.value, 10) || configDefaults.minSeparation,
            logImages: document.getElementById('editAgentLogImages')?.checked || false,
        };

        savedConfig = newConfig;

        try {
            localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(savedConfig));
        } catch (e) {
            console.warn('Failed to save edit agent config:', e);
        }
    }

    /**
     * Log an event to the server (appears in Log tab)
     */
    async function logToServer(eventType, details = {}) {
        try {
            await fetch('/api/log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event_type: eventType,
                    details: details,
                }),
            });
        } catch (err) {
            console.error('Failed to log to server:', err);
        }
    }

    /**
     * Get theme colors from CSS custom properties.
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
            hexColor: '#4CAF50',     // Green for hexagonalness
            coverageColor: '#2196F3', // Blue for coverage
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
        const select = document.getElementById('editAgentProvider');
        if (!select) return;

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
     * Format cost for display
     */
    function formatCost(inputCost, outputCost) {
        if (inputCost === 0 && outputCost === 0) {
            return 'FREE';
        }
        const avgCost = (inputCost + outputCost) / 2;
        if (avgCost < 0.1) {
            return `$${avgCost.toFixed(3)}/M`;
        } else if (avgCost < 1) {
            return `$${avgCost.toFixed(2)}/M`;
        } else {
            return `$${avgCost.toFixed(1)}/M`;
        }
    }

    /**
     * Populate model select based on provider
     */
    function populateModelSelect() {
        const providerSelect = document.getElementById('editAgentProvider');
        const modelSelect = document.getElementById('editAgentModel');
        const modelInfoDiv = document.getElementById('editModelCostInfo');
        if (!providerSelect || !modelSelect) return;

        const providerName = providerSelect.value;
        const provider = state.providers.find(p => p.name === providerName);

        modelSelect.innerHTML = '';

        if (provider && provider.available_models && provider.available_models.length > 0) {
            const models = provider.available_models;

            if (models.length > 1) {
                // Group by vendor
                const byVendor = {};
                models.forEach(m => {
                    if (!byVendor[m.vendor]) byVendor[m.vendor] = [];
                    byVendor[m.vendor].push(m);
                });

                const vendorNames = {
                    'anthropic': 'Anthropic',
                    'openai': 'OpenAI',
                    'google': 'Google',
                    'mistralai': 'Mistral',
                    'qwen': 'Qwen',
                    'x-ai': 'xAI (Grok)',
                };

                const vendors = Object.keys(byVendor).sort();

                vendors.forEach(vendor => {
                    const optgroup = document.createElement('optgroup');
                    optgroup.label = vendorNames[vendor] || vendor;

                    byVendor[vendor].forEach(model => {
                        const opt = document.createElement('option');
                        opt.value = model.id;
                        const costStr = formatCost(model.input_cost, model.output_cost);
                        opt.textContent = `${model.name} [${costStr}]`;
                        opt.dataset.inputCost = model.input_cost;
                        opt.dataset.outputCost = model.output_cost;
                        opt.dataset.isFree = model.is_free;
                        if (model.id === provider.default_model) {
                            opt.textContent += ' (default)';
                        }
                        optgroup.appendChild(opt);
                    });

                    modelSelect.appendChild(optgroup);
                });

                modelSelect.value = provider.default_model;
            } else {
                const model = models[0];
                const opt = document.createElement('option');
                opt.value = model.id;
                const costStr = formatCost(model.input_cost, model.output_cost);
                opt.textContent = `${model.name} [${costStr}]`;
                opt.dataset.inputCost = model.input_cost;
                opt.dataset.outputCost = model.output_cost;
                modelSelect.appendChild(opt);
            }

            updateModelCostInfo();
        } else if (provider) {
            const defaultOpt = document.createElement('option');
            defaultOpt.value = '';
            defaultOpt.textContent = `Default (${provider.default_model})`;
            modelSelect.appendChild(defaultOpt);
        } else {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = '-- Select Provider First --';
            modelSelect.appendChild(opt);
        }
    }

    /**
     * Update model cost info display
     */
    function updateModelCostInfo() {
        const modelSelect = document.getElementById('editAgentModel');
        const infoDiv = document.getElementById('editModelCostInfo');
        if (!modelSelect || !infoDiv) return;

        const selectedOpt = modelSelect.selectedOptions[0];
        if (selectedOpt && selectedOpt.dataset.inputCost !== undefined) {
            const inputCost = parseFloat(selectedOpt.dataset.inputCost);
            const outputCost = parseFloat(selectedOpt.dataset.outputCost);

            if (inputCost === 0 && outputCost === 0) {
                infoDiv.innerHTML = '<span class="cost-free">FREE model - no API costs</span>';
            } else {
                infoDiv.innerHTML = `<span class="cost-label">Cost:</span> ` +
                    `<span class="cost-input">$${inputCost.toFixed(2)}</span> input / ` +
                    `<span class="cost-output">$${outputCost.toFixed(2)}</span> output per 1M tokens`;
            }
            infoDiv.style.display = 'block';
        } else {
            infoDiv.style.display = 'none';
        }
    }

    /**
     * Start the editing agent
     */
    async function startAgent() {
        if (state.isRunning) {
            console.warn('Agent already running');
            return;
        }

        // Get configuration
        const provider = document.getElementById('editAgentProvider')?.value;
        const model = document.getElementById('editAgentModel')?.value;
        const maxIterations = parseInt(document.getElementById('editAgentMaxIterations')?.value, 10) || 30;
        const plateauThreshold = parseInt(document.getElementById('editAgentPlateauThreshold')?.value, 10) || 3;
        const autoConnect = document.getElementById('editAgentAutoConnect')?.checked ?? true;
        const autoConnectMethod = document.getElementById('editAgentAutoConnectMethod')?.value || 'gabriel';
        const debugSeeds = document.getElementById('editAgentDebugSeeds')?.value || '';
        const debugSeedRadius = parseFloat(document.getElementById('editAgentDebugSeedRadius')?.value) || 15;
        const goal = document.getElementById('editAgentGoal')?.value || 'hex_pattern';
        const spotCount = parseInt(document.getElementById('editAgentSpotCount')?.value, 10) || 20;
        const minSeparation = parseInt(document.getElementById('editAgentMinSeparation')?.value, 10) || 30;
        const logImages = document.getElementById('editAgentLogImages')?.checked || false;

        // Check if provider is configured
        const providerInfo = state.providers.find(p => p.name === provider);
        if (!providerInfo || !providerInfo.configured) {
            window.app?.showToast(`Provider ${provider} not configured. Set ${providerInfo?.env_var} environment variable.`, 'error');
            return;
        }

        // Get current image info
        let currentImage = null;
        try {
            const imgResponse = await fetch('/api/current-image');
            currentImage = await imgResponse.json();
        } catch (err) {
            console.error('Failed to get current image:', err);
        }

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

        // Sync current set data to server before starting agent
        // This ensures the agent sees the current set, not stale data from a previous set
        try {
            const currentSet = window.sets?.getCurrentSet?.();
            if (currentSet) {
                const syncResponse = await fetch('/api/tools/state', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tubercles: currentSet.tubercles || [],
                        edges: currentSet.edges || [],
                        parameters: currentSet.parameters || {},
                    }),
                });
                const syncResult = await syncResponse.json();
                console.log('Synced current set to server:', syncResult);
            }
        } catch (err) {
            console.warn('Could not sync current set to server:', err);
            // Continue anyway - the agent will work with whatever server state exists
        }

        // Get current statistics for initial state
        let initialStats = { n_tubercles: 0, hexagonalness_score: 0 };
        try {
            const statsResponse = await fetch('/api/tools/statistics');
            initialStats = await statsResponse.json();
        } catch (err) {
            console.log('Could not get initial stats:', err);
        }

        console.log('Starting edit agent...');
        state.isRunning = true;
        state.currentIteration = 0;
        state.maxIterations = maxIterations;
        state.plateauThreshold = plateauThreshold;
        state.plateauCount = 0;
        state.initialTubercleCount = initialStats.n_tubercles || 0;
        state.currentTubercleCount = state.initialTubercleCount;
        state.initialHexagonalness = initialStats.hexagonalness_score || 0;
        state.currentHexagonalness = state.initialHexagonalness;
        state.initialCoverage = 0;  // Will be updated by agent
        state.currentCoverage = 0;
        state.history = [];
        state.actionSummary = [];
        state.seenLogLines = new Set();
        state.startTime = Date.now();
        state.costs = {
            provider: provider,
            model: model || providerInfo?.default_model || null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,
            previousCost: 0,
        };

        updateUI();
        updateStatus('Starting agent...');
        updateCosts();

        // Store debug seeds config in state
        state.debugSeeds = debugSeeds || null;
        state.debugSeedRadius = debugSeedRadius;
        state.seedAnalysis = null;

        // Show/hide seed analysis section based on whether seeds are enabled
        const seedAnalysisSection = document.getElementById('editSeedAnalysisSection');
        if (seedAnalysisSection) {
            seedAnalysisSection.style.display = debugSeeds ? 'block' : 'none';
        }

        try {
            const response = await fetch('/api/agent/edit/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    provider: provider,
                    model: model || undefined,
                    max_iterations: maxIterations,
                    plateau_threshold: plateauThreshold,
                    auto_connect: autoConnect,
                    auto_connect_method: autoConnectMethod,
                    debug_seeds: debugSeeds || undefined,
                    debug_seed_radius: debugSeeds ? debugSeedRadius : undefined,
                    goal: goal,
                    spot_count: goal === 'bright_spots' ? spotCount : undefined,
                    min_separation: goal === 'bright_spots' ? minSeparation : undefined,
                    log_images: logImages,
                    verbose: true,
                    image_path: currentImage?.path || currentImage?.web_path,
                    calibration: calibration.um_per_px,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app?.showToast(result.error, 'error');
                logToServer('edit_agent_start_error', { error: result.error });
                state.isRunning = false;
                updateUI();
                updateStatus('Failed to start');
                return;
            }

            state.sessionId = result.session_id;
            console.log('Edit agent started, session:', state.sessionId);
            window.app?.showToast('Edit agent started', 'success');
            logToServer('edit_agent_started', { session_id: state.sessionId, provider });
            updateStatus('Running...');
            addAction('Started pattern completion agent');

            startPolling();

        } catch (err) {
            console.error('Failed to start edit agent:', err);
            window.app?.showToast(`Failed to start agent: ${err.message}`, 'error');
            logToServer('edit_agent_start_error', { error: err.message });
            state.isRunning = false;
            updateUI();
            updateStatus('Error starting agent');
        }
    }

    /**
     * Stop the agent
     */
    async function stopAgent() {
        if (!state.isRunning || !state.sessionId) {
            console.warn('No agent running');
            return;
        }

        console.log('Stopping edit agent...');
        updateStatus('Stopping...');

        try {
            const response = await fetch(`/api/agent/edit/stop/${state.sessionId}`, {
                method: 'POST',
            });

            const result = await response.json();

            if (result.error) {
                console.error('Stop error:', result.error);
                logToServer('edit_agent_stop_error', { error: result.error });
            }

            state.isRunning = false;
            stopPolling();
            updateUI();
            updateStatus('Stopped by user');
            addAction('Agent stopped by user');
            window.app?.showToast('Edit agent stopped', 'info');

            // Refresh overlay
            refreshOverlay();

        } catch (err) {
            console.error('Failed to stop agent:', err);
            window.app?.showToast(`Failed to stop agent: ${err.message}`, 'error');
            logToServer('edit_agent_stop_error', { error: err.message });
        }
    }

    /**
     * Reset state
     */
    function reset() {
        console.log('Resetting edit agent state');

        stopPolling();

        state.isRunning = false;
        state.sessionId = null;
        state.currentIteration = 0;
        state.plateauCount = 0;
        state.initialTubercleCount = 0;
        state.currentTubercleCount = 0;
        state.initialHexagonalness = 0;
        state.currentHexagonalness = 0;
        state.initialCoverage = 0;
        state.currentCoverage = 0;
        state.currentPhase = null;
        state.lastPrompt = null;
        state.lastResponse = null;
        state.actionSummary = [];
        state.seenLogLines = new Set();
        state.history = [];
        state.startTime = null;
        state.costs = {
            provider: null,
            model: null,
            inputTokens: 0,
            outputTokens: 0,
            estimatedCost: 0,
            lastStepCost: 0,
            previousCost: 0,
        };
        state.debugSeeds = null;
        state.debugSeedRadius = 15;
        state.seedAnalysis = null;

        updateUI();
        updateChart();
        updateStatus('Ready');
        updateCosts();
        updateLLMDisplay();
        updateActionSummary();
        updateSeedAnalysis();
    }

    /**
     * Accept the result (just shows toast, data is already in place)
     */
    function acceptResult() {
        if (state.isRunning) {
            window.app?.showToast('Agent is still running', 'warning');
            return;
        }

        const delta = state.currentTubercleCount - state.initialTubercleCount;
        window.app?.showToast(
            `Accepted result: ${state.currentTubercleCount} tubercles (${delta >= 0 ? '+' : ''}${delta}), ` +
            `hexagonalness ${state.currentHexagonalness.toFixed(3)}`,
            'success'
        );
    }

    /**
     * Clear all annotations (tubercles and connections) from current set
     */
    async function clearAnnotations() {
        if (state.isRunning) {
            window.app?.showToast('Cannot clear while agent is running', 'warning');
            return;
        }

        const currentCount = state.currentTubercleCount || window.overlay?.getTubercles()?.length || 0;
        if (currentCount === 0) {
            window.app?.showToast('No annotations to clear', 'info');
            return;
        }

        // Confirm with user
        if (!confirm(`Clear all ${currentCount} tubercles and their connections?`)) {
            return;
        }

        try {
            // Clear server state
            const response = await fetch('/api/tools/state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tubercles: [],
                    edges: [],
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to clear server state');
            }

            // Clear overlay using clear() for complete visual reset
            if (window.overlay) {
                window.overlay.clear();
            }

            // Clear editor data (maintains its own copy)
            if (window.editor) {
                window.editor.setData([], []);
            }

            // Clear current set data
            if (window.sets) {
                window.sets.setCurrentData([], []);
                window.sets.markDirty();
            }

            // Clear data panel
            if (window.data) {
                window.data.clear();
            }

            // Clear undo manager
            if (window.undoManager) {
                window.undoManager.clear();
            }

            // Reset state counters
            state.currentTubercleCount = 0;
            state.initialTubercleCount = 0;
            state.currentHexagonalness = 0;
            state.initialHexagonalness = 0;
            state.currentCoverage = 0;
            state.initialCoverage = 0;

            updateStatus('Annotations cleared');
            updateUI();
            addAction('Cleared all annotations');
            window.app?.showToast(`Cleared ${currentCount} tubercles`, 'success');
            logToServer('edit_agent_clear_annotations', { cleared_count: currentCount });

        } catch (err) {
            console.error('Failed to clear annotations:', err);
            window.app?.showToast(`Failed to clear: ${err.message}`, 'error');
        }
    }

    /**
     * Format elapsed time as MM:SS or HH:MM:SS
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
     * Format bytes as human readable
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Copy to clipboard
     */
    async function copyToClipboard(text, button) {
        try {
            await navigator.clipboard.writeText(text);
            if (button) {
                button.classList.add('copied');
                const originalText = button.innerHTML;
                button.innerHTML = 'Copied!';
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
     * Add action to summary
     */
    function addAction(action) {
        if (!state.startTime) state.startTime = Date.now();

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
     * Update action summary display
     */
    function updateActionSummary() {
        const summaryEl = document.getElementById('editAgentActionLog');
        if (!summaryEl) return;

        if (state.actionSummary.length === 0) {
            summaryEl.value = 'No actions yet.';
            return;
        }

        const lines = state.actionSummary.map(a => `[${a.elapsed}s] ${a.action}`);
        summaryEl.value = lines.join('\n');
        summaryEl.scrollTop = summaryEl.scrollHeight;
    }

    /**
     * Clear action summary
     */
    function clearActions() {
        state.actionSummary = [];
        updateActionSummary();
    }

    /**
     * Update status display
     */
    function updateStatus(message) {
        const stateEl = document.getElementById('editAgentState');
        const phaseEl = document.getElementById('editAgentPhase');
        const iterEl = document.getElementById('editAgentIteration');
        const tubEl = document.getElementById('editAgentTubercleCount');
        const hexEl = document.getElementById('editAgentHexagonalness');
        const covEl = document.getElementById('editAgentCoverage');
        const elapsedEl = document.getElementById('editAgentElapsed');
        const plateauEl = document.getElementById('editAgentPlateau');

        if (stateEl) {
            if (state.isRunning) {
                stateEl.textContent = 'Running';
                stateEl.className = 'agent-status-value status-running';
            } else if (state.currentPhase === 'complete') {
                stateEl.textContent = 'Completed';
                stateEl.className = 'agent-status-value status-completed';
            } else if (state.sessionId && state.currentIteration > 0) {
                // Had a session that ended (stopped or error)
                stateEl.textContent = 'Stopped';
                stateEl.className = 'agent-status-value status-stopped';
            } else {
                stateEl.textContent = 'Idle';
                stateEl.className = 'agent-status-value';
            }
        }

        if (phaseEl) {
            phaseEl.textContent = state.currentPhase || '-';
        }

        if (iterEl) {
            iterEl.textContent = `${state.currentIteration}/${state.maxIterations}`;
        }

        if (tubEl) {
            const delta = state.currentTubercleCount - state.initialTubercleCount;
            const deltaStr = delta >= 0 ? `+${delta}` : `${delta}`;
            tubEl.textContent = `${state.currentTubercleCount} (${deltaStr})`;
        }

        if (hexEl) {
            hexEl.textContent = state.currentHexagonalness.toFixed(3);
        }

        if (covEl) {
            covEl.textContent = `${state.currentCoverage.toFixed(0)}%`;
        }

        if (elapsedEl && state.startTime) {
            const elapsed = Date.now() - state.startTime;
            elapsedEl.textContent = formatElapsed(elapsed);
        } else if (elapsedEl) {
            elapsedEl.textContent = '0:00';
        }

        if (plateauEl) {
            plateauEl.textContent = `${state.plateauCount}/${state.plateauThreshold}`;
        }
    }

    /**
     * Update cost display
     */
    function updateCosts() {
        const modelEl = document.getElementById('editAgentCostModel');
        const inputEl = document.getElementById('editAgentCostInputTokens');
        const outputEl = document.getElementById('editAgentCostOutputTokens');
        const estimateEl = document.getElementById('editAgentCostEstimate');
        const lastStepEl = document.getElementById('editAgentCostLastStep');

        if (modelEl) {
            if (state.costs.model) {
                modelEl.textContent = state.costs.model;
            } else if (state.costs.provider) {
                modelEl.textContent = `${state.costs.provider} (default)`;
            } else {
                modelEl.textContent = '-';
            }
        }

        if (inputEl) {
            inputEl.textContent = state.costs.inputTokens.toLocaleString();
        }

        if (outputEl) {
            outputEl.textContent = state.costs.outputTokens.toLocaleString();
        }

        if (estimateEl) {
            if (state.costs.estimatedCost > 0) {
                estimateEl.textContent = `$${state.costs.estimatedCost.toFixed(4)}`;
            } else {
                estimateEl.textContent = '$0.0000';
            }
        }

        if (lastStepEl) {
            if (state.costs.lastStepCost > 0) {
                lastStepEl.textContent = `$${state.costs.lastStepCost.toFixed(4)}`;
            } else {
                lastStepEl.textContent = '$0.0000';
            }
        }
    }

    /**
     * Update progress chart
     */
    function updateChart() {
        const canvas = document.getElementById('editAgentChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const colors = getThemeColors();

        // Clear
        ctx.fillStyle = colors.background;
        ctx.fillRect(0, 0, width, height);

        if (state.history.length === 0) {
            ctx.fillStyle = colors.textDim;
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Progress chart will appear during editing', width / 2, height / 2);
            return;
        }

        const padding = { top: 20, right: 20, bottom: 30, left: 50 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;

        // Draw grid
        ctx.strokeStyle = colors.grid;
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartHeight * i / 4);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(width - padding.right, y);
            ctx.stroke();
        }

        // Y-axis labels
        ctx.fillStyle = colors.text;
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
            const value = 1 - i / 4;
            const y = padding.top + (chartHeight * i / 4);
            ctx.fillText(value.toFixed(2), padding.left - 5, y + 3);
        }

        // X-axis label
        ctx.textAlign = 'center';
        ctx.fillText('Iteration', width / 2, height - 5);

        const maxX = Math.max(state.maxIterations, state.history.length);

        // Draw hexagonalness line (green)
        ctx.strokeStyle = colors.hexColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        state.history.forEach((point, i) => {
            const x = padding.left + (point.iteration / maxX) * chartWidth;
            const y = padding.top + chartHeight * (1 - point.hexagonalness);
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        // Draw coverage line (blue)
        ctx.strokeStyle = colors.coverageColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        state.history.forEach((point, i) => {
            const x = padding.left + (point.iteration / maxX) * chartWidth;
            const y = padding.top + chartHeight * (1 - (point.coverage / 100));
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        // Legend
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillStyle = colors.hexColor;
        ctx.fillText('Hexagonalness', padding.left + 5, padding.top + 12);
        ctx.fillStyle = colors.coverageColor;
        ctx.fillText('Coverage', padding.left + 100, padding.top + 12);
    }

    /**
     * Update LLM prompt/response display
     */
    function updateLLMDisplay() {
        const promptEl = document.getElementById('editAgentPrompt');
        const responseEl = document.getElementById('editAgentResponse');

        if (promptEl) {
            promptEl.textContent = state.lastPrompt || '(Waiting for first LLM call...)';
        }

        if (responseEl) {
            responseEl.textContent = state.lastResponse || '(Waiting for agent actions...)';
        }
    }

    /**
     * Update debug seed analysis display
     */
    function updateSeedAnalysis() {
        const section = document.getElementById('editSeedAnalysisSection');
        const diagnosisEl = document.getElementById('seedAnalysisDiagnosis');
        const confidenceEl = document.getElementById('seedAnalysisConfidence');
        const seedsPlacedEl = document.getElementById('seedAnalysisSeedsPlaced');
        const meanErrorEl = document.getElementById('seedAnalysisMeanError');
        const offsetEl = document.getElementById('seedAnalysisOffset');
        const overlapsEl = document.getElementById('seedAnalysisOverlaps');
        const gridDetectedEl = document.getElementById('seedAnalysisGridDetected');
        const reportEl = document.getElementById('seedAnalysisReport');

        // Hide section if no debug seeds enabled
        if (!state.debugSeeds) {
            if (section) section.style.display = 'none';
            return;
        }

        // Show section when debug seeds are enabled
        if (section) section.style.display = 'block';

        const analysis = state.seedAnalysis;
        if (!analysis) {
            // Clear/reset to waiting state
            if (diagnosisEl) diagnosisEl.textContent = '(Waiting for analysis...)';
            if (confidenceEl) confidenceEl.textContent = '-';
            if (seedsPlacedEl) seedsPlacedEl.textContent = '-';
            if (meanErrorEl) meanErrorEl.textContent = '-';
            if (offsetEl) offsetEl.textContent = '-';
            if (overlapsEl) overlapsEl.textContent = '-';
            if (gridDetectedEl) gridDetectedEl.textContent = '-';
            if (reportEl) reportEl.textContent = '(Analysis will appear after agent completion...)';
            return;
        }

        // Populate summary fields
        if (diagnosisEl) {
            diagnosisEl.textContent = analysis.diagnosis || 'No diagnosis';
            // Color code based on confidence
            const confidence = analysis.confidence || '';
            if (confidence.toLowerCase() === 'high') {
                diagnosisEl.style.color = '#4CAF50';
            } else if (confidence.toLowerCase() === 'medium') {
                diagnosisEl.style.color = '#FFC107';
            } else {
                diagnosisEl.style.color = '';
            }
        }

        if (confidenceEl) {
            confidenceEl.textContent = analysis.confidence || '-';
        }

        if (seedsPlacedEl) {
            seedsPlacedEl.textContent = analysis.seeds_placed !== undefined ? analysis.seeds_placed : '-';
        }

        if (meanErrorEl) {
            const err = analysis.mean_position_error;
            meanErrorEl.textContent = err !== null && err !== undefined ? `${err.toFixed(1)} px` : '-';
        }

        if (offsetEl) {
            const sysOffset = analysis.systematic_offset;
            if (sysOffset && (sysOffset[0] !== 0 || sysOffset[1] !== 0)) {
                offsetEl.textContent = `(${sysOffset[0] >= 0 ? '+' : ''}${sysOffset[0].toFixed(1)}, ${sysOffset[1] >= 0 ? '+' : ''}${sysOffset[1].toFixed(1)}) px`;
            } else {
                offsetEl.textContent = 'None detected';
            }
        }

        if (overlapsEl) {
            const overlaps = analysis.tubercles_overlapping_seeds;
            overlapsEl.textContent = overlaps !== undefined ? overlaps : '-';
            if (overlaps > 0) {
                overlapsEl.style.color = '#f44336';
            } else {
                overlapsEl.style.color = '#4CAF50';
            }
        }

        if (gridDetectedEl) {
            const isGrid = analysis.is_regular_grid;
            gridDetectedEl.textContent = isGrid ? 'YES (possible hallucination)' : 'No';
            if (isGrid) {
                gridDetectedEl.style.color = '#f44336';
            } else {
                gridDetectedEl.style.color = '#4CAF50';
            }
        }

        // Populate full report
        if (reportEl) {
            reportEl.textContent = analysis.report || JSON.stringify(analysis, null, 2);
        }
    }

    /**
     * Parse log lines for structured data
     */
    function parseLogLines(logLines) {
        for (const line of logLines) {
            // Skip already seen lines
            if (state.seenLogLines.has(line)) continue;
            state.seenLogLines.add(line);

            // Parse LLM prompt
            if (line.includes('LLM-Prompt:')) {
                const match = line.match(/LLM-Prompt:\s*(.+)$/i);
                if (match) {
                    state.lastPrompt = match[1].replace(/ \| /g, '\n');
                }
                continue;
            }

            // Parse LLM response
            if (line.includes('LLM-Response:')) {
                const match = line.match(/LLM-Response:\s*(.+)$/i);
                if (match) {
                    state.lastResponse = match[1].replace(/ \| /g, '\n');
                }
                continue;
            }

            // Parse usage
            const usageMatch = line.match(/Usage:\s*(\d+)\s*input,\s*(\d+)\s*output,\s*\$([0-9.]+)/i);
            if (usageMatch) {
                const newCost = parseFloat(usageMatch[3]);
                if (state.costs.estimatedCost > 0) {
                    state.costs.lastStepCost = newCost - state.costs.previousCost;
                }
                state.costs.previousCost = state.costs.estimatedCost;
                state.costs.inputTokens = parseInt(usageMatch[1], 10);
                state.costs.outputTokens = parseInt(usageMatch[2], 10);
                state.costs.estimatedCost = newCost;
                continue;
            }

            // Track actions
            const cleanLine = line.replace(/^\[\d{2}:\d{2}:\d{2}\]\s*/, '');
            if (line.includes('Tool:') ||
                line.includes('Added tubercle') ||
                line.includes('Deleted tubercle') ||
                line.includes('State:') ||
                line.includes('AUTO-STOP') ||
                line.includes('EDITING COMPLETE') ||
                line.includes('Finished:') ||
                line.includes('Screenshot')) {
                addAction(cleanLine);
            }
        }
    }

    /**
     * Poll for status updates
     */
    async function pollStatus() {
        if (!state.isRunning || !state.sessionId) return;

        try {
            const response = await fetch(`/api/agent/edit/status/${state.sessionId}`);

            if (!response.ok) {
                if (response.status === 404) {
                    console.log('Edit agent session not found');
                    state.isRunning = false;
                    stopPolling();
                    updateUI();
                    updateStatus('Session ended');
                    return;
                }
                console.log('Status request failed:', response.status);
                return;
            }

            const status = await response.json();

            // Update state from status
            if (status.iteration !== undefined) {
                state.currentIteration = status.iteration;
            }
            if (status.hexagonalness !== undefined) {
                state.currentHexagonalness = status.hexagonalness;
            }
            if (status.coverage_percent !== undefined) {
                state.currentCoverage = status.coverage_percent;
            }
            if (status.tubercles !== undefined) {
                state.currentTubercleCount = status.tubercles;
            }
            if (status.plateau_count !== undefined) {
                state.plateauCount = status.plateau_count;
            }
            if (status.phase !== undefined) {
                state.currentPhase = status.phase;
            }
            if (status.input_tokens !== undefined) {
                state.costs.inputTokens = status.input_tokens;
            }
            if (status.output_tokens !== undefined) {
                state.costs.outputTokens = status.output_tokens;
            }
            if (status.cost_usd !== undefined) {
                if (state.costs.estimatedCost > 0) {
                    state.costs.lastStepCost = status.cost_usd - state.costs.previousCost;
                }
                state.costs.previousCost = state.costs.estimatedCost;
                state.costs.estimatedCost = status.cost_usd;
            }
            if (status.last_prompt) {
                state.lastPrompt = status.last_prompt;
            }
            if (status.last_response) {
                state.lastResponse = status.last_response;
            }
            if (status.model) {
                state.costs.model = status.model;
            }
            if (status.seed_analysis) {
                state.seedAnalysis = status.seed_analysis;
            }

            // Add to history
            if (state.currentIteration > 0) {
                const existing = state.history.find(h => h.iteration === state.currentIteration);
                if (!existing) {
                    state.history.push({
                        iteration: state.currentIteration,
                        hexagonalness: state.currentHexagonalness,
                        coverage: state.currentCoverage,
                        tubercleCount: state.currentTubercleCount,
                    });
                }
            }

            // Parse log lines
            if (status.log_lines) {
                parseLogLines(status.log_lines);
            }

            // Update UI
            updateStatus();
            updateChart();
            updateCosts();
            updateLLMDisplay();
            updateSeedAnalysis();

            // Refresh overlay periodically
            if (state.currentIteration % 3 === 0 || status.action === 'add_tubercle') {
                refreshOverlay();
            }

            // Check for completion
            if (status.state === 'completed') {
                state.isRunning = false;
                stopPolling();
                updateUI();
                addAction(`Completed: ${status.message || 'Pattern completion finished'}`);
                window.app?.showToast('Edit agent completed', 'success');
                logToServer('edit_agent_completed', {
                    session_id: state.sessionId,
                    tubercles: state.currentTubercleCount,
                    hexagonalness: state.currentHexagonalness,
                    iterations: state.currentIteration,
                    seed_analysis: state.seedAnalysis ? true : false,
                });
                refreshOverlay();

                // Expand seed analysis section if it has results
                if (state.seedAnalysis) {
                    const analysisSection = document.getElementById('editSeedAnalysisSection');
                    if (analysisSection) {
                        analysisSection.classList.remove('collapsed');
                    }
                }
            } else if (status.state === 'failed' || status.state === 'error') {
                state.isRunning = false;
                stopPolling();
                updateUI();
                const errorMsg = status.error || 'Unknown error';
                addAction(`Error: ${errorMsg}`);
                window.app?.showToast(`Agent error: ${errorMsg}`, 'error');
                logToServer('edit_agent_error', {
                    session_id: state.sessionId,
                    error: errorMsg,
                    return_code: status.return_code,
                    iteration: state.currentIteration,
                });
                refreshOverlay();
            } else if (status.state === 'stopped') {
                state.isRunning = false;
                stopPolling();
                updateUI();
                addAction('Agent stopped');
                logToServer('edit_agent_stopped', { session_id: state.sessionId });
                refreshOverlay();
            }

        } catch (err) {
            console.log('Error polling status:', err);
        }
    }

    /**
     * Refresh overlay from server state
     */
    async function refreshOverlay() {
        try {
            const response = await fetch('/api/tools/state');
            const mcpState = await response.json();

            const tubercles = mcpState.tubercles || [];
            const edges = mcpState.edges || [];

            if (tubercles) {
                window.overlay?.setData(tubercles, edges);
            }

            // Sync to current set and mark dirty
            if (window.sets) {
                window.sets.setCurrentData(tubercles, edges);
                if (tubercles.length > 0 || edges.length > 0) {
                    window.sets.markDirty();
                }
            }

            // Also update data panel
            if (window.data) {
                const statsResponse = await fetch('/api/tools/statistics');
                const stats = await statsResponse.json();
                window.data.setData(tubercles, edges, stats);
            }
        } catch (err) {
            console.log('Failed to refresh overlay:', err);
        }
    }

    /**
     * Start polling
     */
    function startPolling() {
        if (state.pollingInterval) {
            clearInterval(state.pollingInterval);
        }
        state.pollingInterval = setInterval(pollStatus, config.pollIntervalMs);
        console.log('Started edit agent status polling');
    }

    /**
     * Stop polling
     */
    function stopPolling() {
        if (state.pollingInterval) {
            clearInterval(state.pollingInterval);
            state.pollingInterval = null;
        }
        console.log('Stopped edit agent status polling');
    }

    /**
     * Update UI elements
     */
    function updateUI() {
        const startBtn = document.getElementById('startEditAgentBtn');
        const stopBtn = document.getElementById('stopEditAgentBtn');
        const resetBtn = document.getElementById('resetEditAgentBtn');
        const clearBtn = document.getElementById('clearEditAnnotationsBtn');
        const acceptBtn = document.getElementById('acceptEditResultBtn');

        if (startBtn) {
            startBtn.disabled = state.isRunning;
        }
        if (stopBtn) {
            stopBtn.disabled = !state.isRunning;
        }
        if (resetBtn) {
            resetBtn.disabled = state.isRunning;
        }
        if (clearBtn) {
            clearBtn.disabled = state.isRunning;
        }
        if (acceptBtn) {
            acceptBtn.disabled = state.isRunning || state.currentTubercleCount === 0;
        }

        // Disable config inputs while running
        const configInputs = [
            'editAgentProvider',
            'editAgentModel',
            'editAgentMaxIterations',
            'editAgentPlateauThreshold',
            'editAgentAutoConnect',
            'editAgentAutoConnectMethod',
            'editAgentGoal',
            'editAgentSpotCount',
            'editAgentMinSeparation',
            'editAgentLogImages',
        ];
        configInputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.disabled = state.isRunning;
        });
    }

    /**
     * Initialize collapsible sections
     */
    function initCollapsibles() {
        // Scope to agent-editing tab to avoid conflict with agent_extraction.js
        const tabContainer = document.querySelector('.tab-pane[data-tab="agent-editing"]');
        if (!tabContainer) return;

        const STORAGE_KEY = 'editAgentSectionCollapsed';
        let collapsedSections = {};

        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                collapsedSections = JSON.parse(stored);
            }
        } catch (e) {
            console.warn('Failed to load section collapse state:', e);
        }

        function saveCollapsedState() {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(collapsedSections));
            } catch (e) {
                console.warn('Failed to save section collapse state:', e);
            }
        }

        // Section header click handlers (scoped to this tab)
        const sectionHeaders = tabContainer.querySelectorAll('.edit-agent-section-header');
        sectionHeaders.forEach(header => {
            const section = header.closest('.edit-agent-section');
            const sectionId = section?.dataset.section;

            if (!sectionId) return;

            // Apply saved state
            if (collapsedSections[sectionId]) {
                section.classList.add('collapsed');
            }

            header.addEventListener('click', () => {
                section.classList.toggle('collapsed');
                collapsedSections[sectionId] = section.classList.contains('collapsed');
                saveCollapsedState();
            });
        });

        // Inner collapsibles (prompt/response) - scoped to this tab
        const innerHeaders = tabContainer.querySelectorAll('.edit-agent-collapsible-header');
        innerHeaders.forEach(header => {
            header.addEventListener('click', (e) => {
                if (e.target.closest('button')) return;
                const parent = header.closest('.edit-agent-collapsible');
                if (parent) parent.classList.toggle('collapsed');
            });
        });
    }

    /**
     * Initialize the module
     */
    function init() {
        console.log('Initializing AgenticEdit module');

        loadProviders();

        // Load saved configuration after providers are loaded
        loadConfig();

        // Button handlers
        document.getElementById('startEditAgentBtn')?.addEventListener('click', startAgent);
        document.getElementById('stopEditAgentBtn')?.addEventListener('click', stopAgent);
        document.getElementById('resetEditAgentBtn')?.addEventListener('click', reset);
        document.getElementById('clearEditAnnotationsBtn')?.addEventListener('click', clearAnnotations);
        document.getElementById('acceptEditResultBtn')?.addEventListener('click', acceptResult);

        // Provider change - also save config
        document.getElementById('editAgentProvider')?.addEventListener('change', () => {
            populateModelSelect();
            saveConfig();
        });

        // Model change - also save config
        document.getElementById('editAgentModel')?.addEventListener('change', () => {
            updateModelCostInfo();
            saveConfig();
        });

        // Config inputs that should trigger saveConfig on change
        const configInputIds = [
            'editAgentMaxIterations',
            'editAgentPlateauThreshold',
            'editAgentAutoConnect',
            'editAgentAutoConnectMethod',
            'editAgentDebugSeedRadius',
            'editAgentSpotCount',
            'editAgentMinSeparation',
            'editAgentLogImages',
        ];
        configInputIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', saveConfig);
                // For number inputs, also save on input (as user types)
                if (el.type === 'number') {
                    el.addEventListener('input', saveConfig);
                }
            }
        });

        // Copy buttons
        document.getElementById('copyEditPromptBtn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = document.getElementById('editAgentPrompt');
            if (el) copyToClipboard(el.textContent, e.target);
        });

        document.getElementById('copyEditResponseBtn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = document.getElementById('editAgentResponse');
            if (el) copyToClipboard(el.textContent, e.target);
        });

        document.getElementById('copyEditActionsBtn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = document.getElementById('editAgentActionLog');
            if (el) copyToClipboard(el.value, e.target);
        });

        document.getElementById('clearEditActionsBtn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            clearActions();
        });

        // Debug seeds dropdown change - show/hide radius input and save config
        document.getElementById('editAgentDebugSeeds')?.addEventListener('change', (e) => {
            const radiusRow = document.getElementById('editAgentDebugSeedRadiusRow');
            if (radiusRow) {
                radiusRow.style.display = e.target.value ? 'flex' : 'none';
            }
            saveConfig();
        });

        // Goal dropdown change - show/hide bright spots parameters and save config
        document.getElementById('editAgentGoal')?.addEventListener('change', (e) => {
            const brightSpotsParams = document.getElementById('editAgentBrightSpotsParams');
            if (brightSpotsParams) {
                brightSpotsParams.style.display = e.target.value === 'bright_spots' ? 'block' : 'none';
            }
            saveConfig();
        });

        // Copy button for seed analysis
        document.getElementById('copySeedAnalysisBtn')?.addEventListener('click', (e) => {
            e.stopPropagation();
            const el = document.getElementById('seedAnalysisReport');
            if (el) copyToClipboard(el.textContent, e.target);
        });

        // Initialize collapsibles
        initCollapsibles();

        // Initialize UI
        updateUI();
        updateStatus('Ready');
        updateChart();
        updateSeedAnalysis();
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    // Export public API
    return {
        startAgent,
        stopAgent,
        reset,
        clearAnnotations,
        acceptResult,
        getState: () => ({ ...state }),
        loadProviders,
    };
})();
