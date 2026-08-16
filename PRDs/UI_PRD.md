# Dashboard

## Company header

Display:

```text
Acme Corporation

Suggested Rating
BB

Risk: Elevated

Latest Filing
FY2025 Annual Report

Data Quality
87% verified
3 issues requiring review
```

## KPI category tabs

```text
Overview | Profitability | Leverage | Coverage |
Liquidity | Cash Flow | Balance Sheet
```

Each category contains:

- current value
- previous year
- YoY change
- historical chart
- risk indicator
- source
- verification status

---

# KPI Detail View

Clicking a KPI should open a detail drawer/page.

Example:

```text
NET DEBT / EBITDA

2025
4.72x
↑ 0.83x YoY

Historical
2021  2.1x
2022  2.4x
2023  3.0x
2024  3.9x
2025  4.7x

Risk interpretation
Leverage has deteriorated materially over the last
three reporting periods.

Calculation
€840m / €178m = 4.72x

Inputs
Debt      €1,200m
Cash        €360m
EBITDA      €178m

Sources
Debt       Annual Report 2025 · p.87
Cash       Annual Report 2025 · p.104
EBITDA     Annual Report 2025 · p.42

Status
✓ Verified
```

---

# Data Correction UX

Click a financial fact:

```text
EBITDA
€178m

Source:
Annual Report 2025 · Page 42

Status:
Unverified AI-generated

[Verify]
[Correct]
```

If corrected:

```text
Original:
€178m

New:
€184m

Reason:
Management adjusted EBITDA figure should be used.

[Save correction]
```

After saving:

```text
EBITDA updated

Affected metrics:
✓ EBITDA Margin
✓ Debt / EBITDA
✓ Net Debt / EBITDA
✓ Interest Coverage
✓ Suggested Rating
```

This is one of the key product moments.

---
