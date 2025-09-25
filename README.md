# Result Portal — Starter (Plain‑Language Blueprint + File Templates)

This starter pack includes:
- Plain-language blueprint (README)
- Data templates for **students** and **results** CSV imports
- Email template (Markdown) for personalized result announcements
- `.env.example` for environment variables
- Suggested Django app structure (folders only; you will initialize Django later)

For the technical multi-stage prompt, see your ChatGPT message (copy it into `TECH_PROMPT.md` if you like).

## Stage 1 — Google Workspace Authentication

- Google OAuth2 login wired via `social-auth-app-django` with domain restriction to `@pmc.edu.pk` accounts.
- Custom pipeline links authenticated users to `Student` records (created from roster imports).
- Minimal UI for `/accounts/login/` providing a Google sign-in button and messaging for restricted access.
- Staff accounts signing in with the institutional domain are auto-provisioned to simplify admin onboarding.