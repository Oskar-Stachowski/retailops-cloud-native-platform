function StackStatus({ stack }) {
    return (
        <section className="status-grid" id="status" aria-label="Local stack status">
            {stack.map((item) => (
            <article
                className={`status-card status-card-${item.variant}`}
                key={item.name}
            >
                <div className="status-icon" aria-hidden="true">
                {item.icon}
                </div>
                <div>
                <h3>{item.name}</h3>
                <p className="status-line">
                    <span></span>
                    {item.status}
                </p>
                <p>{item.description}</p>
                </div>
            </article>
            ))}
        </section>
    );
}

export default StackStatus;