export default function MessagesPanel({ messages }) {
  if (!messages?.length) {
    return (
      <section className="panel messages-panel empty">
        <p className="eyebrow">Runtime messages</p>
        <h2>No messages yet</h2>
        <p className="muted">Run the simulation to generate grounded messages from the historian.</p>
      </section>
    );
  }

  return (
    <section className="panel messages-panel">
      <div className="section-title-row compact">
        <div>
          <p className="eyebrow">Runtime messages</p>
          <h2>Observed events</h2>
        </div>
      </div>

      <div className="message-list">
        {messages.map((message) => (
          <article key={message.id} className="message-card">
            <div className="message-card-header">
              <strong>{message.title}</strong>
              <span className={`status-pill ${message.severity.toLowerCase()}`}>{message.severity}</span>
            </div>
            <p>{message.body}</p>
            <div className="message-meta">{message.timestamp}</div>
          </article>
        ))}
      </div>
    </section>
  );
}
