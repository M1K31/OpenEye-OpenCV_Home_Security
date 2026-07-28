# Privacy Policy — OpenEye Home Security

**Owner / Data Controller:** Smart Industries LLC (owner: Mikel Smart)
**Product:** OpenEye — OpenCV Home Security
**Effective date:** 2026-07-24
**Contact:** privacy@smartindustries.example (update to your official address before publication)

> This policy is written for a **self-hosted, privacy-first** surveillance application distributed via direct download and, where applicable, the Apple App Store and Google Play Store. OpenEye is designed so that video, images, and biometric data remain on hardware the user controls. Smart Industries LLC does not operate a central server that receives your footage unless you explicitly configure an optional third-party cloud provider.

---

## 1. Who we are

OpenEye is developed and owned by **Smart Industries LLC** ("Smart Industries", "we", "us"). Smart Industries is the data controller for any information described in this policy that is processed by the official OpenEye application and companion services.

## 2. Our privacy model in one sentence

**Your data stays on your device/server by default.** OpenEye performs camera capture, motion detection, object detection, and face recognition **locally**. We do not collect, transmit, sell, or monetize your video, images, or biometric data.

## 3. Information the app processes

Because OpenEye is self-hosted, the following categories are processed **on infrastructure you control** (your computer, Raspberry Pi, or private server):

| Category | Examples | Where it lives | Purpose |
|----------|----------|----------------|---------|
| Video & images | Live streams, recorded clips, snapshots | Your local storage (`data/`, configured recordings dir) | Core surveillance function |
| Biometric / face data | Face encodings, face clusters, recognition labels | Local encrypted/permissioned files & local DB | Optional face-recognition feature (opt-in) |
| Camera & network config | Camera IPs, RTSP URLs, credentials, discovery results | Local DB + `.env` (permission `0600`) | Device connectivity |
| Account data | Username, hashed password (bcrypt), 2FA secret, JWT session tokens | Local DB / browser | Authentication |
| Operational logs | Audit logs, event timelines, error logs | Local `logs/` | Security auditing & debugging |

**Sensitive data notice:** Face-recognition data is **biometric information** and may be regulated (e.g., BIPA in Illinois, GDPR Article 9 in the EU). This feature is **opt-in** and disabled until you enable it. You are responsible for obtaining any consent required from individuals who may be recorded.

## 4. Information Smart Industries receives

By default, **none of your surveillance data reaches Smart Industries.** We may receive limited data only when you take an explicit action:

- **Optional cloud storage / notifications (opt-in):** If you configure a third-party provider (e.g., AWS S3, an SMTP server, MQTT broker, push service), data is transmitted **directly from your instance to that provider** under that provider's own privacy policy. Smart Industries is not an intermediary.
- **Optional diagnostics/crash reporting (opt-in):** If enabled, anonymized error traces (no video/biometric content) may be sent to help improve stability. This is off unless you turn it on.
- **App store metadata:** When distributed via the App Store or Play Store, the store platform collects install/analytics data governed by Apple's and Google's respective privacy policies, not this one.

We do **not** use your data for advertising, profiling, or training AI models.

## 5. Third-party integrations you may enable

OpenEye can connect to services **you choose**: AWS S3, SMTP/email, Twilio/SMS, MQTT, Home Assistant, Google Nest, Apple HomeKit, webhooks, and push-notification providers. When you enable an integration, data flows directly between your instance and that service under **their** terms and privacy policy. Review those before enabling.

## 6. How data is protected

- Passwords hashed with bcrypt; sessions via signed JWT.
- Optional two-factor authentication (TOTP).
- Secrets stored in a permission-restricted `.env` (`0600`), never committed to source control.
- Security middleware: rate limiting, security headers, SQL-injection protection.
- You are responsible for securing the host OS, network, and physical access to your OpenEye server.

## 7. Data retention & deletion

- Recordings and events are retained per **your** configured retention settings and storage limits.
- Uninstalling removes application code; use `uninstall.sh` (removes data) or `uninstall-keep-data.sh` (preserves recordings) to control data deletion.
- To delete face-recognition data, remove the enrolled faces via the app; encodings are deleted from local storage.

## 8. Children's privacy

OpenEye is not directed to children under 13 (or the applicable age in your jurisdiction). We do not knowingly collect data from children.

## 9. Your rights

Depending on your jurisdiction (GDPR, CCPA/CPRA, etc.) you may have rights to access, correct, delete, or export personal data. Because data is under your control, you exercise most of these rights directly within the app or on your storage. For data Smart Industries may hold (e.g., opt-in diagnostics), contact us at the address above.

## 10. Legal & regulatory responsibility of the operator

Surveillance laws vary. As the operator you are responsible for compliance with local recording-consent, notification-signage, biometric-consent (e.g., BIPA), and data-protection laws. OpenEye provides tools, not legal advice.

## 11. Platform-specific disclosures

- **Apple App Store:** No data collected by Smart Industries by default; "Data Not Collected" applies unless you enable opt-in diagnostics. Face data is processed on-device.
- **Google Play:** Data Safety section reflects local processing; no data shared/sold by Smart Industries.
- **Direct/self-hosted:** This policy governs the official build; forks/modifications are the responsibility of their distributor.

## 12. Changes to this policy

We will update the effective date above and, for material changes, provide in-app or release-notes notice.

## 13. Contact

Smart Industries LLC — Attn: Privacy (Mikel Smart)
Email: privacy@smartindustries.example *(replace with your official contact before store submission)*

---

© 2026 Smart Industries LLC. OpenEye and the OpenEye logo are property of Smart Industries LLC. All rights reserved.
