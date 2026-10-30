# SCRUB-REPORT — lines that matched a credential pattern

Review every line. Real secrets get redacted in the vendored copy and rotated at the source. False positives get a note here.

- `vendor\backrooms\stream\admin.py:254` [assignment] `const TOKEN='__ADMIN_TOKEN__';`
- `vendor\unity-command\docs\CONFIGURATION.md:94` [pollinations key] `POLLINATIONS_API_KEY=pk_YourPublishableKeyHere`
- `vendor\unity-command\docs\FINALIZED.md:128` [pollinations key] `- Default key shipped in PolliLibPy: ʼpk_REDACTED_IN_VENDOR_COPYʼ`
- `vendor\website2-old-site\PolliLibJS\README.md:95` [assignment] `apiKey: "pk_your_key_here"`
- `vendor\website2-old-site\PolliLibPy\pollylib.py:32` [pollinations key] `DEFAULT_API_KEY = "pk_REDACTED_IN_VENDOR_COPY"`
- `vendor\website2-old-site\PolliLibPy\pollylib.py:39` [pollinations key] `api_key: API key for authentication (default: pk_REDACTED_IN_VENDOR_COPY)`
- `vendor\website2-old-site\PolliLibPy\README.md:91` [assignment] `api = PollinationsAPI(api_key="pk_your_key_here")`

## Review (2026-10-30)

- `backrooms/stream/admin.py:254` — placeholder `__ADMIN_TOKEN__` substituted at runtime. False positive.
- `unity-command/docs/CONFIGURATION.md:94`, `website2-old-site/PolliLibJS/README.md:95`, `website2-old-site/PolliLibPy/README.md:91` — documentation placeholders. False positive.
- `website2-old-site/PolliLibPy/pollylib.py:32,39` and `unity-command/docs/FINALIZED.md:128` — a real Pollinations publishable key shipped as a library default. **Redacted** in the vendored copies to `pk_REDACTED_IN_VENDOR_COPY`. The adapted provider layer takes the key from config, never a baked default. Rotate the key at pollinations.ai if it is still active.
