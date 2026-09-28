# Regulated Plants Privacy Data Register

This register summarizes personal data handled by the Regulated Plants web app
and related Enterprise API administration. It should be reviewed with the UNU
PDP Policy and Legal Office before the public beta is treated as production.

## Researcher Website Access

| Data | Purpose | Access | Storage | Retention |
| --- | --- | --- | --- | --- |
| Name | Identify requester during access review | Project admins | Account database | While request/account administration is needed |
| Email address | Account identity, review communication, passwordless login | Project admins | Account database | While request/account administration is needed |
| Organization | Eligibility and access review | Project admins | Account database | While request/account administration is needed |
| Access purpose | Eligibility and access review | Project admins | Account database | While request/account administration is needed |
| Account status and role | Access control and admin management | Project admins | Account database | While request/account administration is needed |
| Review note and reviewer | Admin audit trail | Project admins | Account database | While audit trail is needed |
| Last login timestamp | Access administration and support | Project admins | Account database | While account administration is needed |
| One-time login token hash | Passwordless login verification | System only | Account database | Token expires after 30 minutes; hashes may remain until cleanup |

Notes:
- Researcher login is passwordless. No account passwords are collected or stored.
- One-time login links are sent by email, expire, and can be used once.
- Raw login tokens are not stored.

## Contact Form

| Data | Purpose | Access | Storage | Retention |
| --- | --- | --- | --- | --- |
| Name | Respond to enquiry | Project contact recipients | Email delivery and mailbox | While needed for response, support, or audit |
| Email address | Reply to enquiry | Project contact recipients | Email delivery and mailbox | While needed for response, support, or audit |
| Subject | Route enquiry | Project contact recipients | Email delivery and mailbox | While needed for response, support, or audit |
| Message | Respond to enquiry or process correction/request | Project contact recipients | Email delivery and mailbox | While needed for response, support, or audit |
| Data release name | Identify the database version for corrections | Project contact recipients | Email delivery and mailbox | While needed for response, support, or audit |

## Enterprise API Access

| Data | Purpose | Access | Storage | Retention |
| --- | --- | --- | --- | --- |
| Organization name | API account administration | API admins | API key database | While API access is active or audit is needed |
| Contact email | API support and administration | API admins | API key database | While API access is active or audit is needed |
| API key prefix | Identify key without storing raw secret | API admins | API key database | While API access is active or audit is needed |
| API key hash | Authenticate API key | System only | API key database | Until key is deleted or rotated |
| Plan, quota, status | API entitlement and revocation | API admins | API key database | While API access is active or audit is needed |
| Endpoint, method, status code, timestamp | Usage, support, security, future billing | API admins | API usage database | While needed for usage administration, audit, or billing |

Notes:
- Raw API keys are shown once and are not stored.
- Stored API keys are salted and hashed.
- API access is separate from researcher website login.

## Analytics And Cookies

| Data | Purpose | Access | Storage | Retention |
| --- | --- | --- | --- | --- |
| Google Analytics events | Aggregate website usage analysis | Project admins and Google Analytics | Google Analytics | According to configured analytics retention |
| Anonymous map identifier cookie | Aggregate map interaction metrics when enabled | Project admins | Browser cookie and metrics service | According to cookie lifetime and metrics retention |

## Open Items Before Production

- Confirm the deployed database and storage encryption-at-rest guarantees with the infrastructure owner.
- Agree exact retention periods and deletion/anonymization process with UNU policy/legal stakeholders.
- Document the user request process for access, correction, export, and deletion.
- Review whether a cookie notice or consent mechanism is required for analytics in the target jurisdictions.
