type BrandAdProps = {
  headline?: string;
  support?: string;
};

export function BrandAd({
  headline = "Operations for clinics that grow with calm care.",
  support = "Enquiries, customers, and bookings stay on your tenant — rooted like a Thai canopy, clear as lagoon water.",
}: BrandAdProps) {
  return (
    <aside className="brand-ad" aria-label="About Lala">
      <div className="brand-ad-sky" aria-hidden="true" />
      <div className="brand-ad-canopy" aria-hidden="true" />
      <div className="brand-ad-lagoon" aria-hidden="true" />
      <div className="brand-ad-copy">
        <p className="brand-ad-mark">Lala</p>
        <p className="brand-ad-headline">{headline}</p>
        <p className="brand-ad-support">{support}</p>
        <ul className="brand-ad-points">
          <li>Isolated clinic tenants</li>
          <li>Website enquiries in one place</li>
          <li>Built for owner-led care teams</li>
        </ul>
      </div>
    </aside>
  );
}
