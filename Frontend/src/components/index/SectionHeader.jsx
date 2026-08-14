function SectionHeader({ icon, title }) {
  return (
    <div className="index-section-title">
      {icon ? <span>{icon}</span> : null}
      <h2>{title}</h2>
    </div>
  );
}

export default SectionHeader;
