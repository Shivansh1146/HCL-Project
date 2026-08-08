/**
 * components/severity.js — Reusable Severity Component Library
 * 
 * Provides consistent rendering of severity indicators across the application.
 * All severity styling uses centralized CSS variables from the design system.
 */

/**
 * Renders a severity badge with appropriate styling
 * @param {string} severity - 'high', 'medium', 'low'
 * @param {Object} options - Additional options
 * @returns {string} HTML string for the badge
 */
export function renderSeverityBadge(severity, options = {}) {
    const { text = null, showRiskLabel = true } = options;
    const displayText = text || severity.toUpperCase();
    const riskLabel = showRiskLabel ? ' RISK' : '';
    
    const badgeClass = `badge-severity-${severity}`;
    
    return `<span class="badge ${badgeClass}" style="font-size:0.65rem;">${displayText}${riskLabel}</span>`;
}

/**
 * Renders a severity dot indicator
 * @param {string} severity - 'high', 'medium', 'low'
 * @returns {string} HTML string for the dot
 */
export function renderSeverityDot(severity) {
    const dotClass = `severity-dot severity-dot-${severity}`;
    return `<span class="${dotClass}"></span>`;
}

/**
 * Renders a severity progress bar segment
 * @param {string} severity - 'high', 'medium', 'low'
 * @param {number} percentage - Width percentage
 * @param {number} count - Count for tooltip
 * @returns {string} HTML string for the progress segment
 */
export function renderSeverityProgress(severity, percentage, count) {
    const fillClass = `progress-fill-${severity}`;
    return `<div style="width:${percentage}%;height:100%;" class="${fillClass}" title="${severity}: ${count}"></div>`;
}

/**
 * Renders a complete severity indicator with dot and label
 * @param {string} severity - 'high', 'medium', 'low'
 * @param {number} count - The count value
 * @param {string} label - Custom label (optional)
 * @returns {string} HTML string for the indicator
 */
export function renderSeverityIndicator(severity, count, label = null) {
    const displayLabel = label || severity.charAt(0).toUpperCase() + severity.slice(1);
    const dot = renderSeverityDot(severity);
    
    return `
        <div class="severity-indicator">
            ${dot}
            <span>${displayLabel}: <strong>${count}</strong></span>
        </div>
    `;
}

/**
 * Renders a severity distribution bar
 * @param {Object} distribution - { high: number, medium: number, low: number }
 * @param {Object} options - Additional options
 * @returns {string} HTML string for the distribution bar
 */
export function renderSeverityDistribution(distribution, options = {}) {
    const { height = '12px', showLabels = true, borderRadius = '6px' } = options;
    
    const total = (distribution.high || 0) + (distribution.medium || 0) + (distribution.low || 0) || 1;
    const highPct = Math.round(((distribution.high || 0) / total) * 100);
    const mediumPct = Math.round(((distribution.medium || 0) / total) * 100);
    const lowPct = Math.round(((distribution.low || 0) / total) * 100);
    
    let labelsHtml = '';
    if (showLabels) {
        labelsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0.5rem;font-size:0.8rem;">
                ${renderSeverityIndicator('high', distribution.high, 'High / Critical')}
                ${renderSeverityIndicator('medium', distribution.medium, 'Medium')}
                ${renderSeverityIndicator('low', distribution.low, 'Low / Code Smell')}
            </div>
        `;
    }
    
    return `
        <div style="display:flex;height:${height};border-radius:${borderRadius};overflow:hidden;background:rgba(255,255,255,0.05);margin-bottom:1rem;">
            ${renderSeverityProgress('high', highPct, distribution.high)}
            ${renderSeverityProgress('medium', mediumPct, distribution.medium)}
            ${renderSeverityProgress('low', lowPct, distribution.low)}
        </div>
        ${labelsHtml}
    `;
}

/**
 * Returns the CSS variable name for a given severity
 * @param {string} severity - 'high', 'medium', 'low'
 * @returns {string} CSS variable name
 */
export function getSeverityColorVar(severity) {
    const colorMap = {
        'high': 'var(--severity-high)',
        'medium': 'var(--severity-medium)',
        'low': 'var(--severity-low)'
    };
    return colorMap[severity] || 'var(--severity-low)';
}

/**
 * Returns the standardized label for a given severity
 * @param {string} severity - 'high', 'medium', 'low'
 * @returns {string} Standardized label
 */
export function getSeverityLabel(severity) {
    const labelMap = {
        'high': 'High / Critical',
        'medium': 'Medium',
        'low': 'Low / Code Smell'
    };
    return labelMap[severity] || severity;
}
