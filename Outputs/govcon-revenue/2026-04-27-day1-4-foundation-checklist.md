# GovCon Foundation — Day 1-4 Checklist

**Goal:** Zero → LLC formed + EIN issued + bank open + UEI applied. In 4 calendar days.

**Total time on-task:** ~3 hours
**Total cost:** $137–$285

---

## Pre-Day 1 — Decisions to Lock (30 min, day before)

- [ ] **State of formation** picked (Wyoming / NM / home state — see roadmap matrix)
- [ ] **LLC name** chosen — must be unique in your state AND have available `.com` domain
  - Check name: state SOS website business search
  - Check domain: namecheap.com or porkbun.com (use one of these to register, $10–12/yr)
- [ ] **Registered agent** chosen
  - You (free, but your home address becomes public record)
  - Northwest Registered Agent ($125/yr — recommended, used by most pros)
  - Wyoming Agents ($50/yr — cheapest legitimate)
- [ ] **Member structure** decided — single-member LLC (default for solo) vs multi-member
- [ ] **Business address** confirmed — must be a real physical address (PO box ≠ acceptable for SAM.gov later)
- [ ] **Responsible party SSN/ITIN** ready (yours, for EIN application)

---

## Day 1 — File LLC + Domain + Email (60 min)

### LLC Filing
- [ ] Go to your state's Secretary of State business filing portal
- [ ] File **Articles of Organization** online
- [ ] Pay state filing fee
- [ ] Save confirmation/receipt PDF
- [ ] **Expected output:** Filing receipt with order number; stamped Articles in 1–7 days

| State | Portal | Fee | Processing |
|---|---|---|---|
| Wyoming | wyobiz.wyo.gov | $100 | Same day–24 hr |
| New Mexico | enterprise.sos.state.nm.us | $50 | 1–3 business days |
| Delaware | corp.delaware.gov | $90 | 7–10 days standard |
| California | bizfileonline.sos.ca.gov | $70 + $800/yr franchise tax | 5–7 days |
| Texas | sos.state.tx.us | $300 | Same day online |
| Florida | sunbiz.org | $125 | 2–5 days |

### Domain
- [ ] Register `yourcompany.com` at Namecheap or Porkbun (~$12/yr)
- [ ] Enable WHOIS privacy (free at both)
- [ ] Auto-renew on

### Business Email
- [ ] Pick one:
  - **Free**: Zoho Mail (forever free for 1 user, custom domain)
  - **$7/mo**: Google Workspace Business Starter (better deliverability + Drive)
- [ ] Set up `you@yourcompany.com` and a `contracts@yourcompany.com` alias
- [ ] Send a test email to yourself — confirm inbound/outbound work

---

## Day 2-3 — Wait for State Confirmation (passive)

- [ ] Check filing status daily (state SOS portal)
- [ ] When confirmed: **download stamped Articles of Organization PDF** — you'll need this for the bank and SAM.gov
- [ ] Save to `~/govcon/01-formation/articles-of-organization.pdf`

**Use this time to:**
- Draft Operating Agreement (single-member template — free at northwestregisteredagent.com/free-llc-operating-agreement)
- Order capability statement headshot if going pro on the design

---

## Day 3-4 — EIN (15 min once Articles arrive)

- [ ] Confirm state has issued stamped Articles (do not skip)
- [ ] Go to **irs.gov/EIN**
- [ ] Click "Apply Online Now" (must be Mon–Fri 7am–10pm ET)
- [ ] Complete SS-4 application:
  - Entity type: Limited Liability Company
  - Members: 1 (single-member) or 2+ (multi-member)
  - State of organization: [your state]
  - Reason: Started a new business
  - Closing month of accounting year: December
  - First wages paid: leave blank or future date
- [ ] **At the end:** download the **CP 575 / SS-4 confirmation letter as PDF immediately**
  - IRS does NOT email this; it's display-once-only
- [ ] Save 3 copies: local PDF, cloud backup, printed
- [ ] Save to `~/govcon/01-formation/ein-confirmation.pdf`

**If you get IRS error 101:** wait 24 hours, retry. Brand-new LLCs sometimes lag in IRS verification.

---

## Day 4 — Bank Account + SAM/UEI Start (45 min)

### Business Bank Account

Pick one:

| Bank | Why | Cost |
|---|---|---|
| **Mercury** | Tech-friendly, free, instant approval, virtual cards | $0 |
| **Bluevine** | Earns interest, free, decent app | $0 |
| **Local credit union** | Builds relationship for future LOC/loan | $0 |
| ~~Bank of America / Chase~~ | High fees, slow approval, mediocre UX | skip |

- [ ] Apply online at chosen bank
- [ ] Required uploads: Articles of Organization, EIN letter, ID, beneficial ownership info
- [ ] Get debit card issued + checking + savings sub-accounts
- [ ] Make a $50 transfer from personal account to capitalize the LLC (don't skip — proves separation)

### SAM.gov + UEI Registration

- [ ] Go to **sam.gov/content/entity-registration**
- [ ] Click "Get Started"
- [ ] Choose: **"Register Entity"** (full SAM, NOT UEI-only)
- [ ] Fill in:
  - Legal Business Name — must match Articles of Organization **exactly** (character for character, including LLC vs L.L.C.)
  - Physical Address — must match Articles
  - EIN
  - Business start date
  - State of incorporation
  - NAICS codes — pick top 5 candidates (you'll refine in W5; can edit later)
- [ ] Submit for processing
- [ ] **Expected timeline:** 2–4 weeks. Status visible in your SAM dashboard.

**Critical:** the legal name must be character-perfect. "Acme Ventures LLC" ≠ "Acme Ventures, LLC" ≠ "ACME VENTURES LLC". Use exactly what the state stamped on your Articles.

---

## End-of-Day-4 State

You should have:

```
~/govcon/01-formation/
├── articles-of-organization.pdf
├── ein-confirmation.pdf (CP 575)
├── operating-agreement.pdf
├── domain-registration-receipt.pdf
└── bank-account-info.txt (account #, routing #, login)
```

And these statuses:
- ✅ LLC: Active
- ✅ EIN: Issued
- ✅ Domain: Registered + DNS pointing somewhere (even if just a holding page)
- ✅ Email: Sending and receiving on custom domain
- ✅ Bank: Open + capitalized with $50
- ⏳ SAM.gov: Submitted, processing (2–4 weeks)
- ⏳ UEI: Will be issued at end of SAM processing

---

## Cost Reality Check

| Item | Cost |
|---|---|
| LLC filing | $50–$300 |
| Registered agent | $0–$125 |
| Domain | $12 |
| Business email | $0–$84 (year) |
| EIN | $0 |
| Bank account | $0 |
| SAM/UEI | $0 |
| Initial LLC capitalization | $50 (your own money, transferred in) |
| **Total Days 1-4** | **$112–$571** depending on state + agent + email choices |

Bootstrap target hit: well under the $1k 12-week cap.

---

## What NOT to Do

- ❌ Pay any service to "get your EIN fast" — it's free and instant from the IRS directly
- ❌ Pay any service to "register you on SAM.gov" — they'll charge $400-$2000 for a free process
- ❌ Use a PO Box as your business address — fails SAM.gov physical address requirement
- ❌ Skip the Operating Agreement — single-member or not, banks will ask
- ❌ Mix personal and business funds — start clean from Day 1, no exceptions
- ❌ File EIN before LLC is state-confirmed — error 101 + delay

---

## Next After Day 4

While SAM/UEI processes (2–4 weeks):
1. Build scanner v1 (per Week 1 of roadmap)
2. Draft capability statement v0 (refine after W5 NAICS decision)
3. Set up bookkeeping (Wave Accounting = free; or Excel)
4. Get a basic logo (Looka or Canva, $0–$20)

---

## New Rules / Preferences to Remember

- **Save EIN letter immediately** — display-once, no email backup
- **Legal name precision** — Articles → bank → SAM must match character-for-character
- **No paid intermediaries** — every govt registration is free direct from the source
