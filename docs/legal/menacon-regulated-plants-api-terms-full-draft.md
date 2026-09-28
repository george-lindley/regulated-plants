---
title: Menacon Regulated Plants API Terms - Full Draft
date: June 9, 2026
---

# API Terms

 Draft terms for Enterprise access to the Regulated Plants API provided commercially by Menacon.

**Draft pending legal review.**

 These terms are a working draft for counsel review before paid API access or production keys are issued. They are not legal advice and may need to be adapted to governing law, insurance, payment terms, and customer-specific agreements.

Last updated: June 9, 2026

## 1. Parties And Scope

 These API Terms govern access to and use of the Regulated Plants API, related documentation, API keys, response data, source metadata, and other materials made available for Enterprise integrations (collectively, the "API").

 The API is provided by Menacon Ltd, a company registered in England and Wales under company number 17252141, with its registered office at 17 Rees Road, Larkhill, Salisbury, England, SP4 8FT ("Menacon", "we", "us", or "our"). Menacon provides commercial API access for the Regulated Plants Database project.

 "Customer", "you", or "your" means the organization or person that requests, receives, pays for, or uses API access. If you use the API on behalf of an organization, you represent that you are authorized to bind that organization to these API Terms.

 References to the Regulated Plants Database, project participants, institutions, contributors, funders, public authorities, regulators, or data sources do not make those parties a party to these API Terms and do not imply endorsement, approval, warranty, or responsibility for Customer's products, listings, shipments, or compliance decisions.

 A separate written agreement signed by Menacon and Customer will control if it conflicts with these API Terms.

## 2. Access Confirmation

 "Access Confirmation" means an email, quote, invoice, order form, Stripe checkout record, payment link, subscription record, or other written confirmation from Menacon that identifies the Customer, approved use case, access period, fees, payment terms, quotas, rate limits, support contact, and any special terms.

## 3. Acceptance And API Keys

 By requesting access, accepting an API key, using the API, or confirming acceptance in writing, you agree to these API Terms. You may not use the API unless you accept these API Terms or another written agreement with Menacon.

 API keys are confidential credentials. You are responsible for keeping them secure, limiting access to authorized personnel and systems, and promptly notifying Menacon if a key is lost, exposed, or misused. You may not share API keys with third parties, embed them in public client-side code, or use them for any application, organization, or customer not approved in the applicable Access Confirmation. Menacon may rotate, suspend, or revoke keys to protect the API, the data, or other users.

## 4. Permitted Use

 Subject to these API Terms and the applicable Access Confirmation, Menacon grants Customer a limited, non-exclusive, non-transferable right during the applicable access period to use the API for internal and customer-facing operational workflows directly related to catalog review, checkout controls, fulfillment review, restricted-shipping logic, compliance review, seller support, customer-support records, or order handling.

 You may use individual API responses to support permitted workflows, including catalog review, checkout controls, fulfillment review, restricted-shipping logic, seller support, customer-support records, and compliance audit records. You may not use API responses to reconstruct, extract, mirror, bulk replicate, or create a substitute for the Regulated Plants Database or a competing plant regulatory data product.

 You may cache and retain individual API responses as reasonably necessary for permitted workflows, troubleshooting, billing verification, legal or compliance audit records, and customer-support records, provided you do not use cached responses to create a standalone database or avoid refreshing regulatory results for active decisions.

 Unless Menacon agrees in writing, you may not resell, sublicense, publish, redistribute, mirror, scrape, bulk-download, overload, reverse engineer, or attempt unauthorized access to the API or related systems.

## 5. Public Dataset License; Enterprise API License

 Public website content, public downloads, sample data, documentation, or other materials may be made available under separate public licenses, including noncommercial licenses. Enterprise API access and API responses are licensed commercially by Menacon only under these API Terms, any applicable Access Confirmation, and any separate written agreement. Permission to use the API for commercial operational workflows does not grant broader rights to public downloads, third-party source materials, institutional marks, or materials outside the API.

## 6. Nature Of The Data And Source Evidence

 The API reports records found in the Regulated Plants Database, which is compiled from government, agricultural, biosecurity, and other source materials. Plant taxonomy, common names, scientific names, jurisdiction boundaries, legal classifications, and regulatory source materials can change over time and may be ambiguous, incomplete, delayed, or inconsistent across authorities.

 API responses may include source URLs, authority names, raw classifications, notes, jurisdiction identifiers, release metadata, and match suggestions. The API is intentionally conservative: it reports whether a matched plant has a regulation record in the requested jurisdiction according to the current dataset. It does not state that a plant is legally allowed, banned, prohibited to sell, or safe to ship.

 Source URLs, authority names, classifications, notes, and other source metadata are provided for reference and traceability only. Source evidence may be incomplete, outdated, unavailable, moved, or changed by the source authority. Inclusion of a source, authority, institution, jurisdiction, or URL does not imply endorsement, approval, or verification of Customer's products, listings, shipments, or compliance decisions.

 The API may produce false positives, false negatives, outdated results, ambiguous matches, or incomplete source coverage.

## 7. No Legal Advice Or Compliance Guarantee

 The API is an informational reference tool only. It is not legal advice, a legal opinion, a regulatory determination, or a substitute for review by qualified counsel or the relevant regulatory authority.

 Customer is responsible for deciding how to interpret API responses in its own workflow, including whether to allow, block, delay, delist, restrict, escalate, or manually review any product, listing, order, or shipment.

 You remain solely responsible for your products, listings, sales, shipping, customer communications, compliance workflow, legal review, and final decisions. You should independently verify regulatory requirements before selling, shipping, restricting, delisting, or otherwise acting on plant products.

## 8. Customer Responsibilities

You agree to:

- Use the API only for lawful purposes and in compliance with all applicable laws and regulations.
- Not submit unnecessary personal data to the API.
- Design your integration to handle errors, unavailable responses, ambiguous plant matches, stale data, and "review needed" outcomes.
- Maintain appropriate human review, escalation, and override procedures for regulated or uncertain products.
- Not use API results as the sole basis for high-risk legal, regulatory, enforcement, or customer-facing decisions without appropriate review.
- Not imply that Menacon, Regulated Plants, the University of California, UC Davis, the United Nations University, UNU-INWEH, contributors, funders, regulators, or data sources have approved your products, listings, shipments, or compliance decisions.
- Not interfere with, overload, reverse engineer, or attempt unauthorized access to the API or related systems.

## 9. Request Data; No Unnecessary Personal Data

 The API is designed to receive plant queries and destination jurisdiction fields, such as country and region/state/province. Customer must not submit customer names, street addresses, email addresses, phone numbers, payment information, or other unnecessary personal data to the API unless Menacon expressly agrees in writing.

 Menacon may log API keys, account identifiers, IP addresses, timestamps, request metadata, plant queries, destination jurisdictions, responses, errors, and usage metrics for security, abuse prevention, debugging, billing, support, audit, and data-quality purposes. Menacon's Privacy Policy governs its handling of personal information.

## 10. Availability, Changes, And Rate Limits

 Menacon may update the API, documentation, data schema, endpoints, rate limits, response format, matching logic, data releases, or source coverage from time to time. Menacon may add, remove, correct, or modify records as new information becomes available. Menacon may also suspend the API for maintenance, security, abuse prevention, legal, data-integrity, or operational reasons.

 For production Enterprise integrations, Menacon will use reasonable efforts to provide advance notice of material breaking changes where practical. Menacon may make immediate changes without notice for security, legal, data-integrity, abuse-prevention, or urgent operational reasons.

 Except as expressly stated in an Access Confirmation or signed agreement, Menacon does not guarantee uninterrupted, error-free, or backwards-compatible access.

## 11. Fees And Pilot Access

 API access may be provided as a no-fee pilot, evaluation, manually approved access, paid subscription, usage-based plan, invoice-based plan, Stripe payment link, bank-transfer arrangement, or other commercial arrangement stated in an Access Confirmation or separate written agreement.

 No fees are owed unless an Access Confirmation, invoice, quote, order form, subscription workflow, or signed agreement states the applicable fees. Unless otherwise stated, fees, quotas, billing period, payment due date, taxes, renewal, expiration, and support commitments are as set out in the applicable Access Confirmation.

 Customer will pay the fees stated in the applicable Access Confirmation. Fees are exclusive of VAT, sales tax, use tax, withholding tax, and similar taxes unless the Access Confirmation states otherwise. Customer is responsible for applicable taxes other than taxes based on Menacon's net income. Menacon may issue invoices, payment links, Stripe checkout links, or other payment instructions.

 If Customer fails to pay undisputed amounts when due, Menacon may suspend API access after reasonable notice, except where immediate suspension is necessary for security, abuse prevention, or operational protection.

## 12. Ownership And Feedback

 Menacon and its licensors retain all rights they have in the API, documentation, database structure, compiled dataset, software, matching logic, source metadata compilation, and related technology. These API Terms do not transfer ownership of the API or underlying data, and they do not grant rights in third-party source materials except to the extent Menacon is authorized to grant those rights.

 If you provide corrections, feedback, suggestions, or data-quality reports, you grant Menacon permission to use them to improve the database, API, and documentation without restriction or compensation.

## 13. Confidentiality

 Non-public API keys, credentials, usage records, pricing, technical information, security information, and other materials marked or reasonably understood as confidential must be protected using reasonable care and used only for the purpose of the Enterprise API relationship. These confidentiality obligations survive termination for as long as the information remains non-public and confidential.

## 14. Disclaimer Of Warranties

 TO THE MAXIMUM EXTENT PERMITTED BY LAW, THE API, DOCUMENTATION, DATA, RESPONSES, SOURCE METADATA, AND RELATED SERVICES ARE PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS, IMPLIED, STATUTORY, OR OTHERWISE, INCLUDING ANY IMPLIED WARRANTIES OF ACCURACY, COMPLETENESS, CURRENTNESS, MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT, AVAILABILITY, OR ERROR-FREE OPERATION.

 MENACON DOES NOT WARRANT THAT THE API WILL IDENTIFY EVERY REGULATED PLANT, JURISDICTION, LAW, RULE, ORDER, CLASSIFICATION, OR SOURCE MATERIAL, OR THAT ANY API RESULT WILL PREVENT FINES, PENALTIES, ENFORCEMENT ACTIONS, PRODUCT DELAYS, LOST SALES, OR OTHER LOSSES.

## 15. Limitation Of Liability

 TO THE MAXIMUM EXTENT PERMITTED BY LAW, MENACON, THE REGULATED PLANTS DATABASE PROJECT, PROJECT PARTICIPANTS, AFFILIATED INSTITUTIONS, CONTRIBUTORS, FUNDERS, OFFICERS, EMPLOYEES, CONTRACTORS, AND AGENTS WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, PUNITIVE, OR ENHANCED DAMAGES, OR FOR LOST PROFITS, LOST REVENUE, LOST DATA, LOST GOODWILL, BUSINESS INTERRUPTION, SUBSTITUTE SERVICES, FINES, PENALTIES, REGULATORY ENFORCEMENT, OR CUSTOMER CLAIMS ARISING FROM OR RELATED TO THE API, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

 TO THE MAXIMUM EXTENT PERMITTED BY LAW, OUR TOTAL AGGREGATE LIABILITY ARISING FROM OR RELATED TO THE API WILL NOT EXCEED THE AMOUNTS YOU PAID TO MENACON FOR API ACCESS DURING THE SIX MONTHS BEFORE THE EVENT GIVING RISE TO THE CLAIM, OR USD $100 IF YOU RECEIVED PILOT, TRIAL, OR FREE ACCESS.

 CUSTOMER ACKNOWLEDGES THAT MENACON, AND NOT ANY UNIVERSITY, PUBLIC AUTHORITY, REGULATOR, FUNDER, CONTRIBUTOR, OR SOURCE AUTHORITY, IS THE COMMERCIAL PROVIDER OF API ACCESS UNDER THESE API TERMS.

## 16. Indemnification

 You will defend, indemnify, and hold harmless Menacon, the Regulated Plants Database project, project participants, affiliated institutions, contributors, funders, officers, employees, contractors, and agents from and against claims, losses, liabilities, damages, fines, penalties, costs, and expenses, including reasonable attorneys' fees, arising from or related to your products, listings, sales, shipments, customer communications, compliance decisions, API integration, breach of these API Terms, violation of law, or misuse of the API.

 Menacon will provide prompt notice of the claim, allow Customer reasonable control of the defense, and cooperate at Customer's expense, except that Customer may not settle any claim in a way that imposes obligations on Menacon or any protected party, admits fault, or limits rights without Menacon's prior written consent.

## 17. Suspension And Termination

 Menacon may suspend or terminate API access if you breach these API Terms, fail to pay applicable fees, create security or operational risk, exceed permitted usage, misuse the data, or use the API in a way that may harm Menacon, the project, data sources, regulators, customers, or other users.

 Upon termination, Customer must stop making API calls and stop using API responses for new operational decisions. Customer may retain copies of prior responses only as reasonably necessary for legal, compliance, accounting, security, or audit records, subject to these API Terms and confidentiality obligations.

## 18. Publicity And Attribution

 Customer may not use the names, logos, marks, institutional affiliations, or source names of Menacon, Regulated Plants, the University of California, UC Davis, the United Nations University, UNU-INWEH, contributors, funders, regulators, or data sources in marketing, product claims, customer notices, press releases, public announcements, or endorsement statements without prior written permission from the applicable rights holder.

## 19. Governing Law And Disputes

 These API Terms and any dispute or claim arising from or related to them, the API, or API access are governed by the laws of England and Wales. The courts of England and Wales will have exclusive jurisdiction, except that Menacon may seek injunctive or equitable relief in any court of competent jurisdiction to protect its confidential information, intellectual property, API, systems, or data.

## 20. Changes To These Terms

 Menacon may update these API Terms from time to time. Material changes will be posted on this page or communicated to Enterprise contacts using reasonable means. Continued API use after the effective date of updated terms constitutes acceptance of those updates, unless a separate written agreement says otherwise. Changes will not override a signed agreement during its stated term unless the signed agreement permits that change.

## 21. Contact

 Questions about Enterprise API access or these API Terms can be sent through the contact form. Commercial API access is provided by Menacon Ltd.

 Commercial API access provided by Menacon Ltd, company number 17252141, registered in England and Wales, registered office 17 Rees Road, Larkhill, Salisbury, England, SP4 8FT.
