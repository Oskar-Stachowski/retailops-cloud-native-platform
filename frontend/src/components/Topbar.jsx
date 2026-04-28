import { NavLink } from "react-router-dom";

const navItems = [
  { label: "Dashboard", to: "/" },
  { label: "Products", to: "/products" },
  { label: "Forecasts", to: "/forecasts" },
  { label: "Anomalies", to: "/anomalies" },
  { label: "Recommendations", to: "/recommendations" },
  { label: "Admin", to: "/admin" },
];

function Topbar() {
  return (
    <nav className="topbar" aria-label="Main navigation">
      <NavLink className="brand" to="/" aria-label="RetailOps Platform home">
        <span className="brand-icon" aria-hidden="true">▣</span>
        <span>
          RetailOps <strong>Platform</strong>
        </span>
      </NavLink>

      <div className="nav-links" aria-label="Page sections">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {item.label}
          </NavLink>
        ))}
      </div>

      <div className="environment-pill" aria-label="Current environment: local">
        <span className="pulse-dot"></span>
        Local Environment
      </div>
    </nav>
  );
}

export default Topbar;