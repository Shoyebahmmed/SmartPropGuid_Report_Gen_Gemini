# SmartPropGuide ◆ Report Engine

An enterprise-grade Pre-Sales Manual Compilation & AI Generation tool built with **Python** and **Streamlit**. This repository automates the processing of customer property search requests, handles manual operator data compilation, and utilizes advanced generative AI models to compose beautifully structured, publication-ready real estate evaluation reports[cite: 3].

---

## 🏗️ System Architecture & Workflow

The platform handles the manual collection workflow in a streamlined 3-step pipeline designed for pre-sales operators[cite: 3]:

### 📋 1. Customer Preferences Intake
* Captures explicit user property criteria: target location/postcode, property layouts, exact budget distributions, and intention parameters (Owner-Occupier vs. Investor)[cite: 3].
* Evaluates secondary priority weights using an interactive grid checklist mapping core environmental and lifestyle metrics (e.g., school boundaries, public transit access, proximity to the CBD, flood and bushfire risks)[cite: 3].

### 📂 2. Data & Template Upload
* **Source Data Integration**: Supports direct uploads of manual operator data compilations via CSV or Excel (`.xlsx`, `.xls`) listings[cite: 3].
* **Report Layout Pre-sets**: Injects customized HTML template files dynamically[cite: 3]. Falls back automatically to the standard enterprise `sample_template.html` template when an alternative layout isn't loaded[cite: 3].
* **Operational Control Layer**: Provides custom directive text fields for operators to tell the AI model exactly what to prioritize during generation (e.g., target capital growth trajectories or transit vectors)[cite: 3].

### ✨ 3. AI Report Generation & Compilation
* Leverages the `gemini-2.5-flash` model to analyze historical and current listings against customer inputs[cite: 3].
* Dynamically parses textual data streams, processes structured listings rows, maps scores, and handles real-time HTML string rendering[cite: 3].
* Seamlessly compiles raw HTML code into professional, portable documents using `xhtml2pdf` for local download[cite: 3].

---

## 🎨 Enterprise UI Design System

The application implements a custom dual-theme architecture supporting high-contrast Dark and Light view modes[cite: 3]:
* **Dark Mode**: Sleek zinc-palette aesthetics optimized for extended night usage[cite: 3].
* **Light Mode**: Reconfigured typography, card elements, and form label bindings to lock text colors to rich high-contrast tones, ensuring readability[cite: 3].
* **Layout Isolation**: Default stream headers, toolbars, and branding footprints are isolated via deep CSS injections to deliver a branded interface[cite: 3].

---

## 🛣️ Development Roadmap

This roadmap outlines the past milestones, current active sprints, and upcoming features for the SmartPropGuide engine.

| Phase | Milestone | Status |
| :--- | :--- | :--- |
| **Phase 1: Foundation** | UI/UX Core Architecture & Frontend Framework | ✅ Done |
| | Integration of Gemini API Pipeline | ✅ Done |
| | Report Generation PDF Export Module | ✅ Done |
| **Phase 2: Validation** | Backend Data Sync: Excel Intake Form | 🚧 In Progress |
| | Full E2E Integration Testing | 🚧 In Progress |
| | User Acceptance Testing (UAT) | ⏳ Pending |
| **Phase 3: Optimization** | Template Dynamic Styling Modules | ⏳ Pending |
| | Automated Email Delivery System | ⏳ Pending |

---

## 🚀 Execution & Setup

### Prerequisites
Ensure your local environment is running Python 3.9+ and contains an active Gemini API credential key[cite: 3].

### Installation
1. Clone your repository:
   ```bash
   git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
   cd your-repo-name
