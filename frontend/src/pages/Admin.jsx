const adminAreas = [
  {
    title: "RBAC Readiness",
    icon: "🔐",
    status: "Planned",
    description:
      "Prepare a future admin area for role-based access control and user permission visibility.",
  },
  {
    title: "Environment Status",
    icon: "🟢",
    status: "MVP",
    description:
      "Expose local environment readiness and link it with platform delivery checks.",
  },
  {
    title: "Data Contracts",
    icon: "📄",
    status: "Planned",
    description:
      "Reserve space for API, data model and integration contract evidence.",
  },
  {
    title: "Evidence Gates",
    icon: "🧱",
    status: "Planned",
    description:
      "Future place for implementation, testing, security and documentation readiness gates.",
  },
];

function Admin() {
  return (
    <section className="modules" id="admin">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">⚙</span>
        <div>
          <p className="eyebrow">Platform governance</p>
          <h2>Admin</h2>
        </div>
      </div>

      <div className="module-grid">
        {adminAreas.map((area) => (
          <article className="module-card module-purple" key={area.title}>
            <div className="module-icon" aria-hidden="true">{area.icon}</div>
            <h3>{area.title}</h3>
            <p>{area.description}</p>
            <span>{area.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}

export default Admin;
