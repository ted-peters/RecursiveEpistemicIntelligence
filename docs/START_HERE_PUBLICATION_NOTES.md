# Publish REI without using a terminal

You have three ZIP downloads:

1. **REI_GitHub_Repository.zip**: full REI-1.0 engine, tests, philosophical blueprint, open research material, and Space source.
2. **REI_HuggingFace_Gradio_Space.zip**: Python-backed, interactive demo using the original REI graph. It may require an eligible Hugging Face plan or compute credits to host.
3. **REI_HuggingFace_Static_Space.zip**: free-compute alternative showing an interactive, prerecorded REI explanation; **does not run Python**.

**Do NOT upload the separate private research archive.** It contains answer keys from a previously circulated synthetic study; use a new independently held-out dataset for a real head-to-head.

## Step A — GitHub, in your web browser

1. Sign in or create an account at https://github.com/.
2. Go to https://github.com/new. Name your repository `recursive-epistemic-intelligence`. Select **Public** if you want the code to be visible. Choose to create an **empty** repo without auto-generating README, .gitignore, or LICENSE (the package already has these).
3. Download and **extract/unzip** `REI_GitHub_Repository.zip` on your computer. **A ZIP uploaded without extracting will not become a browsable code repository.**
4. In the new repository, select **Add file → Upload files**. Drag the extracted *contents* (not just the enclosing folder). GitHub's browser uploader permits up to **100 files per upload**; this project has more, so upload it in 2+ batches or use GitHub Desktop if preferred. Retain folder paths.
5. Click **Commit changes** and verify that `README.md`, `rei0/`, `tests/`, `docs/`, and `space/` appear at the repo root.
6. **Never** upload API keys, reviewer private keys, a `.env` file, or any file with `PRIVATE` in its name.

## Step B — Hugging Face demo, in your browser

1. Sign in or create an account at https://huggingface.co/.
2. Visit https://huggingface.co/new-space and give it a name like `rei-research-demo`.
3. Choose **Gradio** as the SDK (if your account permits a Gradio Space), and choose Public or Private. Some account/hardware combinations currently require a paid plan; read the host's actual terms rather than assuming hosting is free.
4. Extract `REI_HuggingFace_Gradio_Space.zip`. In the new Space open **Files → Add file → Upload files**. Upload the contents, keeping `README.md`, `app.py`, `requirements.txt`, and the `rei0/` folder. Do not upload the ZIP alone.
5. Let Hugging Face build the Space. Open the **App** tab to explore the fictional evidence demo. The first build may take time.
6. If Gradio hosting isn't available for your account, create a new **Static** Space instead and upload the unzipped `REI_HuggingFace_Static_Space.zip` (`README.md`, `index.html`, `LICENSE`). The static site doesn't execute Python.

## What to tell visitors

> Recursive Epistemic Intelligence (REI) is an open research project exploring challengeable beliefs, evidence tracking, and belief revision. The software demonstration is not a trained foundation model and has not been shown to outperform conventional AI on a live, independent benchmark.

## Quick checks after publishing

- GitHub displays the project description at the repository home.
- Hugging Face has an **App** tab showing the demo, not an import error.
- Moving the slider changes evidence status, and conflicting evidence displays **BOTH**.
- No private keys or held-out grading files have been published.

## References

- GitHub browser uploads: https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- Hugging Face Gradio Spaces: https://huggingface.co/docs/hub/spaces-sdks-gradio
- Hugging Face Spaces overview and availability: https://huggingface.co/docs/hub/spaces-overview
- Hugging Face repository uploads: https://huggingface.co/docs/hub/repositories-getting-started