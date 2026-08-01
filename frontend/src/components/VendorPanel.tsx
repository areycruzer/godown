import { useState } from 'react'
import type { Vendor } from '../api'

type Props = { vendors: Vendor[]; onEnrich?: (vendor: Vendor) => void }

export function VendorPanel({ vendors, onEnrich }: Props) {
  if (!vendors.length) {
    return (
      <aside className="vendor-panel">
        <h2>Vendors</h2>
        <p className="muted">Search results will land here.</p>
      </aside>
    )
  }
  return (
    <aside className="vendor-panel">
      <h2>Vendors <span className="count">{vendors.length}</span></h2>
      <ul className="vendor-list">
        {vendors.map((v, i) => (
          <VendorCard key={`${v.supplierId ?? v.supplierUrl ?? i}`} vendor={v} onEnrich={onEnrich} />
        ))}
      </ul>
    </aside>
  )
}

function VendorCard({ vendor, onEnrich }: { vendor: Vendor; onEnrich?: (vendor: Vendor) => void }) {
  const [open, setOpen] = useState(false)
  const loc = [vendor.supplierCity, vendor.supplierState].filter(Boolean).join(', ')
  return (
    <li className="vendor-card">
      <button type="button" className="vendor-head" onClick={() => setOpen((o) => !o)}>
        <div className="vendor-title">
          <strong>{vendor.companyName || 'Unknown company'}</strong>
          <span>{vendor.productName || '—'}</span>
        </div>
        <div className="vendor-meta">
          {vendor.price && <span>{vendor.price}</span>}
          {loc && <span>{loc}</span>}
        </div>
      </button>
      <div className="vendor-quick">
        {vendor.gstNumber && <span>GST {vendor.gstNumber}</span>}
        {vendor.phone && <span>{vendor.phone}</span>}
        {vendor.supplierUrl && (
          <a href={vendor.supplierUrl} target="_blank" rel="noreferrer">
            Storefront
          </a>
        )}
        {vendor.productUrl && (
          <a href={vendor.productUrl} target="_blank" rel="noreferrer">
            Product
          </a>
        )}
        {onEnrich && !vendor.profile && !vendor.pdp && !(vendor.reviews?.length) && (
          <button
            type="button"
            className="enrich-btn"
            onClick={(e) => {
              e.stopPropagation()
              onEnrich(vendor)
            }}
          >
            ⚡ Enrich
          </button>
        )}
      </div>
      {open && (
        <div className="vendor-detail">
          {vendor.profile && (
            <section>
              <h4>Profile</h4>
              <pre>{JSON.stringify(vendor.profile, null, 2)}</pre>
            </section>
          )}
          {vendor.pdp && (
            <section>
              <h4>PDP</h4>
              <pre>{JSON.stringify(vendor.pdp, null, 2)}</pre>
            </section>
          )}
          {vendor.reviews && vendor.reviews.length > 0 && (
            <section>
              <h4>Reviews ({vendor.reviews.length})</h4>
              <pre>{JSON.stringify(vendor.reviews, null, 2)}</pre>
            </section>
          )}
          {!vendor.profile && !vendor.pdp && !(vendor.reviews?.length) && (
            <p className="muted">No enrichment yet — click ⚡ Enrich or use Full mode.</p>
          )}
        </div>
      )}
    </li>
  )
}

