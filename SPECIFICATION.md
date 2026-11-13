# DustWatch: Software Requirements Specification & Technical Architecture (SRS / SDD)

**Product:** DustWatch for Odoo 19  
**Version:** 1.0.0 (Release Candidate / Hackathon Baseline)  
**Track:** Odoo Hackathon 2026 — Green & Renewable Energy Track  
**Repository:** https://github.com/Umarr35/dustwatch  
**Document Classification:** Single Source of Truth (SSOT) for Human Developers & AI Agents  

---

## 1. System Vision & Architecture Overview

### 1.1 The Industry Challenge
In desert environments such as the United Arab Emirates, solar panels suffer from persistent, rapid efficiency degradation due to airborne dust and fine sand deposition. Published regional research highlights:
- An uncleaned solar array in the UAE loses **12.7% of its generation capacity** within 5 months.
- During peak dust storm periods (such as March in Abu Dhabi), daily soiling reaches **close to 1% per day**, causing losses up to **27%**.
- Across Dubai's Shams Dubai initiative (over **725 MW** connected across **8,430+ buildings**), millions of Dirhams are forfeited annually.

Existing maintenance practices oscillate between two detrimental failure modes:
1. **Cleaning Too Rarely:** Dust accumulation compounds over months, forfeiting massive solar energy revenue that far exceeds cleaning costs.
2. **Cleaning Too Often:** Fixed calendar routines (e.g. weekly) incur bloated contractor invoices and waste thousands of liters of scarce desalinated water cleaning panels that are already operating near peak capacity.

### 1.2 The DustWatch Solution
DustWatch is an autonomous operations and financial decision engine built natively on the **Odoo 19 backend**. Instead of relying on arbitrary calendar schedules, DustWatch **prices daily energy deficits in local currency (AED)** and dispatches cleaning crews at the exact mathematical breakeven point where cumulative energy loss matches the cost of a single cleaning intervention.

### 1.3 Dual-Deployment Business Models
DustWatch is engineered with architectural flexibility to serve two distinct solar enterprise profiles:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                       DUSTWATCH DEPLOYMENT ARCHITECTURE                       │
├───────────────────────────────────────┬───────────────────────────────────────┤
│    MODE A: MODULAR CRM/ERP ADD-ON     │      MODE B: TURNKEY OPERATIONS       │
│   (For Established Solar Installers)  │   (For Green-Field O&M Contractors)   │
├───────────────────────────────────────┼───────────────────────────────────────┤
│ • Plugs into existing Odoo ERP / CRM  │ • Complete end-to-end operations      │
│ • Links to existing res.partner       │ • Lead capture & solar rooftop survey │
│ • Dispatches tasks via project.task   │ • Inverter telemetry ingestion        │
│ • Generates invoices via account.move │ • Automated dispatch & field Kanban   │
│ • Exposes JSON-RPC/REST for 3rd-party │ • Customer self-service portal & PDF  │
│   CRMs (Salesforce, HubSpot, custom)  │   monthly performance reports         │
└───────────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. Odoo Backend Native Architecture

### 2.1 Technology Stack
- **Platform:** Odoo 19.0 (Community & Enterprise compatible)
- **Programming Language:** Python 3.11+
- **Database:** PostgreSQL 15+
- **Frontend / UI:** Odoo Web Client (OWL / XML Views / Kanban / QWeb)
- **External Interfaces:** CSV Wizard Ingestion, Odoo JSON-RPC / REST External API

### 2.2 Module Directory Structure
```
dustwatch/
├── __init__.py                  # Root package initializer
├── __manifest__.py              # Odoo 19 module metadata, dependencies & views
├── SPECIFICATION.md             # Single Source of Truth for all Developers & AIs
├── README.md                    # Quickstart guide & installation instructions
├── models/                      # Odoo ORM Data Models
│   ├── __init__.py
│   ├── site.py                  # dustwatch.site (Rooftop solar installation)
│   ├── reading.py               # dustwatch.reading (Daily telemetry & loss math)
│   ├── job.py                   # dustwatch.job (Cleaning work order & recovery)
│   └── res_partner.py           # res.partner inheritance (Customer solar assets)
├── views/                       # Odoo XML UI Views & Dashboards
│   ├── site_views.xml           # Tree (with decorators), Kanban, Form, Search
│   ├── reading_views.xml        # Tree, Form, 2-Line Graph View, Pivot
│   ├── job_views.xml            # Drag-and-drop Operations Kanban Board
│   ├── res_partner_views.xml    # Partner form extension with smart buttons
│   └── menu_views.xml           # Top navigation bar and action bindings
├── wizards/                     # TransientModels for interactive workflows
│   ├── __init__.py
│   ├── import_readings_wizard.py# CSV telemetry parser and bulk creator
│   └── import_readings_views.xml# Modal file upload dialog
├── security/                    # Security Groups & Access Control
│   ├── security_groups.xml      # User & Manager role definitions
│   └── ir.model.access.csv      # Model-level CRUD permission matrix
├── data/                        # Static data & Scheduled Actions
│   ├── ir_cron_data.xml         # Nightly trigger evaluation cron job
│   ├── sample_demo_data.xml     # 3 pre-configured demo solar installations
│   └── sample_readings_90days.csv# 90-day simulated telemetry (dust + storm + clean)
└── static/                      # Web assets & media
    └── description/
        └── icon.png             # Module app store icon
```

---

## 3. Detailed Data Dictionary & Schema Specifications

### 3.1 `dustwatch.site` (Solar Rooftop Site)
Represents a customer's physical rooftop installation.
- `name` (`fields.Char`, required=True): Installation label (e.g. "Grand Hyatt Dubai Rooftop").
- `partner_id` (`fields.Many2one('res.partner')`, required=True): Customer / Asset Owner.
- `capacity_kwp` (`fields.Float`, required=True, default=100.0): System rated peak power in kWp.
- `electricity_price` (`fields.Float`, required=True, default=0.40): Grid tariff in AED/kWh.
- `cleaning_cost` (`fields.Float`, required=True, default=1500.0): Contractor cleaning fee quote in AED.
- `performance_factor` (`fields.Float`, default=0.80): System baseline performance ratio (PR).
- `installation_date` (`fields.Date`): Commissioning date.
- `date_last_cleaned` (`fields.Date`): Baseline date. Only readings on or after this date count toward running loss.
- `location` (`fields.Char`): City / Area in UAE.
- `active` (`fields.Boolean`, default=True): Active record flag.
- `reading_ids` (`fields.One2many('dustwatch.reading', 'site_id')`): Telemetry history.
- `job_ids` (`fields.One2many('dustwatch.job', 'site_id')`): Cleaning history.
- `running_loss_aed` (`fields.Float`, compute='_compute_running_loss', store=True): Cumulative financial loss.
- `days_since_last_clean` (`fields.Integer`, compute='_compute_running_loss', store=True): Elapsed days.
- `cleaning_progress` (`fields.Float`, compute='_compute_running_loss', store=True): `(running_loss / cleaning_cost) * 100`.
- `health_state` (`fields.Selection(['green', 'amber', 'red'])`, compute='_compute_running_loss', store=True):
  - `'green'`: `< 70%` of cleaning cost reached.
  - `'amber'`: `70% - 99%` of cleaning cost reached (Attention).
  - `'red'`: `≥ 100%` of cleaning cost reached (Clean Due!).
- `lifetime_saved_aed` (`fields.Float`, compute='_compute_lifetime_savings'): Total audited ROI delivered.

### 3.2 `dustwatch.reading` (Daily Solar Telemetry)
Time-series production record from on-site inverters or monitoring systems.
- `site_id` (`fields.Many2one('dustwatch.site')`, required=True, ondelete='cascade'): Parent site.
- `date` (`fields.Date`, required=True): Reading timestamp.
- `sun_hours` (`fields.Float`, required=True, default=5.5): Peak sun hours (PSH) measured today.
- `actual_kwh` (`fields.Float`, required=True): Physical electricity recorded by on-site inverters.
- `expected_kwh` (`fields.Float`, compute='_compute_calculations', store=True): $Capacity 	imes Sun 	imes PR$.
- `lost_kwh` (`fields.Float`, compute='_compute_calculations', store=True): $\max(0, Expected - Actual)$.
- `lost_aed` (`fields.Float`, compute='_compute_calculations', store=True): $Lost\ kWh 	imes Tariff$.
- `soiling_loss_pct` (`fields.Float`, compute='_compute_calculations', store=True): $(Lost\ kWh / Expected) 	imes 100$.
- `is_post_clean` (`fields.Boolean`, default=False): Recovery audit flag for 3 days post-clean.
- `notes` (`fields.Char`): Atmospheric conditions (e.g. "Severe sandstorm").

### 3.3 `dustwatch.job` (Cleaning Work Order)
Actionable maintenance order that coordinates crew dispatch and recovery verification.
- `name` (`fields.Char`, required=True): Reference (e.g. `CLEAN/202611/Grand Hyatt`).
- `site_id` (`fields.Many2one('dustwatch.site')`, required=True): Target rooftop.
- `partner_id` (`fields.Many2one('res.partner')`, related='site_id.partner_id', store=True): Customer.
- `state` (`fields.Selection(['proposed', 'scheduled', 'done', 'cancelled'])`, default='proposed'): Workflow stage.
- `date_created` (`fields.Date`, default=today): Dispatch creation date.
- `date_scheduled` (`fields.Date`): Planned execution date.
- `date_completed` (`fields.Date`): Execution completion date.
- `trigger_loss_aed` (`fields.Float`): Cumulative loss that triggered the work order.
- `cost` (`fields.Float`, required=True): Agreed cleaning contractor fee.
- `recovery_kwh_day` (`fields.Float`, compute='_compute_recovery_metrics', store=True): Energy reclaimed per day.
- `recovery_aed_day` (`fields.Float`, compute='_compute_recovery_metrics', store=True): Financial return reclaimed per day.
- `payback_days` (`fields.Float`, compute='_compute_recovery_metrics', store=True): $Cost / Recovery_{daily}$.
- `is_fault_flagged` (`fields.Boolean`, compute='_compute_recovery_metrics', store=True): Hardware fault alert.
- `water_saved_liters` (`fields.Float`, default=750.0): Desalinated water conserved.

### 3.4 `res.partner` (Customer Extension)
- `dustwatch_site_ids` (`fields.One2many('dustwatch.site', 'partner_id')`): Customer's solar portfolio.
- `dustwatch_site_count` (`fields.Integer`, compute): Number of registered rooftop sites.
- `dustwatch_total_capacity_kwp` (`fields.Float`, compute): Total portfolio kWp capacity.
- `dustwatch_total_saved_aed` (`fields.Float`, compute): Lifetime verified financial savings.

---

## 4. The Mathematical Decision Engine

### 4.1 Core Formulas
1. **Expected Output (Clean Baseline):**
   $$E = P_{	ext{kWp}} 	imes H_{	ext{sun}} 	imes 	ext{PR}$$
   *(Example: $500 	ext{ kWp} 	imes 5.5 	ext{ hrs} 	imes 0.80 = 2,200 	ext{ kWh}$)*
2. **Electricity Lost to Soiling:**
   $$L_{	ext{kWh}} = \max(0, E - A_{	ext{actual}})$$
   *(Example: $2,200 - 2,112 = 88 	ext{ kWh}$ lost, or 4%)*
3. **Daily Financial Loss:**
   $$L_{	ext{AED}} = L_{	ext{kWh}} 	imes 	ext{Tariff}$$
   *(Example: $88 	ext{ kWh} 	imes 0.40 	ext{ AED/kWh} = 35.20 	ext{ AED}$)*
4. **Optimal Breakeven Trigger Rule:**
   $$\sum_{t=t_{	ext{clean}}}^{	ext{today}} L_{	ext{AED}}(t) \ge C_{	ext{clean}}$$
   *Dispatch cleaning job the exact day running financial loss matches the cleaning invoice.*
5. **Post-Clean Recovery & Payback Speed:**
   $$\Delta_{	ext{recovery}} = \overline{L}_{	ext{pre-clean (3d)}} - \overline{L}_{	ext{post-clean (3d)}}$$
   $$	ext{Payback Days} = rac{C_{	ext{clean}}}{\Delta_{	ext{recovery}} 	imes 	ext{Tariff}}$$
   *(Example: $	ext{AED } 1,500 / 	ext{AED } 66/	ext{day} = 22.7 	ext{ days}$)*
6. **Dynamic Baseline Learning (Recalibrating PR):**
   $$	ext{PR}_{	ext{new}} = rac{1}{3} \sum_{k=1}^3 rac{A_{	ext{actual}}(k)}{P_{	ext{kWp}} 	imes H_{	ext{sun}}(k)}$$

### 4.2 Mathematical Proof of Optimality
Total cost of soiling over an operational cycle equals:
$$	ext{Total Cost} = C_{	ext{cleaning}} + C_{	ext{lost electricity}}$$
If dust accumulates at rate $r$ per day, daily loss grows linearly ($L(t) = k \cdot t$), so cumulative energy loss grows quadratically ($rac{1}{2} k t^2$). The average cost per day $rac{C_{	ext{clean}} + rac{1}{2} k t^2}{t} = rac{C_{	ext{clean}}}{t} + rac{1}{2} k t$. Taking the derivative with respect to $t$ and setting to 0 yields $t^* = \sqrt{rac{2 C_{	ext{clean}}}{k}}$, at which point:
$$	ext{Cumulative Energy Loss} = rac{1}{2} k (t^*)^2 = C_{	ext{clean}}$$
Thus, **cleaning at the exact moment accumulated losses equal one cleaning cost mathematically minimizes total lifetime expenditure.**

---

## 5. UI/UX & Views Specification

1. **Portfolio Tree View (`dustwatch.site.tree`):**
   - Color decorators: `decoration-danger="health_state == 'red'"`, `decoration-warning="health_state == 'amber'"`, `decoration-success="health_state == 'green'"`.
   - Columns: Site Name, Customer, Capacity kWp, Last Cleaned, Days Elapsed, Running Loss (AED), Cleaning Cost, Progress Bar, Health Badge.
2. **Operations Dashboard Kanban (`dustwatch.site.kanban`):**
   - Grouped by `health_state` (Green, Amber, Red).
   - Display cards with quick-action "Dispatch Clean" buttons for red-alert sites.
3. **Cleaning Dispatch Board (`dustwatch.job.kanban`):**
   - Drag-and-drop workflow columns: `Proposed by App` $ightarrow$ `Dispatched / Scheduled` $ightarrow$ `Cleaned & Verified`.
   - Automatically recalibrates site baseline upon moving card to `Cleaned & Verified`.
4. **2-Line Telemetry Graph (`dustwatch.reading.graph`):**
   - Line chart comparing `expected_kwh` vs `actual_kwh` over time, visually exposing soiling sag and post-clean rebounds.

---

## 6. Security & Role-Based Access Control (RBAC)

| User Group | Technical XML ID | Model Access Permissions |
|---|---|---|
| **Cleaning Crew / Field Technician** | `group_dustwatch_user` | Read all sites; Read/Write daily readings; Read/Write cleaning jobs (cannot delete). |
| **Operations Manager / Admin** | `group_dustwatch_manager` | Full CRUD on all DustWatch models, tariffs, and configuration. |
| **Solar Asset Customer (Portal)** | `group_dustwatch_portal` | Read-only access restricted via record rule to `partner_id == user.partner_id`. |

---

## 7. AI Agent Collaboration Protocol (SSOT Rules)

All human developers and autonomous AI assistants (Cursor, Claude Code, Antigravity, GitHub Copilot) working in this repository **MUST adhere to the following rules**:

1. **Zero Schema Deviation:** Do NOT alter model names, field names, or field types specified in Section 3 without updating this specification document first.
2. **Odoo 19 Compatibility:**
   - Use `list` instead of `tree` in XML view definitions (Odoo 19 standard).
   - Do NOT use deprecated `@api.one` or `_columns` syntax. Use modern `@api.depends` and compute methods.
   - Use `fields.Date.context_today(self)` for date defaults.
3. **Git Branching Strategy:**
   - `main`: Production-ready, validated code only.
   - `feat/odoo-models`: Backend ORM and calculation methods.
   - `feat/odoo-views`: XML views, actions, and menus.
   - `feat/data-generator`: CSV telemetry simulators and demo scripts.
   - `feat/canva-presentation`: Pitch deck narrative, ROI slide assets, and demo scripts.
4. **Commit Message Format:**
   - `feat(models): implement calculation 6.6 recovery audit in job.py`
   - `fix(views): add progress bar widget to site kanban view`
   - `docs(spec): update breakeven mathematical proof`

---

## 8. 48-Hour Hackathon Delivery Roadmap

- **Hour 0–12 (Architecture & Foundation):** Lock models, manifest, security matrix, and initial sample CSV. (COMPLETED)
- **Hour 12–24 (Views & Ingestion):** Verify UI views in Odoo, test CSV wizard, validate color decorators.
- **Hour 24–36 (Choreographed Demo & Canva Deck):** Build 12-slide pitch deck in Canva, calibrate Grand Hyatt Hotel demo dataset.
- **Hour 36–48 (Rehearsal & Polish):** 5-minute timed live pitch rehearsal, Q&A defense drill, release tagging on Git.
