# SHOC SOP Portal
A secure, structured, and user‑friendly Streamlit application for accessing the Standard Operating Procedures (SOPs) of the SADC Humanitarian and Emergency Operations Centre (SHOC). The portal consolidates all Main SOPs, Annexes, Toolkits, Templates, and the Training Manual into a single, intuitive interface designed for operational readiness and rapid access.

## Overview
The SHOC SOP Portal provides a unified environment for staff, partners, and stakeholders to navigate the full SOP ecosystem. It ensures consistent access to official documents, supports browser‑based previews, and maintains a fixed, logical ordering of SOP Volumes that aligns with SHOC’s operational framework. The portal is optimized for use across macOS, Windows, Linux, and mobile browsers.

## Key Features
Fixed left‑to‑right, top‑to‑bottom ordering of all nine SOP Volumes.

Includes the SOP Training Manual as a full SOP entry.

Single multi‑password gate for secure access.

Automatic linking of SOPs to their corresponding Toolkit and Template folders.

PDF preview using browser‑native rendering.

DOCX preview using python‑docx.

Download support for all allowed file types.

Back and Main Page navigation for smooth user experience.

Lightweight, cross‑platform compatibility.

## Repository Structure
```
SOPs/
 └── 1.1/
      ├── SOP Governance Finance and Audit/
      ├── SOP Multi_Hazard Early Warning and Monitoring/
      ├── SOP Emergency Telecommunications/
      ├── SOP Emergency Response Teams/
      ├── SOPs Human Resources/
      ├── SOP Information Communication and Technology/
      ├── SOP Access Security and Assett Management/
      ├── SOP Supply Management and Logistics/
      ├── SOP Business Continuity Management/
      ├── SOP Training Manual/
      ├── Toolkit/
      │     └── <Toolkit folders matching SOP names>
      └── Toolkit/Templates/
            └── <Template folders matching SOP names>
```
Toolkit and Template folder names must match SOP folder names exactly.

## Installation and Local Execution
Install dependencies:

```bash
python -m pip install -r requirements.txt
```
Run the portal locally:

```bash
python -m streamlit run shoc_sop_portal_secured.py
```

##  Deployment on Streamlit Cloud
Push the repository to GitHub.

Deploy the app via Streamlit Cloud.

Add your secrets under App Settings → Secrets:

```bash
APP_PASSWORDS = ["Password1", "Password2", "Password3"]
```
Streamlit Cloud will automatically install dependencies and redeploy.

##  Requirements
```bash
streamlit>=1.32.0
python-docx>=1.1.0
```

##  Maintenance and Updates
Add new SOPs by creating a folder under SOPs/1.1/ and updating the fixed order list in the script if needed.

Toolkit and Template folders must match SOP names exactly.

PDF previews rely on browser rendering; no additional PDF libraries are required.

Secrets must never be committed to GitHub.

##  Usage Restrictions
This portal is an internal SHOC operational tool. Redistribution, modification, or public hosting is not permitted without authorization.