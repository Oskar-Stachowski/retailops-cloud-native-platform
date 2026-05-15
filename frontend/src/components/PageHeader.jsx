export default function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className = "",
}) {
  const classes = [
    "api-page__header",
    actions ? "api-page__header--with-actions" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <header className={classes}>
      <div className="api-page__header-copy">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="api-page__header-actions">{actions}</div> : null}
    </header>
  );
}
