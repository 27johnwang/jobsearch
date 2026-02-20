# Contributing to 2026 New Grad Finance Positions

Thank you for helping maintain this list! Here's how you can contribute.

## Adding a New Job Listing

### Option 1: Open an Issue

[Open a new issue](../../issues/new) with the following information:

- **Company name**
- **Role title**
- **Location(s)**
- **Application URL**
- **Category** (Investment Banking, Sales & Trading, Consulting, Asset Management, Quantitative Finance, Corporate Finance, Risk Management, Financial Technology, Product Management, Sales)

### Option 2: Submit a Pull Request

1. Fork this repository
2. Add the job to `data/manual_jobs.json` following this format:

```json
{
  "company": "Company Name",
  "role": "Analyst / Associate Title",
  "location": "City, State",
  "url": "https://careers.company.com/job-link",
  "date_posted": "2025-09-15",
  "category": "Investment Banking",
  "source": "manual",
  "is_closed": false,
  "requires_visa_sponsorship": true,
  "us_citizenship_required": false,
  "company_url": "https://company.com",
  "tags": []
}
```

3. Run the README generator to update the table:

```bash
pip install -r requirements.txt
python -m scraper.readme_generator
```

4. Submit your pull request

## Marking a Position as Closed

If you find that a listed position is no longer accepting applications:

1. Update the `is_closed` field to `true` in `data/manual_jobs.json` (for manual entries) or open an issue
2. The automated scraper will also detect closed positions during its daily run

## Guidelines

- Only add **new graduate / entry-level** positions (0-2 years experience)
- Positions must be **finance-related** (see categories above)
- Include a **direct application link** (not a third-party aggregator)
- Verify the position is for the **2025-2026 hiring cycle**
- Do not add internship positions (this list is for full-time roles)

## Categories

| Category | Description |
|----------|-------------|
| Investment Banking | IB analyst programs, M&A, capital markets, restructuring |
| Sales & Trading | S&T rotational programs, trading analyst roles |
| Consulting | Management, strategy, financial advisory consulting |
| Asset Management | Portfolio management, investment research, fund operations |
| Quantitative Finance | Quant research, algo trading, financial engineering |
| Corporate Finance | FP&A, treasury, corporate development, IR |
| Risk Management | Credit risk, market risk, compliance, regulatory |
| Financial Technology | FinTech companies, banking technology, payments |
| Product Management (Finance) | PM roles at financial firms or finance-focused PM |
| Sales (Financial Services) | Institutional sales, relationship management, BD |

## Running the Scraper Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scraper
python -m scraper.main

# Regenerate the README
python -m scraper.readme_generator
```
