# Publish the REI interactive research demonstration on Hugging Face

**No ZIP downloads, terminal commands, or Hugging Face API tokens are required.** The source is already stored in GitHub. The deployment uses Hugging Face's **Trusted Publishers** feature for a short-lived, repository-scoped authorization from GitHub Actions.

## What will be published?

`space-static/` contains a **free, publicly accessible Static Space**. The interface loads Pyodide (a pinned public browser Python runtime) and evaluates the real, unchanged REI-1.0 epistemic graph source in the visitor's browser. The fictional example approvals, evidence and observations remain clearly labeled synthetic. No backend model, external retrieval, sensitive credentials, or paid inference is required.

The original optional Gradio application remains available in `space/`, but the Static Space is the recommended first launch because Hugging Face's current policy makes the static tier free for all accounts; hosted Gradio compute generally requires a subscription or an eligible ZeroGPU arrangement.

## One-time Hugging Face setup

1. Sign in or create an account at <https://huggingface.co/join>.
2. Open <https://huggingface.co/new-space> and create a **Public** Space. A suggested name is `rei-interactive` (choose your own available name). Under SDK, select **Static**. The Space is owned by your Hugging Face account; your Hugging Face username does not need to equal your GitHub username.
3. In the Space, open **Settings → Trusted Publishers → Add**. Configure:
   - **Provider:** GitHub Actions
   - **Repository:** `ted-peters/RecursiveEpistemicIntelligence`
   - **Branch:** `main`
   - **Workflow:** `publish-huggingface.yml`
   - **Permission:** allow writing (do not mark read-only)
4. Send the full Space URL (`https://huggingface.co/spaces/YOUR-USERNAME/YOUR-SPACE-NAME`) back to ChatGPT. **Do not send passwords, tokens, or other secret credentials.** The assistant can then set up the matching GitHub deployment target; alternatively you can set the repository variable yourself using step 5.
5. Optional do-it-yourself configuration: Go to [GitHub repository Actions variables](https://github.com/ted-peters/RecursiveEpistemicIntelligence/settings/variables/actions), choose **New repository variable**, and set name `HF_SPACE_ID`, value `YOUR-USERNAME/YOUR-SPACE-NAME` (no `spaces/` prefix).
6. Open [GitHub Actions](https://github.com/ted-peters/RecursiveEpistemicIntelligence/actions/workflows/publish-huggingface.yml). Select **Run workflow** on `main` once `HF_SPACE_ID` is configured. Future updates to `space-static/` automatically publish on a push to `main`.
7. Check your Hugging Face Space URL. You should see the interactive REI dashboard. On first visit the browser downloads Pyodide; subsequent visits are usually faster.

### Troubleshooting

- **Job skipped:** GitHub repository variable `HF_SPACE_ID` is not configured.
- **Trusted Publisher authorization error (`invalid_grant`):** Confirm the Hugging Face repo Settings → Trusted Publishers entries exactly match the GitHub repo, `main` branch, and `publish-huggingface.yml`. If the Space was renamed, update `HF_SPACE_ID`.
- **HTTP 402 / billing error:** You likely created a Gradio or Docker Space. Create a new *Static* Space instead. The static runtime runs in the visitor's browser and requires no paid hardware.
- **Page says Python could not load:** The visitor's browser or firewall blocked the pinned Pyodide CDN. Try a modern browser with network access to `cdn.jsdelivr.net`.
- **Python module unavailable:** Verify the GitHub workflow uploaded the entire `space-static/` directory, including `driver.py` and `rei0/`.
- **Looks like the original Gradio demo:** The new free deployment uses `space-static/` with `sdk: static`; the Gradio app is under `space/` and is a separate optional version.

## Scientific status

This is a software demonstration under scripted, synthetic review metadata, not a benchmark of live AI accuracy. Do not claim independent confirmation that REI outperforms conventional language models. The full REI-1.0 research project is at <https://github.com/ted-peters/RecursiveEpistemicIntelligence>.

References: <https://huggingface.co/docs/hub/spaces-sdks-static> and <https://huggingface.co/docs/hub/trusted-publishers>.
