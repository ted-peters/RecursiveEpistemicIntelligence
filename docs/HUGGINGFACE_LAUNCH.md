# Publish the REI interactive research demonstration on Hugging Face

**No ZIP downloads, terminal commands, or Hugging Face API tokens are required.** The source is already stored in GitHub. The deployment uses Hugging Face's **Trusted Publishers** feature for a short-lived, repository-scoped authorization from GitHub Actions.

## What will be published?

`space-static/` contains a **free, publicly accessible Static Space**. The interface loads Pyodide (a pinned public browser Python runtime) and evaluates the real, unchanged REI-1.0 epistemic graph source in the visitor's browser. The fictional example approvals, evidence and observations remain clearly labeled synthetic. No backend model, external retrieval, sensitive credentials, or paid inference is required.

The original optional Gradio application remains available in `space/`, but the Static Space is the recommended first launch because Hugging Face's current policy makes the static tier free for all accounts; hosted Gradio compute generally requires a subscription or an eligible ZeroGPU arrangement.

## One-time Hugging Face setup

1. Sign in or create an account at <https://huggingface.co/join>.
2. The owner has supplied the intended Space: **<https://huggingface.co/spaces/tedpeters/RecursiveEpistemicIntelligence>**. Confirm it is **Public**, and that the **SDK is Static**. If it was created as Gradio or Docker, use the Hugging Face Space settings or the repository README SDK metadata to switch to Static before final launch.
3. In the Space, open **Settings → Trusted Publishers → Add**. Configure:
   - **Provider:** GitHub Actions
   - **Repository:** `ted-peters/RecursiveEpistemicIntelligence`
   - **Branch:** `main`
   - **Workflow:** `publish-huggingface.yml`
   - **Permission:** allow writing (do not mark read-only)
4. The GitHub deployment target is now fixed to `tedpeters/RecursiveEpistemicIntelligence`; no GitHub repository variable or API token is needed. **Do not share passwords or access tokens.**
5. After authorizing Trusted Publishers, open [GitHub Actions](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/workflows/publish-huggingface.yml), select **Run workflow** on `main`, and confirm the job succeeds. Future updates to `space-static/` automatically publish when pushed to `main`.
6. Visit <https://huggingface.co/spaces/tedpeters/RecursiveEpistemicIntelligence> and check the interactive REI dashboard. The browser downloads Pyodide on first use.

### Troubleshooting

- **Workflow fails with an OIDC authorization error:** Add the GitHub Actions Trusted Publisher to the specific Space under its Settings (step 3), then rerun the workflow.
- **Trusted Publisher authorization error (`invalid_grant`):** Confirm the Hugging Face repo Settings → Trusted Publishers entries exactly match the GitHub repo, `main` branch, and `publish-huggingface.yml`. If the Space was renamed, update the `HF_SPACE_ID` and `HF_OIDC_RESOURCE` workflow values.
- **HTTP 402 / billing error:** You likely created a Gradio or Docker Space. Create a new *Static* Space instead. The static runtime runs in the visitor's browser and requires no paid hardware.
- **Page says Python could not load:** The visitor's browser or firewall blocked the pinned Pyodide CDN. Try a modern browser with network access to `cdn.jsdelivr.net`.
- **Python module unavailable:** Verify the GitHub workflow uploaded the entire `space-static/` directory, including `driver.py` and `rei0/`.
- **Looks like the original Gradio demo:** The new free deployment uses `space-static/` with `sdk: static`; the Gradio app is under `space/` and is a separate optional version.

## Scientific status

This is a software demonstration under scripted, synthetic review metadata, not a benchmark of live AI accuracy. Do not claim independent confirmation that REI outperforms conventional language models. The full REI-1.0 research project is at <https://github.com/ted-peters/RecursiveEpistemicIntelligence>.

References: <https://huggingface.co/docs/hub/spaces-sdks-static> and <https://huggingface.co/docs/hub/trusted-publishers>.
