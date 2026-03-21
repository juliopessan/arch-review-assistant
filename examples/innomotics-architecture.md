# Innomotics Architecture

## Overview
Innomotics is an industrial B2B commerce platform built on SAP Commerce Cloud V2,
integrating product configuration (CPQ), document orchestration (SAP FIORS), and
ERP backend (SAP S/4HANA). The platform serves both B2C Tenant and B2B Tenant users
via SSO on Entra (Microsoft Azure AD).

---

## Layers

### Frontend Layer
- **Headless Spartacus Frontend** — Angular-based storefront consuming SAP Commerce OCC Layer APIs
- **SAP Configurator for Commerce (CPQ UI)** — Product configuration UI with three modes:
  Configuration, Documents, and 3D Model
- **Backoffice** — CMS and catalog management tool (SAP Commerce)
- **SmartEdit** — Content editing tool (SAP Commerce)

### Content & Asset Management
- **DAM — Cloudinary** — Digital Asset Management for product images and media
- **TMS — Translation Service** — Translation Management System for multilingual content
- **Innomotics Access** — SSO gateway connecting B2C and B2B tenants via Microsoft Entra

---

## SAP Commerce Cloud V2 (Core Platform)

### OCC API Layer
- **SAP Commerce OCC Layer** — RESTful API gateway exposing all commerce operations to the Spartacus frontend

### Commerce Core Services
- **My Offers** — Customer-specific pricing and offer management
- **My Products** — Customer product catalog with personalization
- **My Account Products** — Account-level product visibility
- **My Spare Parts** — Spare parts catalog and ordering
- **Catalog** — Master product catalog management
- **Supplier Orders** — Supplier order management
- **Quote History** — Customer quote history and management
- **Quotes** — Active quote creation and management
- **Cart** — Shopping cart service
- **Checkout** — Checkout and order submission flow
- **Order History** — Historical order lookup
- **Projects / Product List** — Project-based product grouping

### API Layers
- **Order APIs** — Order management REST endpoints
- **CPQ APIs** — Configuration and pricing quote APIs

### Microservices
- **DOC Service API** — Document generation service API
- **Configuration Settings & Cache** — Settings and caching layer for configuration
- **Integration Extension** — Extension points for third-party integrations
- **Pricing Service** — Dynamic pricing engine
- **Mailing Service** — Transactional email delivery
- **Contact Info Service** — Customer contact data service
- **CES Product Config Service** — Customer Experience Service for product configuration

### External Integrations
- **AGT — Quotation System** — Legacy AGT quotation system with AGT Offers APIs
- **SIRIUS — MS Dynamics CRM** — Microsoft Dynamics CRM integration via:
  - Service Tickets
  - Base (customer base management)
  - External Config Call
- **3rd Party Configurations (Faresoft)** — External CPQ/configuration provider

---

## SAP BTP (Business Technology Platform)

### SAP CPI Integration Suite
Integration middleware exposing the following functions to the commerce layer:
- **Space Part Finder** — Spare parts lookup
- **Supplier Orders** — Supplier order routing
- **Quote History** — Quote data synchronization
- **Offer Services (small / medium / large)** — Tiered offer management
- **Order Services (small / medium / large)** — Tiered order management
- **Order History** — Historical order data relay

### Data Transport
- **oData / RFC / BAPI Calls** — SAP-native integration protocols connecting CPI to ERP systems

### AI Components
- **Configuration Experience Service (SAP FIORS) — AI Agent (Beta)** — AI agent for configuration
  assistance; storage for KB communications (subprocess, knowledge base, billing)
  - Connected to: SAP HANA Data Base

---

## SAP Configuration & Pricing Service (configurator4)
- **SAP Configuration and Pricing Service** — Core CPQ engine
- **SAP HANA Data Base** — In-memory database for configuration data
- **SAP Data Replication Service** — Replication service syncing configuration data

---

## Document Orchestration Service (SAP FIORS)

### Components
- **Artifacts Registry** — Registry of document templates and artifacts
- **Management UI** — UI for document template and artifact management
- **Document Service (Reports DB)** — Document generation and storage backend
- **Document Template Management** — Template CRUD and versioning
- **Template Storage** — Persistent storage for document templates (database)

---

## 3rd Party Tools (External)

### CalcClick
- **3D Models** — 3D product visualization
- **Technical Documents** — Technical documentation delivery
- **Product Dimensions** — Product dimensional data

### Other Integrations
- **CAD4Sales** — CAD-based product sales configurator
- **DEEP / MLFW** — Machine learning framework integration
- **Dalsi** — (Additional integration system)
- **SES (Startup Calculation)** — Startup cost calculation service

---

## SAP S/4HANA Backend

### On-Premise
- **SAP R/3 On Premise**
  - SAP Cloud Connector
  - SAP ERP Legacy Systems

### SAP S/4HANA Enterprise Cloud (Primary)
- **SAP S/4HANA Enterprise Cloud**
  - SAP Cloud Connector
  - SAP OneERP EAF (400)
- **SAP Smart Data Integration** — Data integration layer
- **SAP S/4HANA EAP (800)** — Primary ERP instance

---

## Integration Flows

### Frontend → Commerce Core
- Spartacus Frontend → SAP Commerce OCC Layer → Commerce Core Services

### Commerce Core → External CPQ
- CPQ APIs → SAP Configuration and Pricing Service (configurator4)
- SAP Configurator for Commerce (CPQ UI) → CPQ APIs

### Commerce Core → BTP Integration
- Order/Quote services → SAP CPI Integration Suite → oData/RFC/BAPI → SAP S/4HANA

### Commerce Core → Document Generation
- DOC Service API → Document Orchestration Service (SAP FIORS) → Template Storage

### Commerce Core → 3rd Party Tools
- Integration Extension → CalcClick (3D Models, Technical Docs, Product Dimensions)
- Integration Extension → CAD4Sales, DEEP/MLFW, Dalsi, SES

### CRM Integration
- SIRIUS (MS Dynamics CRM) → Service Tickets, External Config Call → SAP Commerce Core

### Content Management
- Cloudinary (DAM) → Backoffice / SmartEdit → SAP Commerce Core
- Translation Service (TMS) → Backoffice / SmartEdit → SAP Commerce Core

### AI Configuration Assistance
- Configuration Experience Service AI Agent → SAP HANA Data Base
- Configuration Experience Service AI Agent → SAP Configuration and Pricing Service

---

## Infrastructure & Cloud

- **Primary cloud**: SAP Business Technology Platform (BTP)
- **ERP cloud**: SAP S/4HANA Enterprise Cloud
- **Identity**: Microsoft Entra (Azure AD) — SSO for B2C and B2B tenants
- **Database**: SAP HANA (in-memory, for configuration and AI agent data)
- **On-premise**: SAP R/3 legacy systems connected via SAP Cloud Connector
- **CDN/DAM**: Cloudinary (external SaaS)
- **Translation**: External TMS SaaS service

---

## Business Context
Innomotics is the Siemens motors and large drives division (spun off 2022).
The platform supports B2B industrial product sales, configuration of complex motor and
drive systems (CPQ), spare parts procurement, quoting workflows, and document
generation for technical and commercial proposals. Users include industrial customers,
distributors, and internal sales engineers across multiple regions and languages.
