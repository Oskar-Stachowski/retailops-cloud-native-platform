const productAreas = [
  {
    title: "Product 360",
    icon: "👤",
    status: "Planned",
    description:
      "Unified product view across sales, inventory, category, price and operational signals.",
  },
  {
    title: "Inventory Risk",
    icon: "📦",
    status: "Planned",
    description:
      "Identify slow-moving, overstocked and at-risk products before they become a business problem.",
  },
  {
    title: "Pricing Signals",
    icon: "🏷️",
    status: "Planned",
    description:
      "Prepare space for future pricing, margin and promotion evidence used by commercial teams.",
  },
  {
    title: "Category View",
    icon: "🧭",
    status: "Planned",
    description:
      "Group products by category so category managers can focus on their own decision scope.",
  },
];

function Products() {
  return (
    <section className="modules" id="products">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">▦</span>
        <div>
          <p className="eyebrow">Product intelligence</p>
          <h2>Products</h2>
        </div>
      </div>

      <div className="module-grid">
        {productAreas.map((area) => (
          <article className="module-card module-blue" key={area.title}>
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

export default Products;
