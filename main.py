import time
# LexAI Main Server Entrypoint
import os, io, asyncio, aiohttp, logging, base64, uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import json
import threading
from functools import lru_cache
from passlib.context import CryptContext
import jwt
from email_validator import validate_email, EmailNotValidError
import bcrypt

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — fall back to real env vars

import chromadb
from chromadb.utils import embedding_functions

from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File, Form, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logger import logger, log_api_call, log_security_event, log_pdf_generation, log_error
import database as db

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploaded_docs")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ══════════════════════════════════════════════════
#  CONFIG — all secrets loaded from environment
# ══════════════════════════════════════════════════
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Add it to your .env file:\n"
        "  GROQ_API_KEY=gsk_your_key_here"
    )

# ══════════════════════════════════════════════════
#  PDF GENERATOR — import from same directory
# ══════════════════════════════════════════════════
try:
    from pdf_generator import (
        generate_ntn_pdf,
        generate_itr_pdf,
        generate_wealth_pdf,
        generate_affidavit_pdf,
        generate_wakalatnaama_pdf,
        generate_tenancy_pdf,
        generate_employment_contract_pdf,
        generate_legal_document_pdf,
    )
    PDF_AVAILABLE = True
    logger.info("✓ PDF generator loaded from pdf_generator.py")
except ImportError as e:
    PDF_AVAILABLE = False
    logger.warning(f"⚠ pdf_generator.py not found: {e}. PDF endpoints will return 503.")


# ══════════════════════════════════════════════════
#  RAG LEGAL KNOWLEDGE BASE
# ══════════════════════════════════════════════════
LEGAL_KB = {
  "Pakistan": {

    "Tenant Rights": """
PAKISTAN TENANT RIGHTS — KEY STATUTES
1. PUNJAB RENTED PREMISES ACT 2009 (PRPA)
   - Section 4: Written tenancy agreement mandatory
   - Section 7: Rent increase max 10%/year; 30-day written notice required
   - Section 9: Minimum 30-day eviction notice
   - Section 14: Eviction ONLY through Rent Controller court — self-help eviction is a criminal offence
   - Section 17: Landlord responsible for structural repairs
   - Section 22: Security deposit cannot exceed 2 months rent; must be returned within 30 days of vacating
2. SINDH RENTED PREMISES ORDINANCE 1979 — Rent Controller has jurisdiction; 90-day notice for tenants >5 years
3. REMEDIES: File with Rent Controller (District Court); mediation under ADR Act 2017; civil suit under Contract Act 1872
4. HARASSED BY LANDLORD: Lodge FIR under Section 448 PPC (criminal trespass) if landlord enters without permission
""",

    "Murder & Homicide": """
PAKISTAN MURDER LAW — PPC 1860 & QISAS/DIYAT ORDINANCE
1. SECTION 299 PPC — DEFINITIONS:
   - Qatl-i-Amd (intentional murder): deliberate killing
   - Qatl-i-Shibh-Amd: quasi-intentional (no intent to kill but act likely to cause death)
   - Qatl-i-Khata: killing by mistake / accident
   - Qatl-bis-Sabab: killing by indirect cause
2. SECTION 302 PPC — PUNISHMENT FOR QATL-I-AMD (Murder):
   - Qisas (retaliation — death penalty) if wali (heir) demands
   - Diyat (blood money) if wali forgives — currently PKR approx. 20 million (revised annually)
   - Tazir: imprisonment up to death or life if Qisas not applicable
3. SECTION 306 PPC: Qatl where Qisas not applicable (e.g. killing own child) — up to 25 years + Diyat
4. SECTION 307 PPC: Attempt to murder — up to 10 years + fine; if hurt caused, up to death
5. SECTION 308 PPC: Wali may compound (forgive) — accused still liable to Tazir imprisonment
6. INVESTIGATION & PROCEDURE:
   - FIR under Section 154 CrPC at nearest police station — mandatory and free
   - Police must investigate and file challan within 14 days (Section 173 CrPC)
   - Sessions Court has jurisdiction; death penalty confirmed by High Court
   - Anti-Terrorism Act 1997 applies if murder has terrorist nexus
7. RIGHTS OF VICTIM'S FAMILY (WALI):
   - Right to demand Qisas, accept Diyat, or forgive
   - Cannot be pressured — forgiveness must be voluntary
   - Wali includes spouse, children, parents, siblings
8. DEFENCES: Self-defence (Section 96–106 PPC), sudden provocation (Section 302 Exception), unsoundness of mind (Section 84)
""",

    "Rape & Sexual Assault": """
PAKISTAN RAPE & SEXUAL VIOLENCE LAW
1. ANTI-RAPE (INVESTIGATION & TRIAL) ACT 2021 — LANDMARK REFORM:
   - Special Courts for Rape Cases established in every district
   - Time-bound trial: must conclude within 4 months
   - Victim identity protected — name cannot be published
   - Two-finger test (virginity test) BANNED
   - DNA evidence mandatory — Section 164-B CrPC
2. SECTION 375 PPC (as amended 2021) — RAPE DEFINED:
   - Sexual intercourse with woman against her will or without consent
   - With a woman under 16 years (statutory rape — consent irrelevant)
   - Includes gang rape, rape of a minor, rape by person in authority
3. SECTION 376 PPC — PUNISHMENT:
   - Minimum 10 years, maximum 25 years rigorous imprisonment + fine
   - Gang rape: death or life imprisonment
   - Rape of minor under 12: death or life imprisonment
   - Repeat offender: castration (surgical) on court order
4. ZAINAB ALERT, RESPONSE AND RECOVERY ACT 2020:
   - Mandatory alert system for missing children
   - Applies nationwide; penalty for non-reporting by officials
5. PROTECTION OF WOMEN (CRIMINAL LAWS AMENDMENT) ACT 2006: Sexual harassment criminalised
6. REPORTING A RAPE:
   - File FIR at any police station — police CANNOT refuse (Section 154 CrPC)
   - If police refuse: go directly to Judicial Magistrate under Section 22-A CrPC
   - Medical examination: must be conducted by female doctor if victim is female
   - DNA sample must be collected within 72 hours for best evidence
   - Victim has right to legal aid lawyer (Section 13 Anti-Rape Act 2021)
   - Prosecution Witness Protection Programme available
7. MARITAL RAPE: not explicitly criminalised under current PPC but Protection of Women Act 2006 provides civil remedies
8. ACID ATTACKS: Section 336-A/B PPC — minimum 14 years, maximum life; Section 336-B: up to life imprisonment
9. MANDATORY PROCEDURAL ADVICE FOR THE ACCUSED:
   - If you have committed a crime or are accused of one, you must turn yourself in to the nearest police station immediately.
   - Obtain a qualified criminal defense lawyer to represent you.
   - Cooperate with legal authorities; DNA testing is mandatory in rape cases.
   - Do not attempt to hide evidence or evade the law, as this will result in additional charges.
""",

    "Kidnapping & Abduction": """
PAKISTAN KIDNAPPING & ABDUCTION LAW — PPC 1860
1. SECTION 359 PPC — DEFINITIONS:
   - Kidnapping from Pakistan: takes person outside Pakistan without consent
   - Kidnapping from lawful guardianship: takes minor (under 14 male, under 16 female) from guardian without consent
2. SECTION 363 PPC: Punishment for kidnapping — up to 7 years + fine
3. SECTION 364 PPC: Kidnapping for ransom — death or life imprisonment
4. SECTION 364-A PPC: Kidnapping/abduction of child under 14 — death or life imprisonment + fine
5. SECTION 365 PPC: Kidnapping to murder — death or life imprisonment
6. SECTION 365-A PPC: KIDNAPPING FOR RANSOM (most common):
   - Death penalty OR life imprisonment + forfeiture of property
7. SECTION 366 PPC: Kidnapping/abduction of woman to compel marriage — up to 10 years + fine
8. SECTION 369 PPC: Kidnapping child under 10 to steal from person — up to 7 years
9. ANTI-TERRORISM ACT 1997 Section 7: Kidnapping with terrorist nexus — ATC court; stricter bail rules
10. PROCEDURE: FIR under 154 CrPC; police must register within 2 hours for child kidnapping cases
    - Zainab Alert Act 2020: mandatory alert for missing children under 18
""",

    "Robbery & Theft": """
PAKISTAN THEFT, ROBBERY & DACOITY — PPC 1860
1. SECTION 378 PPC — THEFT: dishonest taking of movable property without consent
   - Section 379: Punishment — up to 3 years + fine
   - Section 380: Theft in dwelling house — up to 7 years
   - Section 381: Theft by clerk/servant — up to 7 years
2. SECTION 390 PPC — ROBBERY: theft + causing hurt or wrongful restraint
   - Section 392: Punishment — up to 10 years; highway robbery up to 14 years
   - Section 393: Attempt to rob — up to 7 years
3. SECTION 391 PPC — DACOITY: robbery by 5 or more persons
   - Section 395: Punishment — up to 10 years or life + fine
   - Section 396: Dacoity with murder — death or life imprisonment
   - Section 397: Using deadly weapon during robbery/dacoity — minimum 7 years
4. HADD PUNISHMENT (Hudood Ordinance 1979):
   - Hadd for theft: amputation of right hand — only if Nisab (threshold) met and conditions of evidence satisfied
   - Rarely applied; Tazir (discretionary) punishment more common
5. REPORTING: FIR under Section 154 CrPC; Sessions Court has jurisdiction for robbery/dacoity
""",

    "Drug Offences": """
PAKISTAN DRUG OFFENCES — CNSA 1997
1. CONTROL OF NARCOTIC SUBSTANCES ACT 1997 (CNSA):
   - Section 6: Trafficking narcotics — death or life imprisonment + forfeiture
   - Section 7: Manufacturing — death or life imprisonment
   - Section 8: Possession for sale — up to life imprisonment
   - Section 9: Possession/consumption — up to 2 years (small quantity) or up to 7 years (larger)
2. QUANTITY THRESHOLDS (Section 9):
   - 10g heroin or less — up to 2 years OR fine OR both
   - 10g to 1kg heroin — 2 to 10 years + fine
   - Over 1kg heroin — life imprisonment or death
3. ANF (Anti-Narcotics Force) has investigative jurisdiction
4. Special Courts under CNSA handle drug cases
5. No bail for trafficking charges in most circumstances
""",

    "Terrorism": """
PAKISTAN ANTI-TERRORISM LAW — ATA 1997
1. ANTI-TERRORISM ACT 1997 (as amended):
   - Section 6: Definition of terrorism — acts causing fear, insecurity, disorder in society
   - Section 7: Punishment — death or life imprisonment for acts causing death; up to 14 years for others
   - Section 11: Membership of terrorist organisation — up to 10 years
   - Section 11-H: Financing terrorism — up to 14 years + forfeiture
2. ANTI-TERRORISM COURTS (ATC):
   - Special dedicated courts in each province
   - Time-bound trials — 7 working days per hearing
   - No adjournments except in exceptional circumstances
3. SCHEDULE I: Proscribed organisations — NACTA maintains list
4. FAIR TRIAL ACT 2013: Surveillance warrants for terrorism suspects; evidence admissibility
5. NATIONAL ACTION PLAN (NAP): 20-point counter-terrorism framework
6. BAIL: ATCs rarely grant bail for serious terrorism charges
""",

    "Cybercrime": """
PAKISTAN CYBERCRIME — PECA 2016
1. PREVENTION OF ELECTRONIC CRIMES ACT 2016 (PECA):
   - Section 3: Unauthorised access to information system — up to 3 months + fine
   - Section 4: Unauthorised copying of data — up to 6 months + fine
   - Section 7: Malicious code (viruses, ransomware) — up to 2 years
   - Section 9: Cyber terrorism — up to 14 years
   - Section 10: Electronic fraud — up to 2 years + fine
   - Section 11: Unauthorised interception — up to 2 years
   - Section 20: Offences against dignity (morphing, revenge porn) — up to 3 years + fine
   - Section 21: Harassment via electronic means — up to 1 year + fine
   - Section 22-A: Hate speech online — up to 7 years
2. FIA CYBERCRIME WING: primary investigating authority — cybercrime.gov.pk
   - Online complaint portal available
3. DEFAMATION ONLINE: Section 20 PECA + Section 499/500 PPC
4. CHILD PORNOGRAPHY: Section 22 PECA — up to 7 years; mandatory reporting
""",

    "Employment Law": """
PAKISTAN EMPLOYMENT LAW
1. INDUSTRIAL & COMMERCIAL EMPLOYMENT ORDINANCE 1968:
   - Section 11: Termination — 30 days notice or one month pay in lieu
   - Probation: max 3 months (extendable to 6)
2. PAYMENT OF WAGES ACT 1936: Wages by 7th of month; deductions strictly limited
3. SHOPS & ESTABLISHMENTS ORDINANCE (Punjab 1969): Max 48 hours/week; overtime at 125%
4. EOBI (Employees Old-Age Benefits Institution): Mandatory; employer 5% + employee 1%
5. MATERNITY BENEFITS ORDINANCE 1958: 12 weeks paid leave; cannot be dismissed during pregnancy
6. UNFAIR DISMISSAL: Labour Court complaint within 3 years; up to 36 months compensation
7. SINDH EMPLOYEES SOCIAL SECURITY ACT 2017 / PUNJAB EMPLOYEES SOCIAL SECURITY ORDINANCE 1965
""",

    "Family Law": """
PAKISTAN FAMILY LAW
1. MUSLIM FAMILY LAWS ORDINANCE 1961:
   - Section 7: Talaq — notice to Union Council within 30 days; 90-day reconciliation period
   - Section 9: Maintenance via Union Council if husband defaults
   - Khula: wife initiated divorce through Family Court; may require returning Mehr
   - Mehr (Dower): wife's exclusive right; recoverable as debt
2. FAMILY COURTS ACT 1964: Exclusive jurisdiction over matrimonial disputes; 6-month target
3. GUARDIANS & WARDS ACT 1890: Haq-e-Hizanat — mother custody: sons till 7, daughters till puberty
4. DOMESTIC VIOLENCE (PREVENTION & PROTECTION) ACT 2012 (Punjab):
   - Protection orders, residence orders, monetary relief
   - Police can arrest without warrant in cases of imminent danger
5. CHILD MARRIAGE RESTRAINT ACT 1929 (amended Punjab 2015): Minimum age 18
6. DOWRY & BRIDAL GIFTS ACT 1976: Dowry articles belong exclusively to wife
""",

    "Property Law": """
PAKISTAN PROPERTY LAW
1. TRANSFER OF PROPERTY ACT 1882: Written registered deed required for all immovable property transfers
2. REGISTRATION ACT 1908: Mandatory registration at Sub-Registrar; unregistered deed inadmissible in court
3. STAMP DUTY: Punjab — 2% urban, 1% rural; Sindh — 3%; CVT 2% in major cities
4. LAND REVENUE ACT 1967 (Punjab): Mutation (Intiqal) at Patwari; Fard-e-Malkiat (ownership certificate)
5. ILLEGAL DISPOSSESSION ACT 2005: Executive Magistrate can restore possession within 30 days
6. FBR WITHHOLDING ON PROPERTY: 2% filer / 4% non-filer (purchase value >PKR 5 million)
7. BENAMI TRANSACTIONS (PROHIBITION) ACT 2017: Criminal liability for benami property; up to 7 years
""",

    "Business Registration": """
PAKISTAN BUSINESS REGISTRATION
1. SOLE PROPRIETORSHIP: NTN from FBR; trade name registration with district authority
2. PRIVATE LIMITED COMPANY (Companies Act 2017 — SECP):
   - 2–50 shareholders; min capital PKR 100,000
   - Register at SECP eServices; documents: MOA, AOA, Form-A, Form-29
   - 3–5 working days processing
3. SINGLE MEMBER COMPANY: One-person limited liability; min PKR 100,000
4. PARTNERSHIP (Partnership Act 1932): Written deed; register with Registrar of Firms
5. FBR: NTN at iris.fbr.gov.pk; STRN if turnover >PKR 10 million
6. PRA/SRB: Service tax registration for Punjab/Sindh based service providers
""",

    "Criminal Procedure": """
PAKISTAN CRIMINAL PROCEDURE — CrPC 1898
1. FIR (Section 154): Free at any police station; cannot be refused
   - Refusal: complain to DSP/SP or directly to Judicial Magistrate (Section 22-A CrPC)
   - E-FIR available in Punjab via Punjab Police app
2. ARREST RIGHTS: Know grounds (Section 50); inform family/lawyer (Section 50-A); max 24-hour detention without Magistrate order
3. REMAND: Police remand max 2 days ordinary cases, 8 days ANF/ATC cases; judicial remand 14 days
4. BAIL: Bailable — right from police; Non-bailable — Sessions Court or High Court
   - Pre-arrest bail (Section 498-A): apply to Sessions/High Court
5. TRIAL COURTS: Magistrate (offences up to 3 years); Sessions (serious offences); High Court (death/life cases on reference)
6. RIGHTS: Article 10A Constitution — fair trial; habeas corpus to High Court if illegally detained
7. LEGAL AID: District Bar Associations; Pakistan Bar Council Legal Aid Committee; NCHR
""",

    "Domestic Violence": """
PAKISTAN DOMESTIC VIOLENCE LAW
1. DOMESTIC VIOLENCE (PREVENTION & PROTECTION) ACT 2012 (Punjab):
   - Covers: physical, emotional, psychological, sexual violence within household
   - Protection Order: restraining abuser from entering home or contacting victim
   - Residence Order: victim retains right to reside in matrimonial home
   - Monetary Relief Order: maintenance + medical expenses
2. SINDH DOMESTIC VIOLENCE (PREVENTION & PROTECTION) ACT 2013: Similar provisions
3. CRIMINAL REMEDIES:
   - Physical assault: Section 337-A to 337-N PPC (various hurt offences)
   - Grievous hurt: Section 335 PPC — up to 10 years
   - Criminal intimidation: Section 506 PPC — up to 7 years
4. HOW TO REPORT:
   - Call 1099 (Women's Helpline — Punjab) or 1043 (Punjab Police)
   - File FIR at nearest police station — police can arrest without warrant if imminent danger
   - Apply for Protection Order at Family Court (no court fee)
   - Darul Aman (shelter homes) available in all districts
5. WOMEN PROTECTION AUTHORITY (Punjab): Oversight body; complaint mechanism
""",

    "Consumer Rights": """
PAKISTAN CONSUMER RIGHTS
1. PUNJAB CONSUMER PROTECTION ACT 2005: Consumer Courts at district level; 90-day decision
2. SINDH CONSUMER PROTECTION ACT 2014; KP CONSUMER PROTECTION ACT 2019
3. DEFECTIVE GOODS: Replacement/refund; manufacturer + seller jointly liable; file within 3 years
4. BANKING OMBUDSMAN: Free; decisions binding; sbp.org.pk
5. FEDERAL OMBUDSMAN (WAFAQI MOHTASIB): Free; federal government agencies
6. FIA: Online fraud, e-commerce scams — cybercrime.gov.pk; dial 9911
7. COMPETITION COMMISSION OF PAKISTAN (CCP): Cartel/monopoly complaints
""",

    "Contract Law": """
PAKISTAN CONTRACT LAW — CONTRACT ACT 1872
1. ESSENTIALS (Section 10): Free consent, competent parties (18+, sound mind), lawful object and consideration
2. VOID CONTRACTS: Agreement by minor, unsound mind, unlawful object, wagering (Section 30)
3. FREE CONSENT VITIATING FACTORS: Coercion, undue influence, fraud, misrepresentation, mistake
4. BREACH REMEDIES: Damages (Section 73 — foreseeable loss), specific performance (Specific Relief Act 1877)
5. LIMITATION: Written contract 6 years; oral 3 years; property contracts 12 years (Limitation Act 1908)
6. DIGITAL CONTRACTS: Electronic Transactions Ordinance 2002 — e-signatures legally valid
7. PENALTY CLAUSES: Courts may reduce unconscionable penalties (Section 74)
""",

    "Blasphemy & Religious Offences": """
PAKISTAN BLASPHEMY LAWS — PPC 1860
1. SECTION 295 PPC: Injuring or defiling place of worship — up to 2 years + fine
2. SECTION 295-A PPC: Deliberate acts to outrage religious feelings — up to 10 years + fine
3. SECTION 295-B PPC: Defiling Holy Quran — life imprisonment
4. SECTION 295-C PPC: Defiling name of Prophet Muhammad (PBUH) — death or life imprisonment
5. SECTION 298 PPC: Uttering words to wound religious feelings — up to 1 year + fine
6. SECTION 298-A: Derogatory remarks re companions of Prophet — up to 3 years
7. SECTION 298-B/C: Ahmadi-specific religious restrictions
8. PROCEDURE:
   - Only Sessions Court can try Section 295-C cases
   - FIR requires Superintendent of Police (SP) authorisation
   - Supreme Court guidelines (Sajjad Hussain case 2023): FIR registration requires preliminary inquiry
9. MISUSE PROTECTION: Supreme Court in Asia Bibi case emphasised need for caution; false accusations are themselves an offence
""",

    "Corruption & White Collar Crime": """
PAKISTAN ANTI-CORRUPTION LAW
1. NATIONAL ACCOUNTABILITY BUREAU ORDINANCE 1999 (NAB/NABO):
   - Jurisdiction: corruption, corrupt practices, loan defaults, misuse of authority
   - Section 9: Punishment — up to 14 years + disgorgement + disqualification from public office
   - Voluntary Return: accused can return corruption proceeds in exchange for prosecution withdrawal
   - NAB Amendment Act 2022: jurisdiction reduced — private sector, small amounts removed
2. PREVENTION OF CORRUPTION ACT 1947 (PCA):
   - Governs public servants; FIA has jurisdiction
   - Section 5: Criminal misconduct by public servant — up to 7 years
3. ANTI-MONEY LAUNDERING ACT 2010 (AMLA):
   - Section 3: Money laundering — up to 10 years + forfeiture
   - FATF Compliance measures apply
4. FBR ENFORCEMENT: Tax evasion — Section 192 Income Tax Ordinance — up to 5 years + fine
5. COMPLAINT MECHANISM:
   - NAB: nab.gov.pk; 1800-ANTINAB (toll-free)
   - FIA: fia.gov.pk; public accountability wing
   - ACE (Anti-Corruption Establishment): Provincial; Punjab ACE most active
""",

    "Juvenile Justice": """
PAKISTAN JUVENILE JUSTICE — JJSO 2018
1. JUVENILE JUSTICE SYSTEM ACT 2018 (JJSO):
   - Applies to persons under 18 years at time of offence
   - Section 4: No death penalty or life imprisonment for juveniles
   - Section 7: Diversion — first-time minor offences resolved without formal prosecution
   - Section 9: Separate Juvenile Courts mandatory in all sessions divisions
   - Section 13: Remand — juvenile must be sent to Juvenile Rehabilitation Centre, NOT adult prison
   - Section 17: Probation preferred over imprisonment for juveniles
2. AGE DETERMINATION: Medical board assessment if date of birth disputed; benefit of doubt to juvenile
3. RIGHTS OF JUVENILE:
   - Right to legal aid from state if cannot afford lawyer
   - Parents/guardian must be informed immediately upon arrest
   - Cannot be handcuffed or put in stocks
   - Cannot be tried jointly with adults
4. REHABILITATION CENTRES: In each district; education and skill development mandatory
""",
  },

  # ─────────────────────────────────────────────
  "United Kingdom": {
    "Tenant Rights": """
UK TENANT RIGHTS
1. HOUSING ACT 1988: Assured Shorthold Tenancy most common; Section 21 no-fault eviction being abolished (Renters Reform Bill)
2. TENANT FEES ACT 2019: Most letting fees banned; deposit capped 5 weeks rent
3. LANDLORD & TENANT ACT 1985 Section 11: Landlord must repair structure, heating, water
4. DEPOSIT: Protected in TDS/DPS/MyDeposits within 30 days; failure = 1–3x compensation
5. ILLEGAL EVICTION: Criminal offence under Protection from Eviction Act 1977
""",
    "Employment Law": """
UK EMPLOYMENT LAW
1. EMPLOYMENT RIGHTS ACT 1996: Unfair dismissal after 2 years; up to £115,115 compensation
2. EQUALITY ACT 2010: 9 protected characteristics; direct + indirect discrimination unlawful
3. NATIONAL MINIMUM WAGE: £11.44/hr (25+, April 2024)
4. WORKING TIME REGULATIONS: 48-hour max week; 28 days paid leave
5. TRIBUNAL: ACAS Early Conciliation mandatory; 3-month claim deadline
""",
    "Criminal Law": """
UK CRIMINAL LAW
1. MURDER: Common law; mandatory life sentence; minimum tariff set by judge
2. RAPE: Sexual Offences Act 2003 Section 1 — maximum life imprisonment
3. ASSAULT: Common assault (Section 39 CJA 1988) — 6 months; ABH (Section 47 OAPA 1861) — 5 years; GBH (Section 18) — life
4. THEFT: Theft Act 1968 — up to 7 years; robbery up to life
5. DOMESTIC ABUSE: Domestic Abuse Act 2021 — coercive control criminalised; up to 5 years
6. REPORTING: Call 999 (emergency) or 101 (non-emergency); report online at police.uk
7. VICTIM SUPPORT: Victims Commissioner; Legal Aid available (criminal cases)
""",
    "Family Law": """
UK FAMILY LAW
1. MARRIAGE ACT 1949: Requirements for valid marriage; Marriage (Same Sex Couples) Act 2013
2. DIVORCE: Divorce, Dissolution and Separation Act 2020 — no-fault divorce; 20-week minimum process
3. CHILDREN ACT 1989: Best interests of child paramount; parental responsibility; contact orders
4. DOMESTIC VIOLENCE: Non-Molestation Orders; Occupation Orders under Family Law Act 1996
5. FINANCIAL ORDERS: Matrimonial Causes Act 1973 — division of assets, maintenance (spousal + child)
6. CAFCASS: Children and Family Court Advisory and Support Service — welfare reports
""",
  },

  # ─────────────────────────────────────────────
  "United States": {
    "Criminal Law": """
US CRIMINAL LAW — FEDERAL & COMMON STATE PRINCIPLES
1. MURDER: Model Penal Code — First degree (premeditated) life/death; Second degree up to life
2. RAPE/SEXUAL ASSAULT: Varies by state; federal Sexual Abuse Act — up to life; most states 10–25 years minimum
3. ASSAULT: Simple assault misdemeanor; aggravated assault felony up to 20 years
4. ROBBERY: Federal Bank Robbery Act — up to 25 years; state laws similar
5. DRUG OFFENCES: Controlled Substances Act — Schedule I trafficking 10 years to life
6. DUE PROCESS: 4th Amendment (unreasonable search), 5th (self-incrimination), 6th (speedy trial, counsel)
7. MIRANDA RIGHTS: Must be read upon custodial interrogation
8. LEGAL AID: Public Defender if cannot afford attorney (Gideon v. Wainwright 1963)
""",
    "Employment Law": """
US EMPLOYMENT LAW
1. TITLE VII CIVIL RIGHTS ACT 1964: No discrimination — race, color, religion, sex, national origin; EEOC enforces
2. FLSA: Federal minimum wage $7.25; overtime 1.5x for >40 hours/week
3. FMLA: 12 weeks unpaid job-protected leave; firms with 50+ employees
4. ADA: Disability accommodation required
5. AT-WILL EMPLOYMENT: Most states; exceptions for discrimination, public policy
6. NLRA: Right to organise unions, collective bargaining
""",
    "Tenant Rights": """
US TENANT RIGHTS
1. FAIR HOUSING ACT: No discrimination — race, color, religion, sex, national origin, disability, familial status
2. SECURITY DEPOSIT: 1–2 months rent; return within 14–30 days with itemised deductions
3. HABITABILITY: Implied warranty in all states; remedies — rent withholding, repair & deduct
4. EVICTION: Unlawful detainer; tenant has right to hearing; self-help eviction illegal everywhere
5. VARIES BY STATE: California (AB 1482 rent control), New York (Rent Stabilisation), Texas (landlord-friendly)
""",
    "Family Law": """
US FAMILY LAW — VARIES BY STATE
1. DIVORCE: No-fault available in all states; equitable distribution or community property
2. CUSTODY: Best interests of child; joint vs sole; parenting plans
3. DOMESTIC VIOLENCE: VAWA (Violence Against Women Act); restraining orders in all states
4. CHILD SUPPORT: State guidelines based on income; enforced by state agencies
5. SAME-SEX MARRIAGE: Legal nationwide — Obergefell v. Hodges (2015)
""",
  },

  # ─────────────────────────────────────────────
  "United Arab Emirates": {
    "Criminal Law": """
UAE CRIMINAL LAW — FEDERAL PENAL CODE (DECREE-LAW 31 OF 2021)
1. MURDER: Article 332 — death penalty or life imprisonment; Diyat (blood money) in certain cases
2. RAPE: Article 363 — minimum 5 years; if victim under 18 or by multiple perpetrators, up to life/death
3. ASSAULT: Varying imprisonment + fines based on severity
4. DRUG OFFENCES: Federal Law 14/1995 — trafficking death penalty; possession up to life imprisonment
5. ALCOHOL: Permitted for non-Muslims in licensed venues; DUI — imprisonment + deportation for expats
6. CYBERCRIME: Cybercrime Law 2021 — online defamation up to 2 years + AED 500,000 fine
7. IMPORTANT: Sharia law applies for Muslims in personal status matters; civil law in commercial
8. REPORTING: Dubai Police app; 999 emergency; expats should involve embassy
""",
    "Employment Law": """
UAE LABOUR LAW — FEDERAL DECREE-LAW 33 OF 2021
1. EMPLOYMENT CONTRACT: Written mandatory; 3-year maximum fixed term (renewable)
2. WORKING HOURS: 8 hours/day, 48 hours/week; reduced during Ramadan
3. ANNUAL LEAVE: 30 calendar days after 1 year
4. GRATUITY (END OF SERVICE): 21 days per year for first 5 years; 30 days per year thereafter
5. TERMINATION: 30-day notice (1 year+); arbitrary dismissal entitles employee to 3 months compensation
6. DISPUTE: Ministry of Human Resources & Emiratisation (MOHRE); then Labour Court; mohre.gov.ae
7. DOMESTIC WORKERS: Protected under Federal Law 10/2017; 12-hour rest; 1 day off/week
""",
  },

  # ─────────────────────────────────────────────
  "India": {
    "Criminal Law": """
INDIA CRIMINAL LAW — IPC 1860 (now BHARATIYA NYAYA SANHITA 2023)
1. MURDER: Section 302 IPC / Section 101 BNS — death or life imprisonment
2. RAPE: Section 375/376 IPC / Section 63/64 BNS:
   - Minimum 10 years; maximum life or death (if victim under 12 or gang rape)
   - Criminal Law Amendment Act 2013 (Nirbhaya reforms) — stricter penalties
3. KIDNAPPING: Section 363 IPC — up to 7 years; for ransom Section 364A — death or life
4. DOMESTIC VIOLENCE: PWDVA 2005 — civil remedies; Protection Officers in every district
5. DOWRY HARASSMENT: Section 498-A IPC / Section 85 BNS — up to 3 years; dowry death Section 304-B — up to life
6. CYBERCRIME: IT Act 2000 — various offences; CERT-In regulates
7. REPORTING: 112 (all-India emergency); NCW for women complaints; cybercrime.gov.in
""",
    "Employment Law": """
INDIA EMPLOYMENT LAW — LABOUR CODES 2019–2020
1. CODE ON WAGES 2019: National minimum wage framework; overtime at 2x rate
2. INDUSTRIAL RELATIONS CODE 2020: Retrenchment compensation 15 days/year of service
3. CODE ON SOCIAL SECURITY 2020: ESIC, EPF, gratuity provisions consolidated
4. SEXUAL HARASSMENT: POSH Act 2013 — Internal Complaints Committee mandatory for 10+ employee firms
5. MATERNITY BENEFIT (AMENDMENT) ACT 2017: 26 weeks paid maternity leave
6. DISPUTE: Labour Commissioner; Industrial Tribunal; Labour Court
""",
  },

  # ─────────────────────────────────────────────
  "Canada": {
    "Criminal Law": """
CANADA CRIMINAL LAW — CRIMINAL CODE RSC 1985
1. MURDER: Section 235 — first degree: mandatory life (25 years minimum before parole); second degree: life (10–25 years minimum)
2. SEXUAL ASSAULT: Sections 271–273 — up to life imprisonment for aggravated sexual assault
3. ASSAULT: Section 266 — summary (18 months) or indictable (5 years)
4. ROBBERY: Section 344 — up to life imprisonment
5. DRUG OFFENCES: CDSA — trafficking max life; possession penalties reduced post-cannabis legalisation
6. CHARTER RIGHTS: Section 7 (life/liberty/security), Section 8 (unreasonable search), Section 10 (right to counsel)
7. LEGAL AID: Available in all provinces for serious criminal charges
""",
    "Employment Law": """
CANADA EMPLOYMENT LAW
1. CANADA LABOUR CODE (Federal): Applies to federally regulated industries (banks, airlines, telecoms)
2. PROVINCIAL: Employment Standards Acts in each province govern hours, wages, termination
3. HUMAN RIGHTS: Canadian Human Rights Act (federal); provincial codes cover accommodation, discrimination
4. MINIMUM WAGE: Varies by province ($16.55–$17.40/hr, 2024); Federal $17.30/hr
5. WRONGFUL DISMISSAL: Common law — reasonable notice (1 month/year of service typical)
6. EMPLOYMENT INSURANCE (EI): 55% of insurable earnings for up to 45 weeks
""",
  },

  # ─────────────────────────────────────────────
  "Australia": {
    "Criminal Law": """
AUSTRALIA CRIMINAL LAW — VARIES BY STATE
1. MURDER: All states — maximum life imprisonment; mandatory life in some jurisdictions
2. RAPE/SEXUAL ASSAULT: Maximum life imprisonment; federal Criminal Code Act for cross-border offences
3. ASSAULT: Common assault up to 2 years; aggravated up to 7–10 years (state dependent)
4. DRUG OFFENCES: State-based + Commonwealth Criminal Code; trafficking up to life
5. DOMESTIC VIOLENCE: Family Violence Protection Acts in each state; safety notices, intervention orders
6. REPORTING: 000 (emergency); 131 444 (police non-emergency); 1800RESPECT for DV
7. LEGAL AID: Legal Aid commissions in each state; duty solicitor at courts
""",
    "Employment Law": """
AUSTRALIA EMPLOYMENT LAW — FAIR WORK ACT 2009
1. NATIONAL EMPLOYMENT STANDARDS (NES): 11 minimum entitlements including 4 weeks annual leave, 10 days personal leave
2. MINIMUM WAGE: $23.23/hr (2024 National Minimum Wage)
3. UNFAIR DISMISSAL: Fair Work Commission; minimum 6 months employment; compensation up to 26 weeks pay
4. GENERAL PROTECTIONS: Cannot dismiss for union activity, illness, parental leave
5. ENTERPRISE AGREEMENTS: Bargained above award; must pass better-off overall test
6. WORKPLACE HEALTH & SAFETY: Safe Work Australia; model WHS laws adopted by most states
""",
  },

  # ─────────────────────────────────────────────
  "Saudi Arabia": {
    "Criminal Law": """
SAUDI ARABIA CRIMINAL LAW — SHARIA + ROYAL DECREES
1. LEGAL SYSTEM: Based on Quran, Sunnah, and Royal Decrees; no codified penal code (Nizami system)
2. HADD CRIMES (fixed punishments):
   - Theft (above nisab ~SR 6,000): amputation (rarely applied; strict evidence rules)
   - Adultery/Fornication: requires 4 witnesses — almost impossible to prove; false accusers flogged
   - Robbery: amputation + cross-amputation
   - Murder: Qisas — death penalty if wali demands; Diyat (blood money) if forgiven
3. TAZIR CRIMES: Discretionary penalties; include imprisonment, fines, deportation for expats
4. DRUG OFFENCES: Death penalty for trafficking (regularly carried out); imprisonment for possession
5. CYBERCRIME: Anti-Cybercrime Law 2007 — up to 4 years for online defamation
6. FOR EXPATS: Embassy registration advised; Saudi Arabia Transparency & Anti-Corruption Centre (Nazaha) for corruption complaints
7. REFORMS (Vision 2030): Entertainment loosened; women driving legalised; Public Investment Fund oversight
""",
    "Employment Law": """
SAUDI ARABIA EMPLOYMENT LAW — LABOUR LAW RD M/51 2005
1. CONTRACT: Written in Arabic; 2-year maximum fixed term (renewable once)
2. WORKING HOURS: 8 hrs/day, 48 hrs/week; 36 hrs/week in Ramadan
3. ANNUAL LEAVE: 21 days (1–5 years service); 30 days (5+ years)
4. END OF SERVICE: 0.5 month/year for first 5 years; 1 month/year thereafter (if not resigned)
5. SAUDISATION (NITAQAT): Mandatory percentage of Saudi nationals in workforce; varies by industry
6. DISPUTE: Ministry of Human Resources & Social Development; Labour Courts
7. DOMESTIC WORKERS: Protected under DW regulations 2013; cannot confiscate passport (though common in practice — illegal)
""",
  },

  # ─────────────────────────────────────────────
  "Germany": {
    "Criminal Law": """
GERMANY CRIMINAL LAW — STRAFGESETZBUCH (STGB)
1. MURDER (§211 StGB): Premeditated murder — mandatory life imprisonment (Lebenslange Freiheitsstrafe)
2. MANSLAUGHTER (§212 StGB): 5 years to life imprisonment
3. RAPE/SEXUAL ASSAULT (§177 StGB): 2–15 years; aggravated (gang, weapon, severe harm) up to 15 years
4. ASSAULT (§223 StGB): Up to 5 years; GBH (§224) up to 10 years
5. ROBBERY (§249 StGB): 1–15 years; armed robbery up to 15 years
6. DRUG OFFENCES: BtMG — trafficking up to 15 years; possession small amounts often prosecuted lightly
7. RIGHTS: Presumption of innocence; right to interpreter; public defender (Pflichtverteidiger) for serious charges
8. REPORTING: 110 (police emergency); Opferschutz (victim support) available
""",
    "Employment Law": """
GERMANY EMPLOYMENT LAW
1. CIVIL CODE (BGB): Employment contracts; notice periods 2 weeks (probation) to 7 months (20+ years service)
2. PROTECTION AGAINST UNFAIR DISMISSAL ACT (KSchG): Applies after 6 months; socially unjustified dismissal unlawful
3. MINIMUM WAGE: €12.41/hr (2024)
4. WORKING TIME ACT (ARBZG): Max 8 hours/day (up to 10 with compensation); 30 hours/day max
5. WORKS COUNCIL (BETRIEBSRAT): Employee representation in firms with 5+ staff; co-determination rights
6. MATERNITY PROTECTION: 14 weeks maternity leave (MuSchG); up to 3 years parental leave (BEEG)
7. DISPUTE: Labour Courts (Arbeitsgericht); quick interim injunctions available
""",
  },

  # ─────────────────────────────────────────────
  "Turkey": {
    "Criminal Law": """
TURKEY CRIMINAL LAW — TÜRK CEZA KANUNU (TCK) 2004
1. MURDER (Article 81 TCK): Life imprisonment (aggravated); 25 years (simple)
2. RAPE (Article 102 TCK): 5–10 years; gang rape 16–20 years; child victim 16+ years up to life
3. ASSAULT (Article 86): 4 months to 2 years; aggravated up to 6 years
4. KIDNAPPING (Article 109): 3–8 years; for ransom 15–20 years
5. DRUG TRAFFICKING (Article 188): 20 years to life + judicial fine
6. TERRORISM: TMK No.3713 — membership 5–10 years; management 10–15 years (FETÖ/PKK related prosecutions widespread)
7. RIGHTS: Constitution Articles 36–38; European Convention on Human Rights applies
8. REPORTING: 155 (police); 182 (gendarmerie); 156 (gendarmerie emergency)
""",
    "Employment Law": """
TURKEY EMPLOYMENT LAW — LABOUR ACT NO.4857
1. CONTRACT: Indefinite or fixed term; max 2 years fixed (renewable once)
2. WORKING HOURS: 45 hours/week maximum; overtime 1.5x rate
3. ANNUAL LEAVE: 14 days (1–5 years); 20 days (5–15 years); 26 days (15+ years)
4. SEVERANCE: 30 days per year of service (employees working 1+ year dismissed without just cause)
5. MINIMUM WAGE: TRY 20,002.50/month (2024 H1)
6. TRADE UNIONS: Trade Unions and Collective Labour Agreement Act No.6356
7. DISPUTE: Labour Courts; TÜRK-İŞ and other unions provide legal aid
""",
  },

  # ─────────────────────────────────────────────
  "Bangladesh": {
    "Criminal Law": """
BANGLADESH CRIMINAL LAW — PENAL CODE 1860 (as applicable)
1. MURDER: Section 302 — death or life imprisonment
2. RAPE: Nari-O-Shishu Nirjatan Daman Ain 2000 (Women and Children Repression Prevention Act):
   - Section 9: Rape — minimum rigorous life imprisonment; gang rape or death of victim — death
   - Section 9(1): Rape of child — death
3. ACID ATTACKS: Acid Crime Prevention Act 2002 — death or life imprisonment
4. DOMESTIC VIOLENCE: Domestic Violence (Prevention and Protection) Act 2010
5. CYBERCRIME: Digital Security Act 2018 — up to 14 years for various offences
6. REPORTING: 999 (emergency); National Human Rights Commission; Bangladesh Legal Aid and Services Trust (BLAST)
""",
    "Employment Law": """
BANGLADESH LABOUR LAW — LABOUR ACT 2006 (AMENDED 2013/2018)
1. WORKING HOURS: 8 hours/day, 48 hours/week; overtime double rate
2. ANNUAL LEAVE: 11 days casual leave; 14 days sick leave; 10 days earned leave per year
3. MATERNITY BENEFIT: 16 weeks paid (Section 45–46)
4. MINIMUM WAGE: BDT 12,500/month (garment sector 2023)
5. TERMINATION: 120 days notice (permanent workers); 30 days compensation per year of service
6. DISPUTE: Labour Courts; Department of Labour
""",
  },

  # ─────────────────────────────────────────────
  "France": {
    "Criminal Law": """
FRANCE CRIMINAL LAW — CODE PÉNAL
1. MURDER (Article 221-1): 30 years imprisonment; premeditated (assassinat) — life
2. RAPE (Article 222-23): 15 years; aggravated (minor, torture) up to 20 years
3. ASSAULT (Articles 222-7 to 222-14): 3–15 years depending on severity
4. ROBBERY (Article 311-4 to 311-10): 10–20 years for armed robbery
5. DRUG TRAFFICKING (Article 222-36 to 222-41): Up to 10 years; organised trafficking up to 30 years
6. RIGHTS: Declaration of Human Rights 1789; ECHR applies
7. REPORTING: 17 (police emergency); 3919 (domestic violence helpline)
""",
    "Employment Law": """
FRANCE EMPLOYMENT LAW — CODE DU TRAVAIL
1. MINIMUM WAGE (SMIC): €11.65/hr (2024)
2. WORKING TIME: 35-hour legal week; overtime supplements 25–50%
3. DISMISSAL: For cause (faute) or economic reasons; procedural requirements strict; prud'hommes (labour tribunal)
4. PAID LEAVE: 5 weeks per year minimum
5. CDI vs CDD: Indefinite contract (CDI) vs fixed term (CDD max 18 months)
6. UNIONS: Strong union rights; sectoral collective agreements widespread
""",
  },
}


# ══════════════════════════════════════════════════
#  FBR TAX DATA
# ══════════════════════════════════════════════════
FBR_TAX_SLABS = [
    {"min": 0,        "max": 600000,       "rate": 0.00, "fixed": 0},
    {"min": 600001,   "max": 1200000,      "rate": 0.05, "fixed": 0},
    {"min": 1200001,  "max": 2400000,      "rate": 0.15, "fixed": 30000},
    {"min": 2400001,  "max": 3600000,      "rate": 0.25, "fixed": 210000},
    {"min": 3600001,  "max": 6000000,      "rate": 0.30, "fixed": 510000},
    {"min": 6000001,  "max": float("inf"), "rate": 0.35, "fixed": 1230000},
]
WITHHOLDING_RATES = {
    "cash_withdrawal":        {"filer": 0.006, "non_filer": 0.012, "description": "Cash withdrawal >PKR 50,000", "threshold": 50000},
    "property_purchase":      {"filer": 0.02,  "non_filer": 0.04,  "description": "Purchase of immovable property"},
    "vehicle_1000_1800cc":    {"filer": 0.01,  "non_filer": 0.03,  "description": "Vehicle purchase (1000cc–1800cc)"},
    "foreign_remittance":     {"filer": 0.00,  "non_filer": 0.01,  "description": "Foreign remittance received"},
    "dividend_income":        {"filer": 0.15,  "non_filer": 0.30,  "description": "Dividend income"},
    "prize_winnings":         {"filer": 0.15,  "non_filer": 0.30,  "description": "Prize / lottery winnings"},
    "capital_gains_property": {"filer": 0.035, "non_filer": 0.07,  "description": "Capital gains on immovable property"},
}

# ══════════════════════════════════════════════════
#  VECTOR DB SETUP (CHROMA DB)
# ══════════════════════════════════════════════════
CHROMA_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_data")
chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
try:
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    legal_collection = chroma_client.get_or_create_collection(
        name="legal_knowledge", 
        embedding_function=emb_fn
    )
except Exception as e:
    logger.warning(f"Could not load SentenceTransformer embedding, using default: {e}")
    legal_collection = chroma_client.get_or_create_collection(name="legal_knowledge")

def chunk_text(text: str, max_length: int = 500) -> List[str]:
    """Split text intelligently based on numbered points or blank lines."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_len = 0
    
    for p in paragraphs:
        if current_len + len(p) > max_length and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p]
            current_len = len(p)
        else:
            current_chunk.append(p)
            current_len += len(p)
            
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    return chunks

def seed_vector_db():
    if legal_collection.count() > 0:
        logger.info(f"Vector DB already seeded with {legal_collection.count()} constraints/blocks.")
        return
        
    logger.info("Initializing Vector DB and seeding data blocks...")
    docs, metadatas, ids = [], [], []
    
    for country, topics in LEGAL_KB.items():
        for topic, content in topics.items():
            chunks = chunk_text(content, max_length=500)
            for i, chunk in enumerate(chunks):
                chunk_str = chunk.strip()
                if chunk_str:
                    docs.append(chunk_str)
                    metadatas.append({"country": country, "topic": topic})
                    ids.append(f"{country.replace(' ', '_')}_{topic.replace(' ', '_')}_{i}")
                    
    if docs:
        try:
            # Batch add to avoid payload limits
            batch_size = 100
            for i in range(0, len(docs), batch_size):
                legal_collection.add(
                    documents=docs[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size]
                )
            logger.info(f"Successfully seeded Vector DB with {len(docs)} data blocks.")
        except Exception as e:
            logger.error(f"Error seeding Vector DB: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database correctly
    seed_vector_db()
    yield
    # Cleanup code can go here

@lru_cache(maxsize=128)
def get_rag_context(country: str, question: str, topic: str = None, n_results: int = 5) -> str:
    """
    Pure Vector DB RAG pipeline.
    Filters by specific country and optionally by topic.
    """
    try:
        # Build filter
        where_filter = {"country": country}
        if topic:
            # Multi-filter for ChromaDB
            where_filter = {
                "$and": [
                    {"country": country},
                    {"topic": topic}
                ]
            }
        
        results = legal_collection.query(
            query_texts=[question],
            n_results=n_results,
            where=where_filter
        )
        if results and results.get("documents") and results["documents"][0]:
            # Filter out very short/noisy chunks (headers, page numbers, etc.)
            valid_chunks = [
                chunk for chunk in results["documents"][0]
                if len(chunk.strip()) > 120
            ]
            if valid_chunks:
                return "\n\n---\n\n".join(valid_chunks)
    except Exception as e:
        logger.error(f"Vector DB query failed: {e}")
    return ""

def get_all_topics(country: str) -> list:
    return list(LEGAL_KB.get(country, {}).keys())

@lru_cache(maxsize=128)
def calculate_tax(annual_income: float) -> dict:
    tax, slab_info = 0.0, None
    for slab in FBR_TAX_SLABS:
        if slab["min"] <= annual_income <= slab["max"]:
            tax = slab["fixed"] + max(0, annual_income - slab["min"]) * slab["rate"]
            slab_info = slab
            break
    eff = (tax / annual_income * 100) if annual_income > 0 else 0
    if slab_info:
        mx = "∞" if slab_info["max"] == float("inf") else f"{slab_info['max']:,}"
        desc = f"PKR {slab_info['min']:,} – {mx}"
        mrate = slab_info["rate"] * 100
    else:
        desc, mrate = "N/A", 0
    return {
        "annual_income": annual_income,
        "tax_liability": round(tax, 2),
        "effective_rate": round(eff, 2),
        "marginal_rate": mrate,
        "slab_description": desc,
    }

# ══════════════════════════════════════════════════
#  FASTAPI APP
# ══════════════════════════════════════════════════
app = FastAPI(
    title="LexAI API", 
    version="4.0.0", 
    description="AI Legal Advisor Powered by VectorDB",
    lifespan=lifespan
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"], allow_credentials=True
)

@app.middleware("http")
async def security_and_logging_middleware(request: Request, call_next):
    start_time = time.time()
    client_ip = request.client.host if request.client else "0.0.0.0"
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000.0
    
    # Security headers (HSTS, X-Content-Type-Options, etc.)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    log_api_call(request.url.path, request.method, client_ip, status_code=response.status_code, duration_ms=duration_ms)
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# ── Pydantic Models ─────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class LegalQueryRequest(BaseModel):
    country: str
    region: str = ""
    topic: Optional[str] = None
    question: str
    history: List[ChatMessage] = []
    language: str = "English"
    model: str = "llama-3.3-70b-versatile"
    reasoning_mode: str = "Deep Legal Reasoning"

class DocGenRequest(BaseModel):
    doc_type: str
    country: str
    region: str
    party_data: dict = {}

class PersonalInfo(BaseModel):
    name: str = ""; cnic: str = ""; dob: str = ""; phone: str = ""
    email: str = ""; address: str = ""; citizen: str = "resident"
    father_name: str = ""; gender: str = ""; marital_status: str = ""
    city: str = ""; province: str = ""; employer_ntn: str = ""
    occupation: str = ""

class IncomeInfo(BaseModel):
    annual: float = 0; employer: str = ""; iban: str = ""; tds: float = 0
    bank_name: str = ""; employer_address: str = ""

class AssetsInfo(BaseModel):
    bank: float = 0; inv: float = 0; prop: float = 0; propAddr: str = ""
    veh: float = 0; vehDesc: str = ""; loan: float = 0; otherL: float = 0
    other_assets: float = 0

class TaxData(BaseModel):
    personal: PersonalInfo = PersonalInfo()
    income: IncomeInfo = IncomeInfo()
    assets: AssetsInfo = AssetsInfo()
    emp_type: str = "salaried"

class AIAdviceReq(BaseModel):
    emp_type: str
    annual_income: float

class SavingsReq(BaseModel):
    cash_withdrawal: float = 0; property_value: float = 0; vehicle_value: float = 0
    remittance: float = 0; dividend: float = 0; prize: float = 0; capital_gains: float = 0

class AffidavitRequest(BaseModel):
    personal: PersonalInfo = PersonalInfo()
    content: str = ""
    jurisdiction: str = "Pakistan, Punjab"
    purpose: str = ""

class WakalatnamaRequest(BaseModel):
    personal: PersonalInfo = PersonalInfo()
    attorney: dict = {}
    jurisdiction: str = "Pakistan, Punjab"
    scope: str = "General"
    purpose: str = "general legal matters"
    powers: List[str] = []

class TenancyRequest(BaseModel):
    landlord: dict = {}
    tenant: dict = {}
    property: dict = {}
    financial: dict = {}
    jurisdiction: str = "Pakistan, Punjab"

class EmploymentContractRequest(BaseModel):
    employee: dict = {}
    employer: dict = {}
    terms: dict = {}
    jurisdiction: str = "Pakistan"

# ── Groq helper ─────────────────────────────────
async def groq(messages: list, max_tokens: int = 1800, temperature: float = 0.2, model: str = None) -> str:
    target_model = model or GROQ_MODEL
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    payload = {
        "model": target_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    timeout = aiohttp.ClientTimeout(total=40)
    attempts = 3
    last_err = None
    
    for attempt in range(attempts):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as sess:
                async with sess.post(GROQ_URL, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        if resp.status == 429: # Rate limit
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise HTTPException(status_code=resp.status, detail=f"Groq error: {err[:400]}")
                    data = await resp.json()
                    if "error" in data:
                        raise HTTPException(status_code=400, detail=data["error"]["message"])
                    res_text = data["choices"][0]["message"]["content"]
                    return res_text
        except aiohttp.ClientError as e:
            last_err = e
            await asyncio.sleep(2 ** attempt)
            
    raise HTTPException(status_code=502, detail=f"Groq upstream failure after {attempts} attempts: {str(last_err)}")


def _require_pdf():
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation unavailable. Run: pip install reportlab  — then ensure pdf_generator.py is in the same directory as main.py."
        )

# ════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "version": "4.0.0",
        "model": GROQ_MODEL,
        "api_key_set": bool(GROQ_API_KEY),
        "pdf_available": PDF_AVAILABLE,
    }

@app.get("/api/jurisdictions")
async def jurisdictions():
    REGIONS = {
        "Pakistan":      ["Punjab","Sindh","Khyber Pakhtunkhwa","Balochistan","Islamabad (Federal)","Gilgit-Baltistan","AJK"],
        "United Kingdom":["England","Scotland","Wales","Northern Ireland"],
        "United States": ["Federal","California","New York","Texas","Florida","Illinois","Pennsylvania","Georgia"],
        "United Arab Emirates":["Dubai","Abu Dhabi","Sharjah","Ajman","Ras Al Khaimah"],
        "India":         ["Delhi","Maharashtra","Karnataka","Tamil Nadu","Gujarat","Rajasthan","West Bengal"],
        "Canada":        ["Ontario","British Columbia","Quebec","Alberta","Manitoba","Nova Scotia"],
        "Australia":     ["New South Wales","Victoria","Queensland","Western Australia","South Australia"],
        "Germany":       ["Bavaria","Berlin","Hamburg","North Rhine-Westphalia","Baden-Württemberg"],
        "France":        ["Île-de-France","Provence","Normandy","Brittany","Lyon"],
        "Saudi Arabia":  ["Riyadh","Jeddah","Mecca","Medina","Dammam"],
        "Turkey":        ["Istanbul","Ankara","Izmir","Antalya","Bursa"],
        "Bangladesh":    ["Dhaka","Chittagong","Khulna","Rajshahi","Sylhet"],
    }
    return {
        c: {
            "regions": REGIONS.get(c, []),
            "rag_topics": get_all_topics(c),
            "tax_module": (c == "Pakistan")
        }
        for c in REGIONS
    }

# ── Legal Chat ──────────────────────────────────
@app.post("/api/legal/chat")
@limiter.limit("5/minute")
async def legal_chat(request: Request, req: LegalQueryRequest):
    try:
        q_lower = req.question.lower().strip().rstrip("?!.")

        # 1. Broad conversational intent detection
        SMALL_TALK_PATTERNS = [
            "hi","hello","hey","howdy","greetings","sup","yo",
            "how are you","how r u","how are u","how's it going",
            "how is it going","good morning","good afternoon","good evening",
            "good night","what's up","whats up","nice to meet you",
            "who are you","what are you","tell me about yourself",
            "what can you do","what do you do","help me","thanks",
            "thank you","thx","ok","okay","cool","great","nice",
            "bye","goodbye","see you","take care","awesome",
        ]
        is_small_talk = any(p == q_lower for p in SMALL_TALK_PATTERNS) or (
            len(q_lower.split()) <= 4 and any(p in q_lower for p in SMALL_TALK_PATTERNS)
        )

        if is_small_talk:
            rag_ctx = ""
            system = (
                f"You are LexAI, a warm and professional AI legal and tax advisor. "
                f"The user is greeting you or making small talk. Respond in a friendly, "
                f"brief, conversational way. Introduce yourself naturally, mention you specialise in "
                f"legal and tax guidance for {req.country}, and invite them to ask their question. "
                f"Respond in {req.language}. Keep it under 60 words. Do NOT cite any statutes."
            )
            temp = 0.5
            user_payload = req.question
        else:
            try:
                db.record_analytics(category="legal_chat", action="query", country=req.country, topic=req.topic or "General", value=1.0)
            except Exception:
                pass

            n_results = (
                3 if req.model == "llama-3.1-8b-instant"
                else 4 if req.model == "meta-llama/llama-4-scout-17b-16e-instruct"
                else 7
            )
            rag_ctx = get_rag_context(req.country, req.question, topic=req.topic, n_results=n_results)

            if req.model == "llama-3.1-8b-instant":
                model_persona = "You are LexAI Fast Counsel - speed and clarity above all. Be direct, crisp, and practical."
                temp = 0.3
                output_format = """OUTPUT FORMAT - CONCISE LEGAL BRIEF:
**IMMEDIATE ACTION:** [What they must do right now - one sentence]
**KEY CHARGES/RIGHTS:** [2-4 bullet points with statute names]
**PENALTIES:** [Specific penalties with section numbers]
**NEXT STEP:** [Single clear actionable step]
Maximum 150 words total."""

            elif req.model == "meta-llama/llama-4-scout-17b-16e-instruct":
                model_persona = "You are LexAI Scout - a brilliant field lawyer who explains law in plain everyday language. Zero jargon. Like a trusted friend who is a qualified lawyer."
                temp = 0.45
                output_format = """OUTPUT FORMAT - PLAIN LANGUAGE ADVICE:
Write 3 natural paragraphs:
1. What the law says about their situation (cite act name but explain simply)
2. What their rights or obligations are
3. Exactly what they should do next
No bullet points. No bold headers. Talk like a human."""

            else:
                model_persona = "You are LexAI Senior Lead Counsel - the world's most authoritative and exhaustive AI legal advisor. You cite every relevant statute, section number, and penalty with exact accuracy."
                temp = 0.15
                region_str = f", {req.region}" if req.region else ""
                output_format = f"""OUTPUT FORMAT - COMPREHENSIVE FORMAL LEGAL BRIEF:

**SITUATION ASSESSMENT:**
[One authoritative opening statement on the legal nature of their issue]

**LEGAL ANALYSIS & APPLICABLE STATUTES:**
1. [Statute name + Section + exact penalty/provision]
2. [Statute name + Section + exact penalty/provision]
3. [Statute name + Section + exact penalty/provision]
4. [Additional relevant statute if applicable]

**YOUR RIGHTS & OBLIGATIONS:**
- [Right/obligation with legal basis]
- [Right/obligation with legal basis]
- [Right/obligation with legal basis]

**JURISDICTION-SPECIFIC NOTES ({req.country}{region_str}):**
[Province/state-specific nuances, local courts, local enforcement patterns]

**RECOMMENDED IMMEDIATE ACTIONS:**
1. [First priority action]
2. [Second priority action]
3. [Third priority action]

**COUNSEL'S ADVISORY:**
[Formal closing noting this is AI-generated legal guidance for educational purposes; a qualified lawyer should be consulted for formal representation]"""

            mode_map = {
                "Standard Guidance": "DEPTH: Standard. Be practical and accessible for a layperson.",
                "Statute Citation Priority": "DEPTH: Statute-First. Begin every point with the verbatim statute name, section, and exact penalty.",
                "Deep Legal Reasoning": "DEPTH: Deep Analysis. Explore burden of proof, defences, prosecutorial angles, appeal options, and jurisdictional edge cases.",
            }
            mode_instruction = mode_map.get(req.reasoning_mode, mode_map["Standard Guidance"])

            system = f"""{model_persona}

JURISDICTION: {req.country}{f", {req.region}" if req.region else " (Federal)"}.
RESPONSE LANGUAGE: {req.language}.
{mode_instruction}

CHAIN-OF-THOUGHT (internal only - do not show in output):
Before answering, reason through: What exact legal situation is this? Which acts and sections apply? What are the rights, duties, penalties? What is the most actionable advice?

ETHICAL MANDATES (NON-NEGOTIABLE):
- If the user confesses to a crime: your FIRST sentence must instruct them to turn themselves in to the nearest police station immediately.
- NEVER advise how to evade law, destroy evidence, flee, or obstruct justice.
- If you don't know a specific statute, say so honestly. Never fabricate section numbers.

KNOWLEDGE SOURCE: Use the LEGAL CONTEXT below as your primary reference. Cite specific sections and acts. Supplement with training only when needed.

{output_format}"""

            if rag_ctx:
                rag_block = f"LEGAL CONTEXT from {req.country} statutes:\n{'─'*60}\n{rag_ctx}\n{'─'*60}\n\n"
            else:
                rag_block = f"LEGAL CONTEXT: No statute retrieved. Answer from comprehensive legal training for {req.country}.\n\n"

            user_payload = (
                f"{rag_block}"
                f"{'TOPIC: ' + req.topic + chr(10) if req.topic else ''}"
                f"JURISDICTION: {req.country}{f', {req.region}' if req.region else ''}\n\n"
                f"USER QUESTION: {req.question}"
            )

        if req.history and not is_small_talk:
            messages = [{"role": "system", "content": system}]
            for h in req.history[-12:]:
                messages.append({"role": h.role, "content": h.content})
            messages.append({"role": "user", "content": req.question})
        else:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_payload},
            ]

        max_tok = 300 if is_small_talk else (500 if req.model == "llama-3.1-8b-instant" else 2000)
        response = await groq(messages, max_tokens=max_tok, temperature=temp, model=req.model)

        return {
            "response": response,
            "rag_used": bool(rag_ctx),
            "topic": req.topic,
            "jurisdiction": f"{req.country}, {req.region or 'Federal'}",
            "model_used": req.model,
            "language": req.language,
            "is_small_talk": is_small_talk,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat crash: {e}", exc_info=True)
        return JSONResponse(content={"detail": str(e)}, status_code=500)
# ── Legal Document Generation (AI text + PDF) ──
@app.post("/api/legal/document")
async def gen_legal_doc(req: DocGenRequest):
    rag_ctx = get_rag_context(req.country, req.doc_type)
    system = f"""You are LexAI, an expert legal document drafter for {req.country}, {req.region}.

Draft a complete, professional {req.doc_type}. Requirements:
- Include ALL standard clauses for this document type under {req.country} law
- Reference applicable statutes precisely
- Use [FIELD: description] format for blanks that need to be filled
- Include: recitals, operative clauses, schedule/annexures if needed, execution + signature block
- Add stamp duty / registration note where required by law
- For Pakistan documents: reference Punjab/Sindh/KP/Federal applicable law
{rag_ctx if rag_ctx else ""}

Format: Use **SECTION TITLE** for section headings. Use numbered clauses (1., 2., 3.).
Be comprehensive — a real lawyer should be able to use this as a solid first draft."""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Draft a complete {req.doc_type} for {req.country}, {req.region}."}
    ]
    content = await groq(messages, max_tokens=3000, temperature=0.1)

    # Generate PDF
    pdf_b64 = None
    if PDF_AVAILABLE:
        try:
            pdf_bytes = generate_legal_document_pdf(
                req.doc_type, content,
                f"{req.country}, {req.region}",
                req.party_data
            )
            pdf_b64 = base64.b64encode(pdf_bytes).decode()
        except Exception as e:
            logger.warning(f"Legal doc PDF generation failed: {e}")

    return {
        "content": content,
        "doc_type": req.doc_type,
        "jurisdiction": f"{req.country}, {req.region}",
        "pdf_base64": pdf_b64,
    }

# ── Affidavit (dedicated route) ─────────────────
@app.post("/api/legal/affidavit")
async def gen_affidavit(req: AffidavitRequest):
    _require_pdf()
    # Optionally generate AI content if not provided
    if not req.content:
        system = "You are a Pakistan legal document expert. Draft affidavit body paragraphs (facts only, numbered). Be concise and factual. No preamble or signature block — just the numbered factual statements."
        user = f"Draft affidavit body for: {req.purpose or 'general declaration'} in {req.jurisdiction}."
        req.content = await groq([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  max_tokens=600, temperature=0.1)

    pdf_bytes = await asyncio.to_thread(generate_affidavit_pdf, {
        "personal": req.personal.dict(),
        "content": req.content,
        "jurisdiction": req.jurisdiction,
    })
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=LexAI_Affidavit.pdf"}
    )

# ── Wakalatnaama (dedicated route) ──────────────
@app.post("/api/legal/wakalatnaama")
async def gen_wakalatnaama(req: WakalatnamaRequest):
    _require_pdf()
    pdf_bytes = await asyncio.to_thread(generate_wakalatnaama_pdf, {
        "personal": req.personal.dict(),
        "attorney": req.attorney,
        "jurisdiction": req.jurisdiction,
        "scope": req.scope,
        "purpose": req.purpose,
        "powers": req.powers if req.powers else [],
    })
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=LexAI_Wakalatnaama.pdf"}
    )

# ── Tenancy Agreement (dedicated route) ─────────
@app.post("/api/legal/tenancy-agreement")
async def gen_tenancy(req: TenancyRequest):
    _require_pdf()
    pdf_bytes = await asyncio.to_thread(generate_tenancy_pdf, req.dict())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=LexAI_Tenancy_Agreement.pdf"}
    )

# ── Employment Contract (dedicated route) ───────
@app.post("/api/legal/employment-contract")
async def gen_employment(req: EmploymentContractRequest):
    _require_pdf()
    pdf_bytes = await asyncio.to_thread(generate_employment_contract_pdf, req.dict())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=LexAI_Employment_Contract.pdf"}
    )

# ── AI Tax Advice ────────────────────────────────
@app.post("/api/tax/ai-advice")
async def ai_tax_advice(req: AIAdviceReq):
    tc = calculate_tax(req.annual_income)
    system = ("You are LexAI, a certified Pakistan tax advisor expert in FBR regulations "
              "and the Income Tax Ordinance 2001. Be specific, cite actual sections, give "
              "concrete PKR amounts. Be practical and actionable.")
    user = f"""I am a {req.emp_type} with annual income PKR {req.annual_income:,.0f}.
Computed tax: PKR {tc['tax_liability']:,.0f} ({tc['effective_rate']:.2f}% effective rate).

Give me 4–5 specific tax optimisation strategies for Pakistan Tax Year 2024–25:
- Section 60B: Pension fund contributions (up to 20% of income)
- Section 60C/60D: Voluntary Pension + Health Insurance (PKR 150,000 limit)
- Section 61: Charitable donations to approved NGOs (30% of taxable income)
- Section 62: Investment in listed company shares (PKR 2 million limit)
- Section 65D: Investment in new manufacturing plants
- Zakat deduction (Section 60), EOBI contributions
- Employer-specific strategies for {req.emp_type}

For each strategy: name the section, explain the deduction, give the PKR saving at my income level."""

    advice = await groq(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=900, temperature=0.2
    )
    return {"advice": advice, "tax_summary": tc}

# ── Tax Calculation ──────────────────────────────
@app.post("/api/tax/calculate")
async def tax_calc(data: dict):
    return calculate_tax(float(data.get("annual_income", 0)))

# ── Filer vs Non-Filer Savings ───────────────────
@app.post("/api/tax/savings-calculator")
async def savings_calc(req: SavingsReq):
    mapping = [
        ("cash_withdrawal",  req.cash_withdrawal, "cash_withdrawal"),
        ("property_purchase",req.property_value,  "property_purchase"),
        ("vehicle",          req.vehicle_value,   "vehicle_1000_1800cc"),
        ("remittance",       req.remittance,       "foreign_remittance"),
        ("dividend",         req.dividend,         "dividend_income"),
        ("prize",            req.prize,            "prize_winnings"),
        ("capital_gains",    req.capital_gains,    "capital_gains_property"),
    ]
    breakdown = {}
    total = 0
    for key, amount, rk in mapping:
        if amount > 0 and rk in WITHHOLDING_RATES:
            r = WITHHOLDING_RATES[rk]
            sav = amount * (r["non_filer"] - r["filer"])
            total += sav
            breakdown[key] = {
                "amount": amount,
                "filer_tax": amount * r["filer"],
                "non_filer_tax": amount * r["non_filer"],
                "saving": round(sav, 2),
                "description": r["description"]
            }
    return {"breakdown": breakdown, "total_saving": round(total, 2), "rates": WITHHOLDING_RATES}

# ── FBR Tax Slabs ────────────────────────────────
@app.get("/api/tax/slabs")
async def tax_slabs():
    return {"slabs": FBR_TAX_SLABS, "tax_year": "2024-25", "withholding": WITHHOLDING_RATES}

# ══════════════════════════════════════════════════
#  AUTHENTICATION
# ══════════════════════════════════════════════════
class BcryptHasher:
    def hash(self, password: str) -> str:
        # Bcrypt has a 72-byte limit; truncate to avoid ValueError
        pw_bytes = password.encode('utf-8')[:72]
        return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode('utf-8')
    def verify(self, password: str, hashed: str) -> bool:
        try:
            pw_bytes = password.encode('utf-8')[:72]
            return bcrypt.checkpw(pw_bytes, hashed.encode('utf-8'))
        except Exception:
            return False

pwd_context = BcryptHasher()
SECRET_KEY = os.getenv("JWT_SECRET", "")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET is not set. Add it to your .env file:\n"
        "  JWT_SECRET=some-long-random-string-at-least-32-chars"
    )
ALGORITHM = "HS256"
# Auth uses SQLite via database.py

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

security_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        user = db.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        log_security_event("admin_access_fail", "Unauthorized access attempt to admin endpoint", "unknown", user.get("email", "unknown"))
        raise HTTPException(status_code=403, detail="Privilege required: Admin access only")
    return user

@app.post("/api/auth/signup")
@app.post("/api/v1/auth/signup")
async def auth_signup(request: Request, req: SignupRequest):
    client_ip = request.client.host if request.client else "0.0.0.0"
    try:
        valid = validate_email(req.email)
        email = valid.normalized
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    hashed_password = pwd_context.hash(req.password)
    role = "admin" if email.lower() == "admin@lexai.app" else "user"
    
    # Save to SQLite
    db_success = db.create_user(email, req.first_name, req.last_name, hashed_password, role)
    
    if not db_success:
        raise HTTPException(status_code=400, detail="Email already registered")
    db.record_audit_log(email, "signup", f"New user signup: {role}", client_ip)

    exp = datetime.utcnow() + timedelta(days=7)
    token = jwt.encode({"sub": email, "name": f"{req.first_name} {req.last_name}", "role": role, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "user": {"email": email, "name": f"{req.first_name} {req.last_name}", "role": role}}

@app.post("/api/auth/login")
@app.post("/api/v1/auth/login")
async def auth_login(request: Request, req: LoginRequest):
    client_ip = request.client.host if request.client else "0.0.0.0"
    email = req.email.lower()
    
    # Check SQLite
    db_user = db.get_user_by_email(email)
    
    pw_hash = db_user["password_hash"] if db_user else None
    role = db_user["role"] if db_user else "user"
    first_name = db_user["first_name"] if db_user else ""
    last_name = db_user["last_name"] if db_user else ""
    
    if not pw_hash:
        log_security_event("login_fail", f"user not found ({email})", client_ip, "unknown")
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    try:
        if not pwd_context.verify(req.password, pw_hash):
            log_security_event("login_fail", f"bad password ({email})", client_ip, "unknown")
            raise HTTPException(status_code=401, detail="Invalid email or password")
            
        db.record_audit_log(email, "login", "Successful login", client_ip)
        exp = datetime.utcnow() + timedelta(days=7)
        token = jwt.encode({"sub": email, "name": f"{first_name} {last_name}", "role": role, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer", "user": {"email": email, "name": f"{first_name} {last_name}", "role": role}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login crash: {e}", exc_info=True)
        return JSONResponse(content={"detail": str(e)}, status_code=500)


# ══════════════════════════════════════════════════
#  TAX PDF ENDPOINTS
# ══════════════════════════════════════════════════

@app.post("/api/tax/generate-ntn-pdf")
async def ntn_pdf(data: TaxData):
    _require_pdf()
    try:
        pdf = await asyncio.to_thread(generate_ntn_pdf, data.dict())
        return Response(
            content=pdf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=LexAI_NTN_Application.pdf"}
        )
    except Exception as e:
        logger.error(f"NTN PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tax/generate-itr-pdf")
async def itr_pdf(data: TaxData):
    _require_pdf()
    try:
        pdf = await asyncio.to_thread(generate_itr_pdf, data.dict())
        return Response(
            content=pdf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=LexAI_Income_Tax_Return.pdf"}
        )
    except Exception as e:
        logger.error(f"ITR PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tax/generate-wealth-pdf")
async def wealth_pdf(data: TaxData):
    _require_pdf()
    try:
        pdf = await asyncio.to_thread(generate_wealth_pdf, data.dict())
        return Response(
            content=pdf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=LexAI_Wealth_Statement.pdf"}
        )
    except Exception as e:
        logger.error(f"Wealth PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tax/generate-affidavit-pdf")
async def affidavit_pdf_tax(data: TaxData):
    """Generate a generic tax-purpose affidavit."""
    _require_pdf()
    try:
        payload = {
            "personal": data.personal.dict(),
            "content": (f"That I am a {'salaried employee' if data.emp_type=='salaried' else 'business owner'} "
                       f"with annual income of PKR {data.income.annual:,.0f}.\n"
                       f"That the information provided in my tax documents is true and correct.\n"
                       f"That I am submitting this affidavit in support of my NTN application / tax return."),
            "jurisdiction": "Pakistan",
        }
        pdf = await asyncio.to_thread(generate_affidavit_pdf, payload)
        return Response(
            content=pdf, media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=LexAI_Tax_Affidavit.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════
#  DOCUMENT MANAGEMENT (API v1)
# ══════════════════════════════════════════════════

@app.post("/api/v1/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = Form("legal"),
    user: dict = Depends(get_current_user)
):
    client_ip = request.client.host if request.client else "0.0.0.0"
    doc_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    safe_filename = f"{doc_id}{ext}"
    target_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        content = await file.read()
        with open(target_path, "wb") as f:
            f.write(content)
        db.save_document_metadata(doc_id, user["email"], file.filename, doc_type, target_path)
        db.record_audit_log(user["email"], "upload_document", f"Uploaded document: {file.filename} ({doc_type})", client_ip)
        db.create_notification(user["email"], "Document Uploaded", f"Your file '{file.filename}' has been securely uploaded.")
        return {"status": "success", "doc_id": doc_id, "filename": file.filename}
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save document: {e}")

@app.get("/api/v1/documents/list")
async def list_documents(user: dict = Depends(get_current_user)):
    docs = db.get_user_documents(user["email"])
    return {"documents": docs}

@app.get("/api/v1/documents/download/{doc_id}")
async def download_document(request: Request, doc_id: str, user: dict = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "0.0.0.0"
    doc = db.get_document_by_id(doc_id)
    if not doc or doc["user_email"] != user["email"].lower():
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    if not os.path.exists(doc["file_path"]):
        raise HTTPException(status_code=404, detail="File missing on disk")
    db.record_audit_log(user["email"], "download_document", f"Downloaded doc {doc['doc_name']}", client_ip)
    return FileResponse(doc["file_path"], filename=doc["doc_name"])

@app.delete("/api/v1/documents/delete/{doc_id}")
async def delete_document(request: Request, doc_id: str, user: dict = Depends(get_current_user)):
    client_ip = request.client.host if request.client else "0.0.0.0"
    doc = db.get_document_by_id(doc_id)
    if not doc or doc["user_email"] != user["email"].lower():
        raise HTTPException(status_code=404, detail="Document not found or access denied")
    
    success = db.delete_document_by_id(doc_id, user["email"])
    if success and os.path.exists(doc["file_path"]):
        try:
            os.remove(doc["file_path"])
        except OSError as e:
            logger.warning(f"Could not remove file from disk: {e}")
    db.record_audit_log(user["email"], "delete_document", f"Deleted doc {doc['doc_name']}", client_ip)
    return {"status": "success", "message": "Document deleted successfully"}

# ══════════════════════════════════════════════════
#  ADMIN DASHBOARD (API v1)
# ══════════════════════════════════════════════════

@app.get("/api/v1/admin/analytics")
async def get_admin_analytics(admin: dict = Depends(get_current_admin)):
    summary = db.get_analytics_summary()
    return summary

@app.get("/api/v1/admin/logs")
async def get_admin_logs(limit: int = 50, admin: dict = Depends(get_current_admin)):
    logs = db.get_recent_audit_logs(limit)
    return {"logs": logs}

@app.get("/api/v1/admin/users")
async def get_admin_users(admin: dict = Depends(get_current_admin)):
    users = db.list_all_users()
    return {"users": users}

# ══════════════════════════════════════════════════
#  NOTIFICATIONS (API v1)
# ══════════════════════════════════════════════════

@app.get("/api/v1/notifications")
async def get_notifications(user: dict = Depends(get_current_user)):
    n = db.get_user_notifications(user["email"])
    return {"notifications": n}

@app.post("/api/v1/notifications/read")
async def mark_read(user: dict = Depends(get_current_user)):
    db.mark_notifications_read(user["email"])
    return {"status": "success"}

# ══════════════════════════════════════════════════
#  STATIC FILE SERVING
# ══════════════════════════════════════════════════
@app.get("/")
async def serve_index():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [
        os.path.join(here, "index.html"),
        os.path.join(here, "frontend", "index.html"),
        os.path.join(here, "static", "index.html"),
    ]:
        if os.path.exists(p):
            return FileResponse(p)
    return HTMLResponse(
        "<h1>LexAI API v4 ✓</h1>"
        "<p><a href='/docs'>API Docs (Swagger)</a> | "
        "<a href='/redoc'>ReDoc</a></p>"
        "<p>Place <code>index.html</code> next to <code>main.py</code></p>"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)