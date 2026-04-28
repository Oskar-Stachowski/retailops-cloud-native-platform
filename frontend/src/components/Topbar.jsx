function Topbar() {
    return (
        <nav className="topbar" aria-label="Main navigation">
            <a className="brand" href="#home" aria-label="RetailOps Platform home">
            <span className="brand-icon" aria-hidden="true">▣</span>
            <span>
                RetailOps <strong>Platform</strong>
            </span>
            </a>

            <div className="nav-links" aria-label="Page sections">
            <a className="active" href="#home">Home</a>
            <a href="#status">Status</a>
            <a href="#modules">Modules</a>
            <a href="#about">About</a>
            </div>

            <div className="environment-pill" aria-label="Current environment: local">
            <span className="pulse-dot"></span>
            Local Environment
            </div>
        </nav>
    );
}

export default Topbar;