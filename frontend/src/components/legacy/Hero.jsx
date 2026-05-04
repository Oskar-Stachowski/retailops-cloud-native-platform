function Hero({ children }) {
    return (
        <section className="hero" id="home">
            <div className="hero-content">
                <p className="eyebrow">React + Vite local stack</p>
                <h1>RetailOps Platform</h1>
                <h2>Dashboard MVP Shell</h2>
                <p className="hero-copy">
                This React shell is the first user-facing layer of the RetailOps platform.
                It prepares the foundation for inventory risk, alerts, forecasting, anomaly detection,
                and platform health dashboards.
                </p>
            </div>

            <div className="hero-panel" aria-label="RetailOps MVP summary">
                <p className="eyebrow">MVP focus</p>
                <h3>Local full-stack readiness</h3>
                <ul>
                <li>Frontend shell</li>
                <li>FastAPI health contract</li>
                <li>PostgreSQL service prepared</li>
                <li>Docker Compose integration</li>
                </ul>
            </div>

            {children}

        </section>
    );
}

export default Hero;