# Administrator guide (MOCK release)

Start the stack with `docker compose up --build`, then open the dashboard. Use `superadmin@example.local` with `ChangeMe123!` only for the local demo; change it immediately in any non-demo deployment. The password is Argon2-hashed and the account is flagged for a change on first sign-in.

Sign in from the **Authenticated admin demo** panel to access protected control-plane APIs. Super Admins can create Admins and users; Admins can create Trader and Viewer accounts. Viewer accounts cannot use protected management actions. Login failures are audited and five consecutive failures lock a demo account for 15 minutes.

The AI Strategy Assistant creates a non-executing `DRAFT`. An Admin or Super Admin may approve only a safe draft. Approval means mock-validation eligibility, not live authorization; it never submits an order.

The current control plane is in memory and resets with the service. Do not use its demo identities as a production identity system.
