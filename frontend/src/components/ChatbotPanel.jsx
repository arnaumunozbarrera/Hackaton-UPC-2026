import './ChatbotPanel.css';
import { useEffect, useRef, useState } from 'react';
import { sendChatQuery } from '../services/chatApi';

const SUGGESTED_QUESTIONS = [
  'When is the blade required to be replaced?',
  'What is the current status of this component?',
  'How has this component degraded over the run?',
  'What warnings or events were stored?'
];

export default function ChatbotPanel({ runId, selectedComponentId, disabled }) {
  const [question, setQuestion] = useState('');
  const [chatEntries, setChatEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const historyRef = useRef(null);
  const latestEntryRef = useRef(null);

  useEffect(() => {
    setChatEntries([]);
    setQuestion('');
    setError('');
  }, [runId, selectedComponentId]);

  useEffect(() => {
    if (!historyRef.current) return;
    if (latestEntryRef.current) {
      latestEntryRef.current.scrollIntoView({ block: 'start', behavior: 'smooth' });
      return;
    }
    historyRef.current.scrollTop = 0;
  }, [chatEntries, loading]);

  /**
   * Sends a grounded chat query and appends the response to the local thread.
   *
   * @param {string} nextQuestion - Question text to submit.
   * @returns {Promise<void>} Resolves after the query has completed.
   */
  async function submitQuestion(nextQuestion) {
    const normalizedQuestion = nextQuestion.trim();
    if (!normalizedQuestion) return;

    setLoading(true);
    setError('');
    setQuestion('');

    try {
      const payload = await sendChatQuery({
        question: normalizedQuestion,
        runId,
        componentId: selectedComponentId
      });

      setChatEntries((current) => [
        ...current,
        {
          id: `${Date.now()}-${current.length}`,
          question: normalizedQuestion,
          response: payload
        }
      ]);
    } catch (requestError) {
      setError(requestError.message || 'Failed to query the historian-backed chatbot.');
      setQuestion(normalizedQuestion);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await submitQuestion(question);
  }

  function handlePrefill(nextQuestion) {
    setQuestion(nextQuestion);
  }

  async function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      await submitQuestion(question);
    }
  }

  const latestModel = chatEntries.at(-1)?.response?.model;

  return (
    <section className="panel chatbot-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Grounded chat</p>
          <h2>Component AI expert</h2>
        </div>
        <span className="db-chip">
          {latestModel?.provider === 'ollama' ? `Model: ${latestModel.name}` : 'Model: grounded explainer'}
        </span>
      </div>

      <p className="muted">
        Queries are answered only from stored telemetry, messages, predictions, and decision context. Press `Enter`
        to send and `Shift+Enter` for a new line.
      </p>

      <div ref={historyRef} className="chatbot-history">
        {!chatEntries.length ? (
          <div className="chatbot-empty">
            <p className="muted">Ask a question about the selected component or the latest stored run.</p>
          </div>
        ) : (
          chatEntries.map((entry, index) => (
            <article
              key={entry.id}
              ref={index === chatEntries.length - 1 ? latestEntryRef : null}
              className="chat-thread-card"
            >
              <div className="chat-question-block">
                <span className="chat-role">Question</span>
                <p>{entry.question}</p>
              </div>

              <div className={`chatbot-answer ${entry.response.insufficient_data ? 'insufficient' : ''}`}>
                <div className="chat-answer-header">
                  <span className="chat-role">Answer</span>
                  <span className="status-pill functional">
                    {entry.response.insufficient_data ? 'LIMITED DATA' : 'GROUNDED'}
                  </span>
                </div>
                <p>{entry.response.answer}</p>
              </div>

              <div className="chatbot-meta">
                <span className="axis-chip">Run: {entry.response.run_id || 'none'}</span>
                <span className="axis-chip">Scenario: {entry.response.scenario_id || 'none'}</span>
                <span className="axis-chip">Component: {entry.response.component_id || 'general'}</span>
              </div>

              <div className="chatbot-facts">
                {entry.response.support_metrics?.length ? (
                  <ul className="fact-list metric-list">
                    {entry.response.support_metrics.map((metric) => (
                      <li key={`${entry.id}-${metric.scope}-${metric.label}`}>
                        <span>{metric.label}</span>
                        <strong>
                          {metric.value} {metric.unit}
                        </strong>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted">No supporting metrics were available for this question.</p>
                )}
              </div>
            </article>
          ))
        )}
      </div>

      <form className="chatbot-form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Question</span>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? 'Run the simulation first to enable grounded chat.'
                : `Ask about ${selectedComponentId || 'the latest run'}`
            }
            disabled={disabled || loading}
            rows={3}
          />
        </label>
        <div className="button-row">
          <button type="submit" className="primary-button" disabled={disabled || loading || !question.trim()}>
            {loading ? 'Querying...' : 'Ask historian'}
          </button>
        </div>
      </form>

      <div className="suggestion-row">
        {SUGGESTED_QUESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="ghost-button"
            onClick={() => handlePrefill(suggestion)}
            disabled={disabled || loading}
          >
            {suggestion}
          </button>
        ))}
      </div>

      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}
