import './LlmOutputPanel.css';

export default function LlmOutputPanel({
  output,
  loading = false,
  error = '',
  className = ''
}) {
  if (loading) {
    return (
      <section className={`panel llm-output-panel empty ${className}`.trim()}>
        <p className="eyebrow">LLM copilot</p>
        <h2>Generating recommendation</h2>
        <p className="muted">The maintenance explanation is being generated from the latest agent analysis.</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className={`panel llm-output-panel empty ${className}`.trim()}>
        <p className="eyebrow">LLM copilot</p>
        <h2>Output unavailable</h2>
        <p className="error-text">{error}</p>
      </section>
    );
  }

  if (!output) {
    return (
      <section className={`panel llm-output-panel empty ${className}`.trim()}>
        <p className="eyebrow">LLM copilot</p>
        <h2>No LLM output yet</h2>
        <p className="muted">Run or load a stored simulation to generate the agent-backed LLM output.</p>
      </section>
    );
  }

  return (
    <section className={`panel llm-output-panel ${className}`.trim()}>
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">LLM copilot</p>
          <h2>Maintenance recommendation</h2>
        </div>
        <div className="llm-meta-row">
          <span className={`status-pill ${String(output.highest_priority || 'info').toLowerCase()}`}>
            {output.highest_priority || 'INFO'}
          </span>
          <span className="axis-chip">{output.decision_count ?? 0} decisions</span>
          <span className="axis-chip">{output.provider || 'llm'}</span>
        </div>
      </div>

      <div className="llm-question-block">
        <span>Prompt</span>
        <strong>{output.question}</strong>
      </div>

      <div className="llm-answer-box">
        {formatLlmAnswer(output.answer).map((block, index) => (
          <p key={`${block.slice(0, 24)}-${index}`}>{block}</p>
        ))}
      </div>

      <div className="message-meta">
        Run {output.run_id} | {output.model || 'grounded maintenance copilot'} | {output.mode || 'answer'}
      </div>
    </section>
  );
}

/**
 * Splits plain LLM output into display paragraphs with an empty-content fallback.
 *
 * @param {string} answer - Raw answer returned by the backend.
 * @returns {Array<string>} Paragraph blocks suitable for rendering.
 */
function formatLlmAnswer(answer) {
  const blocks = toPlainText(answer)
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.length ? blocks : ['No answer content was returned.'];
}

/**
 * Removes Markdown-like markers from LLM output before rendering.
 *
 * @param {string} value - Raw LLM output.
 * @returns {string} Plain text with normalized line content.
 */
function toPlainText(value) {
  return String(value || '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/```/g, '')
    .replace(/__/g, '')
    .replace(/[*`#>]/g, '')
    .split('\n')
    .map((line) => line
      .trim()
      .replace(/^[-+]\s+/, '')
      .replace(/^\d+[.)]\s+/, '')
      .replace(/\s{2,}/g, ' '))
    .join('\n')
    .trim();
}
