# Community consolidation implementation plan

> Execute inline with superpowers:executing-plans; perform one independent whole-branch review before publication/merge.

**Goal:** Consolidate the selected community features into the latest upstream project, publish and merge after verification, and replace the three old local source directories with one complete checkout.

**Architecture:** Start at upstream main, retaining its Markdown/rich-text editor wrapper, SDK pages, streaming storage, upload limits, moderation, and authorization. Port only the selected local changes. Untrusted Host/forwarded headers must not become unrestricted SSO redirect targets.

**Tech stack:** FastAPI, SQLAlchemy, Redis, Next.js 15, React 19, Tiptap 3, Python unittest, Node test runner, browser regression tests.

**Spec:** User-approved feature inventory 1–17 in this chat and the final selection of 2026-11-10.

## Constraints

- Include SSO callback consistency, existing banners/editor/video/branding, editor fullscreen/view/image enhancements, post editing/sharing, profile editing, infinite scrolling, optional automatic SSO and failure fallback, audit pagination/search/jump/Beijing time, and category/post announcement layout.
- Exclude the local customer-specific HiAgent implementation, news-source expansion, Weaviate rewrites, registration/login reward removal, and category-label feature. Preserve upstream generic implementations.
- No customer hostnames, AppKeys, credentials, deployment IPs, generated builds, or archived delivery payloads in the PR.
- Preserve the original source directories until consolidation is tested and merged. Native worktree request was cancelled; use the existing independent clone without retrying that request.
- The user has authorized push, PR, merge after successful validation, and deletion of superseded local source directories.

## Task 1: Backend integration

- Add regression coverage for configuration whitelist/defaults, trusted callback origins, one-time state binding, browser failure fallback, and post edit authorization/moderation/concurrent updates.
- Run new coverage against main to confirm missing behavior, then port the selected APIs and supporting services.
- Keep streaming upload/storage and upstream database behavior intact. Run the full backend unittest suite; report unavailable external database checks separately.

## Task 2: Frontend integration

- Port automatic SSO helpers/configuration, explicit entry route, post edit/share, profile modals, audit controls/time formatting, selected login/layout changes, and rich editor enhancements while keeping the Markdown mode and upload-busy protection.
- Add/execute logic and browser regression tests. Exercise stale requests, duplicate scroll loads, profile load/save failures, storage denial, clipboard fallback, audit filtering/jumping, and editor fullscreen/view switching.
- Run TypeScript checks and the production build. Preserve generic SDK navigation and the existing dynamic announcement card.

## Task 3: Review, publish, consolidate

- Run whitespace/scope/secret checks. Commit, bind evidence to base/head SHAs, and request an independent read-only review.
- Address material findings with failing-then-passing regression tests and rerun affected/full verification.
- Push the integration branch to the established fork; create one Chinese PR into stepll2026/AinaDev main. Recheck exact head/base, checks and review threads before the authorized merge.
- Verify the merged upstream commit. Copy the complete independent repository into the project as AinaDev, include README/setup/env/test instructions, then delete the superseded source directories with checked absolute PowerShell targets. Keep the retained release archives and audit records.

## Review focus

- Host/proxy spoofing must not exfiltrate SSO credentials; callback/token exchange must use one validated origin.
- Editing must enforce ownership, moderation and concurrent-update checks without rerunning automatic replies.
- Asynchronous category/sort/profile requests must not overwrite a later selection or clear unseen employee fields.
- Automatic SSO and storage failures must leave manual login usable and avoid redirect loops.
- Pagination, observer triggers, modal focus and editor mode changes must remain usable on desktop/mobile.
