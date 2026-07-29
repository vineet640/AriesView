"""Generate sample CRE documents (native PDFs) for the demo portfolio —
a commercial lease agreement and an offering memorandum, mirroring the
sample document library used during development."""

from pathlib import Path

import fitz

OUT = Path(__file__).resolve().parent

LEASE_SECTIONS = [
    ("COMMERCIAL LEASE AGREEMENT", ""),
    (
        "1. PARTIES AND PREMISES",
        "This Commercial Lease Agreement is entered into as of January 1, 2025, "
        "between Forty Acres Properties LLC, a Delaware limited liability company "
        "(Landlord), and Meridian Analytics Inc., a Texas corporation (Tenant). "
        "Landlord leases to Tenant approximately 12,400 rentable square feet on the "
        "third floor of the building located at 2100 Congress Avenue, Austin, Texas "
        "(the Premises).",
    ),
    (
        "2. TERM",
        "The initial term of this Lease is seven (7) years, commencing on January 1, "
        "2025 and expiring on December 31, 2031. Tenant shall have one option to "
        "renew for an additional five (5) year term, exercisable by written notice "
        "delivered to Landlord no later than nine (9) months before expiration of "
        "the initial term.",
    ),
    (
        "3. RENT PROVISIONS",
        "Base Rent for the first lease year is $42.00 per rentable square foot per "
        "annum, payable in equal monthly installments of $43,400 on the first day of "
        "each calendar month. Base Rent shall escalate by three percent (3%) on each "
        "anniversary of the Commencement Date. Tenant shall additionally pay its "
        "proportionate share of Operating Expenses, estimated at $14.25 per square "
        "foot for calendar year 2025. A late charge of five percent (5%) applies to "
        "any installment not received within five (5) days of the due date.",
    ),
    (
        "4. SECURITY DEPOSIT",
        "Tenant shall deposit with Landlord the sum of $130,200, equal to three (3) "
        "months of Base Rent, as security for the faithful performance of Tenant's "
        "obligations. The deposit shall be returned within thirty (30) days after "
        "expiration of the term, less any amounts applied to cure Tenant defaults.",
    ),
    (
        "5. TERMINATION CLAUSE",
        "Tenant may terminate this Lease effective at the end of the sixtieth (60th) "
        "month of the term, provided that Tenant delivers written notice of "
        "termination to Landlord at least twelve (12) months in advance and pays a "
        "termination fee equal to the sum of six (6) months of the then-current Base "
        "Rent plus the unamortized portion of tenant improvement allowances and "
        "leasing commissions. If Tenant fails to timely deliver the notice or pay "
        "the fee, the termination right is void and the Lease continues in full "
        "force. Landlord may terminate this Lease upon an Event of Default that "
        "remains uncured for thirty (30) days after written notice.",
    ),
    (
        "6. SUBORDINATION AND SNDA",
        "This Lease is subordinate to any mortgage now or hereafter placed on the "
        "Premises, provided that the holder of such mortgage delivers a commercially "
        "reasonable Subordination, Non-Disturbance and Attornment Agreement (SNDA). "
        "Tenant agrees to execute an estoppel certificate within ten (10) business "
        "days of Landlord's request, certifying the status of the Lease, the rent "
        "payable, and any defaults known to Tenant.",
    ),
    (
        "7. ASSIGNMENT AND SUBLETTING",
        "Tenant shall not assign this Lease or sublet any portion of the Premises "
        "without Landlord's prior written consent, which shall not be unreasonably "
        "withheld. Any permitted sublease shall not release Tenant from liability "
        "under this Lease.",
    ),
]

OM_SECTIONS = [
    ("OFFERING MEMORANDUM", ""),
    (
        "EXECUTIVE SUMMARY",
        "Congress Tower is a 148,000 square foot Class A office asset located in the "
        "Austin central business district, offered at $62,000,000, representing a "
        "6.1% capitalization rate on in-place net operating income of $3,782,000. "
        "The property is 93% leased to a diversified roster of technology, legal, "
        "and financial services tenants with a weighted average lease term of 5.4 "
        "years.",
    ),
    (
        "INVESTMENT HIGHLIGHTS",
        "The asset offers durable in-place cash flow with contractual three percent "
        "annual escalations across 87% of the rent roll. Below-market in-place rents "
        "average $39.50 per square foot against market asking rents of $46.00, "
        "creating a mark-to-market opportunity at rollover. Recent capital "
        "improvements total $4.2 million, including lobby renovation, elevator "
        "modernization, and a new rooftop amenity deck.",
    ),
    (
        "FINANCIAL OVERVIEW",
        "In-place net operating income is $3,782,000 for the trailing twelve months. "
        "Year one pro forma NOI is projected at $3,950,000, growing to $4,610,000 by "
        "year five, driven by contractual escalations and lease-up of the remaining "
        "vacancy. Projected levered internal rate of return over a five-year hold is "
        "14.2% assuming 60% loan-to-value financing at a 5.9% fixed rate.",
    ),
    (
        "TENANCY AND ROLLOVER",
        "The three largest tenants are Lakeline Software (31,000 SF through 2030), "
        "Barton Legal Group (24,500 SF through 2029), and Hill Country Wealth "
        "Management (18,200 SF through 2027). Lease rollover is modest, with no more "
        "than 14% of rentable area expiring in any single year during the projected "
        "hold period.",
    ),
    (
        "RISK FACTORS",
        "Prospective investors should consider downtown Austin office supply "
        "additions totaling 1.8 million square feet through 2027, potential "
        "moderation in technology sector demand, and rising insurance premiums. The "
        "largest tenant accounts for 22% of in-place base rent, and its 2030 "
        "expiration falls within a typical extended hold period.",
    ),
]


def build_pdf(sections, out_path):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for heading, body in sections:
        if y > 700:
            page = doc.new_page()
            y = 72
        page.insert_text((72, y), heading, fontsize=15, fontname="helv")
        y += 26
        if body:
            rect = fitz.Rect(72, y, 540, 780)
            used = page.insert_textbox(rect, body, fontsize=10.5, fontname="helv")
            if used < 0:  # did not fit; new page
                page = doc.new_page()
                used = page.insert_textbox(fitz.Rect(72, 72, 540, 780), body, fontsize=10.5, fontname="helv")
                y = 72 + (780 - 72 - used) if used > 0 else 72
            y = 780 - used + 20 if used > 0 else y + 20
    doc.save(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    build_pdf(LEASE_SECTIONS, OUT / "Lease_Agreement_TenantA.pdf")
    build_pdf(OM_SECTIONS, OUT / "Offering_Memorandum_CongressTower.pdf")
